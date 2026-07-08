param(
    [string]$InputFile = "data/pcb442.tsp",
    [string]$MaxGens = "1000,3000,5000",
    [int]$MigrationInterval = 100,
    [int]$LocalToGlobalRatio = 5,
    [string]$Seeds = "12345,22345,32345",
    [string]$ResultsFile = "results/convergence_sensitivity_results.csv"
)

$ErrorActionPreference = "Stop"

function Get-ProjectRoot {
    $scriptDir = $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($scriptDir)) {
        $scriptDir = (Get-Location).Path
    }
    if (Test-Path -LiteralPath (Join-Path $scriptDir "src")) {
        return (Resolve-Path -LiteralPath $scriptDir).Path
    }
    return (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
}

function Resolve-ProjectPath([string]$Path) {
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return (Join-Path $ProjectRoot $Path)
}

function Invoke-NativeCommand([string]$Label, [string[]]$Command) {
    $exe = $Command[0]
    $args = @()
    if ($Command.Count -gt 1) {
        $args = $Command[1..($Command.Count - 1)]
    }

    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $exe @args 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }

    if ($exitCode -ne 0) {
        $output | ForEach-Object { Write-Host $_ }
        throw "$Label failed with exit code $exitCode"
    }

    return $output
}

function Compile-Serial {
    Write-Host "[COMPILE] SERIAL"
    Invoke-NativeCommand "compile SERIAL" @(
        "gcc", "-std=c11", "-Wall", "-Wextra", "-O2",
        $SerialSource, "-lm", "-o", $SerialExe
    ) | Out-Null
}

function Compile-MpiProgram([string]$Name, [string]$Source, [string]$ExePath) {
    if (Get-Command mpicc -ErrorAction SilentlyContinue) {
        Write-Host "[COMPILE] $Name with mpicc"
        Invoke-NativeCommand "compile $Name with mpicc" @(
            "mpicc", "-std=c11", "-Wall", "-Wextra", "-O2",
            $Source, "-lm", "-o", $ExePath
        ) | Out-Null
    } elseif ((Get-Command gcc -ErrorAction SilentlyContinue) -and $env:MSMPI_INC -and $env:MSMPI_LIB64) {
        Write-Host "[COMPILE] $Name with gcc + MS-MPI SDK"
        $msmpiInc = $env:MSMPI_INC.TrimEnd('\')
        $msmpiLibDir = $env:MSMPI_LIB64.TrimEnd('\')
        Invoke-NativeCommand "compile $Name with gcc + MS-MPI SDK" @(
            "gcc", "-std=c11", "-Wall", "-Wextra", "-O2",
            "-I$msmpiInc", $Source, "-L$msmpiLibDir", "-lmsmpi", "-lm", "-o", $ExePath
        ) | Out-Null
    } else {
        throw "No usable MPI C compiler found. Need mpicc, or gcc with MSMPI_INC/MSMPI_LIB64."
    }
}

function Parse-IntList([string]$Text, [string]$Name) {
    $values = @()
    foreach ($item in ($Text -split ",")) {
        $trimmed = $item.Trim()
        if ($trimmed.Length -eq 0) {
            continue
        }
        $values += [int]$trimmed
    }
    if ($values.Count -eq 0) {
        throw "No $Name provided"
    }
    return $values
}

function Format-NumberText([string]$Text, [string]$Format) {
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    $value = [double]::Parse($Text, $culture)
    return $value.ToString($Format, $culture)
}

function Read-LastResultRow([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Temporary result CSV was not created: $Path"
    }
    $rows = @(Import-Csv -LiteralPath $Path)
    if ($rows.Count -lt 1) {
        throw "Temporary result CSV has no data rows: $Path"
    }
    return $rows[$rows.Count - 1]
}

function Append-UnifiedResult([hashtable]$Case, [int]$CurrentMaxGen, [int]$Seed, [string]$TempPath) {
    $row = Read-LastResultRow $TempPath
    if ($row.algorithm -ne $Case.Algorithm) {
        throw "Expected algorithm $($Case.Algorithm) but got $($row.algorithm) in $TempPath"
    }
    if ([int]$row.nproc -ne [int]$Case.NProc) {
        throw "Expected nproc $($Case.NProc) but got $($row.nproc) in $TempPath"
    }
    if ([int]$row.base_seed -ne $Seed) {
        throw "Expected seed $Seed but got $($row.base_seed) in $TempPath"
    }

    $globalBest = Format-NumberText $row.global_best "0.######"
    $elapsedSec = Format-NumberText $row.elapsed_sec "0.######"
    $line = "{0},{1},{2},{3},{4},{5},{6},{7},{8}" -f `
        $Case.Algorithm, $Case.NProc, $CurrentMaxGen, $Case.MigrationInterval, `
        $Case.LocalToGlobalRatio, $Case.NumGroups, $Seed, $globalBest, $elapsedSec
    Add-Content -LiteralPath $ResultsPath -Encoding UTF8 -Value $line

    Write-Host ("[DONE] global_best={0} elapsed_sec={1}" -f $globalBest, $elapsedSec)
}

function Invoke-ExperimentCase([hashtable]$Case, [int]$CurrentMaxGen, [int]$Seed) {
    $tempName = "tmp_convergence_{0}_n{1}_g{2}_max{3}_seed{4}.csv" -f `
        $Case.Algorithm.ToLowerInvariant(), $Case.NProc, $Case.NumGroups, $CurrentMaxGen, $Seed
    $tempPath = Join-Path $TempDir $tempName
    if (Test-Path -LiteralPath $tempPath) {
        Remove-Item -LiteralPath $tempPath -Force
    }

    Write-Host ("[RUN] {0} n={1} groups={2} maxGen={3} seed={4}" -f `
        $Case.Algorithm, $Case.NProc, $Case.NumGroups, $CurrentMaxGen, $Seed)

    if ($Case.Algorithm -eq "SERIAL") {
        Invoke-NativeCommand "execute SERIAL maxGen=$CurrentMaxGen seed=$Seed" @(
            $SerialExe, $InputPath, "$CurrentMaxGen", "$Seed", $tempPath
        ) | Out-Null
    } elseif ($Case.Algorithm -eq "DEA") {
        Invoke-NativeCommand "execute DEA n=$($Case.NProc) maxGen=$CurrentMaxGen seed=$Seed" @(
            "mpiexec", "-n", "$($Case.NProc)", $DeaExe, $InputPath,
            "$CurrentMaxGen", "$($Case.MigrationInterval)", "$Seed", $tempPath
        ) | Out-Null
    } elseif ($Case.Algorithm -eq "HDEA") {
        Invoke-NativeCommand "execute HDEA n=$($Case.NProc) groups=$($Case.NumGroups) maxGen=$CurrentMaxGen seed=$Seed" @(
            "mpiexec", "-n", "$($Case.NProc)", $HdeaExe, $InputPath,
            "$CurrentMaxGen", "$($Case.MigrationInterval)", "$($Case.LocalToGlobalRatio)",
            "$($Case.NumGroups)", "$Seed", $tempPath
        ) | Out-Null
    } elseif ($Case.Algorithm -eq "MOVING_HDEA") {
        Invoke-NativeCommand "execute MOVING_HDEA n=$($Case.NProc) groups=$($Case.NumGroups) maxGen=$CurrentMaxGen seed=$Seed" @(
            "mpiexec", "-n", "$($Case.NProc)", $MovingHdeaExe, $InputPath,
            "$CurrentMaxGen", "$($Case.MigrationInterval)", "$($Case.LocalToGlobalRatio)",
            "$($Case.NumGroups)", "$Seed", $tempPath
        ) | Out-Null
    } else {
        throw "Unknown algorithm: $($Case.Algorithm)"
    }

    Append-UnifiedResult $Case $CurrentMaxGen $Seed $tempPath
    Remove-Item -LiteralPath $tempPath -Force
}

function Validate-ConvergenceResults {
    $rows = @(Import-Csv -LiteralPath $ResultsPath)
    $expectedRows = $cases.Count * $maxGenList.Count * $seedList.Count
    if ($rows.Count -ne $expectedRows) {
        throw "Expected $expectedRows result rows, got $($rows.Count)"
    }

    $seenKeys = @{}
    foreach ($row in $rows) {
        foreach ($field in @("global_best", "elapsed_sec")) {
            if ([string]::IsNullOrWhiteSpace($row.$field)) {
                throw "Empty $field in result row: $($row | ConvertTo-Json -Compress)"
            }
            $parsed = 0.0
            if (-not [double]::TryParse($row.$field, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsed)) {
                throw "Non-numeric $field in result row: $($row.$field)"
            }
        }
        $key = "{0}|{1}|{2}|{3}|{4}|{5}|{6}" -f `
            $row.algorithm, $row.nproc, $row.maxGen, $row.migration_interval, `
            $row.local_to_global_ratio, $row.num_groups, $row.base_seed
        if ($seenKeys.ContainsKey($key)) {
            throw "Duplicate result row for $key"
        }
        $seenKeys[$key] = $true
    }

    foreach ($case in $cases) {
        foreach ($currentMaxGen in $maxGenList) {
            $groupRows = @(
                $rows | Where-Object {
                    $_.algorithm -eq $case.Algorithm -and
                    [int]$_.nproc -eq [int]$case.NProc -and
                    [int]$_.maxGen -eq [int]$currentMaxGen -and
                    [int]$_.migration_interval -eq [int]$case.MigrationInterval -and
                    [int]$_.local_to_global_ratio -eq [int]$case.LocalToGlobalRatio -and
                    [int]$_.num_groups -eq [int]$case.NumGroups
                }
            )
            if ($groupRows.Count -ne $seedList.Count) {
                throw "Expected $($seedList.Count) rows for $($case.Algorithm) n=$($case.NProc) maxGen=$currentMaxGen groups=$($case.NumGroups), got $($groupRows.Count)"
            }
            foreach ($seed in $seedList) {
                $seedRows = @($groupRows | Where-Object { [int]$_.base_seed -eq [int]$seed })
                if ($seedRows.Count -ne 1) {
                    throw "Expected one seed=$seed row for $($case.Algorithm) n=$($case.NProc) maxGen=$currentMaxGen, got $($seedRows.Count)"
                }
            }
        }
    }

    Write-Host "validated $($rows.Count) result rows in $ResultsPath"
}

$ProjectRoot = Get-ProjectRoot
$InputPath = Resolve-ProjectPath $InputFile
$ResultsPath = Resolve-ProjectPath $ResultsFile
$ResultsDir = Split-Path -Parent $ResultsPath
$TempDir = Join-Path $ResultsDir "_tmp_convergence_sensitivity"
$BinDir = Join-Path $ProjectRoot "bin"
$SerialSource = Join-Path $ProjectRoot "src/tsp_serial_exp.c"
$DeaSource = Join-Path $ProjectRoot "src/tsp_mpi_dea.c"
$HdeaSource = Join-Path $ProjectRoot "src/tsp_mpi_hdea.c"
$MovingHdeaSource = Join-Path $ProjectRoot "src/tsp_mpi_moving_hdea.c"
$SerialExe = Join-Path $BinDir "tsp_serial_exp.exe"
$DeaExe = Join-Path $BinDir "tsp_mpi_dea.exe"
$HdeaExe = Join-Path $BinDir "tsp_mpi_hdea.exe"
$MovingHdeaExe = Join-Path $BinDir "tsp_mpi_moving_hdea.exe"

New-Item -ItemType Directory -Force -Path $BinDir, $ResultsDir, $TempDir | Out-Null

foreach ($path in @($InputPath, $SerialSource, $DeaSource, $HdeaSource, $MovingHdeaSource)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required file not found: $path"
    }
}
if (-not (Get-Command gcc -ErrorAction SilentlyContinue)) {
    throw "gcc not found"
}
if (-not (Get-Command mpiexec -ErrorAction SilentlyContinue)) {
    throw "mpiexec not found"
}

$maxGenList = Parse-IntList $MaxGens "maxGen values"
$seedList = Parse-IntList $Seeds "seeds"

$cases = @(
    @{ Algorithm = "SERIAL"; NProc = 1; MigrationInterval = 0; LocalToGlobalRatio = 0; NumGroups = 0 },
    @{ Algorithm = "DEA"; NProc = 4; MigrationInterval = $MigrationInterval; LocalToGlobalRatio = 0; NumGroups = 0 },
    @{ Algorithm = "HDEA"; NProc = 4; MigrationInterval = $MigrationInterval; LocalToGlobalRatio = $LocalToGlobalRatio; NumGroups = 2 },
    @{ Algorithm = "MOVING_HDEA"; NProc = 4; MigrationInterval = $MigrationInterval; LocalToGlobalRatio = $LocalToGlobalRatio; NumGroups = 2 }
)

Compile-Serial
Compile-MpiProgram "DEA" $DeaSource $DeaExe
Compile-MpiProgram "HDEA" $HdeaSource $HdeaExe
Compile-MpiProgram "MOVING_HDEA" $MovingHdeaSource $MovingHdeaExe

if (Test-Path -LiteralPath $ResultsPath) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = "$ResultsPath.bak-$timestamp"
    Move-Item -LiteralPath $ResultsPath -Destination $backup
    Write-Host "backed up existing convergence-sensitivity results to $backup"
}

Set-Content -LiteralPath $ResultsPath -Encoding UTF8 -Value `
    "algorithm,nproc,maxGen,migration_interval,local_to_global_ratio,num_groups,base_seed,global_best,elapsed_sec"

Write-Host "convergence sensitivity settings: input=$InputPath maxGen=$($maxGenList -join ',') migration_interval=$MigrationInterval local_to_global_ratio=$LocalToGlobalRatio seeds=$($seedList -join ',') results=$ResultsPath"

foreach ($currentMaxGen in $maxGenList) {
    foreach ($case in $cases) {
        foreach ($seed in $seedList) {
            Invoke-ExperimentCase $case $currentMaxGen $seed
        }
    }
}

Validate-ConvergenceResults
Remove-Item -LiteralPath $TempDir -Recurse -Force
Write-Host "convergence sensitivity experiment completed"
