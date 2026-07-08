param(
    [string]$InputFile = "data/pcb442.tsp",
    [int]$MaxGen = 5000,
    [int]$MigrationInterval = 25,
    [int]$LocalToGlobalRatio = 20,
    [string]$Seeds = "12345,22345,32345,42345,52345",
    [string]$ResultsFile = "results/reproduction_extension_results.csv"
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
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $Path))
}

function Assert-NotProtectedResultPath([string]$Path) {
    $resolved = Resolve-ProjectPath $Path
    $protected = @(
        "results/final_experiment_results.csv",
        "results/final_analysis_summary.csv",
        "results/final_analysis_summary.txt"
    )
    foreach ($item in $protected) {
        $protectedPath = Resolve-ProjectPath $item
        if ([string]::Equals($resolved, $protectedPath, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to write protected formal result file: $resolved"
        }
    }
}

function Write-ProtectedHashes([string]$Label) {
    Write-Host $Label
    $protected = @(
        "results/final_experiment_results.csv",
        "results/final_analysis_summary.txt",
        "results/final_analysis_summary.csv"
    )
    foreach ($item in $protected) {
        $path = Resolve-ProjectPath $item
        if (Test-Path -LiteralPath $path) {
            $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $path
            Write-Host ("{0} {1}" -f (Split-Path $path -Leaf), $hash.Hash)
        } else {
            Write-Host ("{0} MISSING" -f $item)
        }
    }
}

function Invoke-NativeCommand([string]$Label, [string[]]$Command) {
    Write-Host $Label
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
    Invoke-NativeCommand "compile SERIAL" @(
        "gcc", "-std=c11", "-Wall", "-Wextra", "-O2",
        $SerialSource, "-lm", "-o", $SerialExe
    ) | Out-Null
}

function Compile-MpiProgram([string]$Name, [string]$Source, [string]$ExePath) {
    if (Get-Command mpicc -ErrorAction SilentlyContinue) {
        Invoke-NativeCommand "compile $Name with mpicc" @(
            "mpicc", "-std=c11", "-Wall", "-Wextra", "-O2",
            $Source, "-lm", "-o", $ExePath
        ) | Out-Null
    } elseif ((Get-Command gcc -ErrorAction SilentlyContinue) -and $env:MSMPI_INC -and $env:MSMPI_LIB64) {
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

function Parse-Seeds([string]$SeedText) {
    $values = @()
    foreach ($text in ($SeedText -split ",")) {
        $trimmed = $text.Trim()
        if ($trimmed.Length -eq 0) {
            continue
        }
        $values += [int]$trimmed
    }
    if ($values.Count -eq 0) {
        throw "No seeds provided"
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

function Append-UnifiedResult([hashtable]$Case, [int]$Seed, [string]$TempPath) {
    $row = Read-LastResultRow $TempPath
    if ($row.algorithm -ne $Case.Algorithm) {
        throw "Expected algorithm $($Case.Algorithm) but got $($row.algorithm) in $TempPath"
    }
    if ([int]$row.nproc -ne [int]$Case.NProc) {
        throw "Expected nproc $($Case.NProc) but got $($row.nproc) in $TempPath"
    }
    if ([int]$row.maxGen -ne [int]$MaxGen) {
        throw "Expected maxGen $MaxGen but got $($row.maxGen) in $TempPath"
    }
    if ([int]$row.base_seed -ne $Seed) {
        throw "Expected seed $Seed but got $($row.base_seed) in $TempPath"
    }

    $globalBest = Format-NumberText $row.global_best "0.######"
    $elapsedSec = Format-NumberText $row.elapsed_sec "0.######"
    $line = "{0},{1},{2},{3},{4},{5},{6},{7},{8}" -f `
        $Case.Algorithm, $Case.NProc, $MaxGen, $Case.MigrationInterval, `
        $Case.LocalToGlobalRatio, $Case.NumGroups, $Seed, $globalBest, $elapsedSec
    Add-Content -LiteralPath $ResultsPath -Encoding UTF8 -Value $line

    Write-Host ("[DONE] global_best={0} elapsed_sec={1}" -f $globalBest, $elapsedSec)
}

function Invoke-ExperimentCase([hashtable]$Case, [int]$Seed) {
    $tempName = "tmp_reproduction_{0}_n{1}_g{2}_seed{3}.csv" -f `
        $Case.Algorithm.ToLowerInvariant(), $Case.NProc, $Case.NumGroups, $Seed
    $tempPath = Join-Path $TempDir $tempName
    if (Test-Path -LiteralPath $tempPath) {
        Remove-Item -LiteralPath $tempPath -Force
    }

    Write-Host ("[RUN] {0} n={1} groups={2} seed={3}" -f `
        $Case.Algorithm, $Case.NProc, $Case.NumGroups, $Seed)

    if ($Case.Algorithm -eq "SERIAL") {
        Invoke-NativeCommand "execute SERIAL seed=$Seed" @(
            $SerialExe, $InputPath, "$MaxGen", "$Seed", $tempPath
        ) | Out-Null
    } elseif ($Case.Algorithm -eq "DEA") {
        Invoke-NativeCommand "execute DEA n=$($Case.NProc) seed=$Seed" @(
            "mpiexec", "-n", "$($Case.NProc)", $DeaExe, $InputPath,
            "$MaxGen", "$($Case.MigrationInterval)", "$Seed", $tempPath
        ) | Out-Null
    } elseif ($Case.Algorithm -eq "HDEA") {
        Invoke-NativeCommand "execute HDEA n=$($Case.NProc) groups=$($Case.NumGroups) seed=$Seed" @(
            "mpiexec", "-n", "$($Case.NProc)", $HdeaExe, $InputPath,
            "$MaxGen", "$($Case.MigrationInterval)", "$($Case.LocalToGlobalRatio)",
            "$($Case.NumGroups)", "$Seed", $tempPath
        ) | Out-Null
    } elseif ($Case.Algorithm -eq "MOVING_HDEA") {
        Invoke-NativeCommand "execute MOVING_HDEA n=$($Case.NProc) groups=$($Case.NumGroups) seed=$Seed" @(
            "mpiexec", "-n", "$($Case.NProc)", $MovingHdeaExe, $InputPath,
            "$MaxGen", "$($Case.MigrationInterval)", "$($Case.LocalToGlobalRatio)",
            "$($Case.NumGroups)", "$Seed", $tempPath
        ) | Out-Null
    } else {
        throw "Unknown algorithm: $($Case.Algorithm)"
    }

    Append-UnifiedResult $Case $Seed $tempPath
    Remove-Item -LiteralPath $tempPath -Force
}

function Validate-ReproductionResults {
    $rows = @(Import-Csv -LiteralPath $ResultsPath)
    $expectedRows = $cases.Count * $seedList.Count
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
        $groupRows = @(
            $rows | Where-Object {
                $_.algorithm -eq $case.Algorithm -and
                [int]$_.nproc -eq [int]$case.NProc -and
                [int]$_.maxGen -eq [int]$MaxGen -and
                [int]$_.migration_interval -eq [int]$case.MigrationInterval -and
                [int]$_.local_to_global_ratio -eq [int]$case.LocalToGlobalRatio -and
                [int]$_.num_groups -eq [int]$case.NumGroups
            }
        )
        if ($groupRows.Count -ne $seedList.Count) {
            throw "Expected $($seedList.Count) rows for $($case.Algorithm) n=$($case.NProc) groups=$($case.NumGroups), got $($groupRows.Count)"
        }
        foreach ($seed in $seedList) {
            $seedRows = @($groupRows | Where-Object { [int]$_.base_seed -eq [int]$seed })
            if ($seedRows.Count -ne 1) {
                throw "Expected one seed=$seed row for $($case.Algorithm) n=$($case.NProc), got $($seedRows.Count)"
            }
        }
    }

    Write-Host "validated $($rows.Count) result rows in $ResultsPath"
}

$ProjectRoot = Get-ProjectRoot
$InputPath = Resolve-ProjectPath $InputFile
$ResultsPath = Resolve-ProjectPath $ResultsFile
Assert-NotProtectedResultPath $ResultsFile

$ResultsDir = Split-Path -Parent $ResultsPath
$TempDir = Join-Path $ResultsDir "_tmp_reproduction_extension"
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

$seedList = Parse-Seeds $Seeds

$cases = @(
    @{ Algorithm = "SERIAL"; NProc = 1; MigrationInterval = 0; LocalToGlobalRatio = 0; NumGroups = 0 },
    @{ Algorithm = "DEA"; NProc = 4; MigrationInterval = $MigrationInterval; LocalToGlobalRatio = 0; NumGroups = 0 },
    @{ Algorithm = "HDEA"; NProc = 4; MigrationInterval = $MigrationInterval; LocalToGlobalRatio = $LocalToGlobalRatio; NumGroups = 2 },
    @{ Algorithm = "MOVING_HDEA"; NProc = 4; MigrationInterval = $MigrationInterval; LocalToGlobalRatio = $LocalToGlobalRatio; NumGroups = 2 },
    @{ Algorithm = "DEA"; NProc = 9; MigrationInterval = $MigrationInterval; LocalToGlobalRatio = 0; NumGroups = 0 },
    @{ Algorithm = "HDEA"; NProc = 9; MigrationInterval = $MigrationInterval; LocalToGlobalRatio = $LocalToGlobalRatio; NumGroups = 3 },
    @{ Algorithm = "MOVING_HDEA"; NProc = 9; MigrationInterval = $MigrationInterval; LocalToGlobalRatio = $LocalToGlobalRatio; NumGroups = 3 }
)

Write-ProtectedHashes "[HASH BEFORE] protected formal results"

Compile-Serial
Compile-MpiProgram "DEA" $DeaSource $DeaExe
Compile-MpiProgram "HDEA" $HdeaSource $HdeaExe
Compile-MpiProgram "MOVING_HDEA" $MovingHdeaSource $MovingHdeaExe

if (Test-Path -LiteralPath $ResultsPath) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    # Default backup shape: results/reproduction_extension_results.csv.bak-YYYYMMdd-HHmmss
    $backup = "$ResultsPath.bak-$timestamp"
    Move-Item -LiteralPath $ResultsPath -Destination $backup
    Write-Host "backed up existing reproduction_extension_results.csv to $backup"
}

Set-Content -LiteralPath $ResultsPath -Encoding UTF8 -Value `
    "algorithm,nproc,maxGen,migration_interval,local_to_global_ratio,num_groups,base_seed,global_best,elapsed_sec"

Write-Host "reproduction extension settings: input=$InputPath maxGen=$MaxGen migration_interval=$MigrationInterval local_to_global_ratio=$LocalToGlobalRatio seeds=$($seedList -join ',') results=$ResultsPath"

foreach ($case in $cases) {
    foreach ($seed in $seedList) {
        Invoke-ExperimentCase $case $seed
    }
}

Validate-ReproductionResults
Remove-Item -LiteralPath $TempDir -Recurse -Force
Write-ProtectedHashes "[HASH AFTER] protected formal results"
Write-Host "reproduction extension experiment completed"
