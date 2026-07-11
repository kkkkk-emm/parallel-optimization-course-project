param(
    [string]$InputFile = "data/pcb442.tsp",
    [int]$MaxGen = 1000,
    [int]$MigrationInterval = 100,
    [string]$Seeds = "12345,22345,32345,42345,52345,62345,72345,82345,92345,102345",
    [string]$ResultsFile = "results/equal_budget_results.csv"
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

function Assert-NotProtectedResultPath([string]$Path) {
    $resolved = [System.IO.Path]::GetFullPath($Path)
    $protected = @(
        "results/final_experiment_results.csv",
        "results/final_analysis_summary.csv",
        "results/final_analysis_summary.txt"
    )
    foreach ($item in $protected) {
        $protectedPath = [System.IO.Path]::GetFullPath((Resolve-ProjectPath $item))
        if ([string]::Equals($resolved, $protectedPath, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to write protected formal result file: $resolved"
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
        if ($trimmed.Length -gt 0) {
            $values += [int]$trimmed
        }
    }
    if ($values.Count -eq 0) {
        throw "No seeds provided"
    }
    return $values
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

function Format-NumberText([string]$Text, [string]$Format) {
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    $value = [double]::Parse($Text, $culture)
    return $value.ToString($Format, $culture)
}

function Append-EqualBudgetResult([hashtable]$Case, [int]$Seed, [string]$TempPath) {
    $row = Read-LastResultRow $TempPath
    if ($row.algorithm -ne $Case.Algorithm) {
        throw "Expected algorithm $($Case.Algorithm) but got $($row.algorithm) in $TempPath"
    }
    if ([int]$row.nproc -ne [int]$Case.NProc) {
        throw "Expected nproc $($Case.NProc) but got $($row.nproc) in $TempPath"
    }
    $globalBest = Format-NumberText $row.global_best "0.######"
    $elapsedSec = Format-NumberText $row.elapsed_sec "0.######"
    $line = "{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10}" -f `
        $Case.Algorithm, $Case.NProc, $MaxGen, $Case.MigrationInterval, 0, 0, `
        $Case.LocalColonySize, 100, $Seed, $globalBest, $elapsedSec
    Add-Content -LiteralPath $ResultsPath -Encoding UTF8 -Value $line
    Write-Host ("[DONE] global_best={0} elapsed_sec={1}" -f $globalBest, $elapsedSec)
}

function Invoke-ExperimentCase([hashtable]$Case, [int]$Seed) {
    $tempName = "tmp_equal_budget_{0}_n{1}_seed{2}.csv" -f $Case.Algorithm.ToLowerInvariant(), $Case.NProc, $Seed
    $tempPath = Join-Path $TempDir $tempName
    if (Test-Path -LiteralPath $tempPath) {
        Remove-Item -LiteralPath $tempPath -Force
    }
    Write-Host ("[RUN] {0} n={1} local_colony={2} seed={3}" -f $Case.Algorithm, $Case.NProc, $Case.LocalColonySize, $Seed)
    if ($Case.Algorithm -eq "SERIAL") {
        Invoke-NativeCommand "execute SERIAL seed=$Seed" @(
            $SerialExe, $InputPath, "$MaxGen", "$Seed", $tempPath, "$($Case.LocalColonySize)"
        ) | Out-Null
    } elseif ($Case.Algorithm -eq "DEA") {
        Invoke-NativeCommand "execute DEA n=$($Case.NProc) seed=$Seed" @(
            "mpiexec", "-n", "$($Case.NProc)", $DeaExe, $InputPath,
            "$MaxGen", "$($Case.MigrationInterval)", "$Seed", $tempPath, "$($Case.LocalColonySize)"
        ) | Out-Null
    } else {
        throw "Unknown algorithm: $($Case.Algorithm)"
    }
    Append-EqualBudgetResult $Case $Seed $tempPath
    Remove-Item -LiteralPath $tempPath -Force
}

$ProjectRoot = Get-ProjectRoot
$InputPath = Resolve-ProjectPath $InputFile
$ResultsPath = Resolve-ProjectPath $ResultsFile
Assert-NotProtectedResultPath $ResultsPath

$ResultsDir = Split-Path -Parent $ResultsPath
$TempDir = Join-Path $ResultsDir "_tmp_equal_budget"
$BinDir = Join-Path $ProjectRoot "bin"
$SerialSource = Join-Path $ProjectRoot "src/tsp_serial_exp.c"
$DeaSource = Join-Path $ProjectRoot "src/tsp_mpi_dea.c"
$SerialExe = Join-Path $BinDir "tsp_serial_exp.exe"
$DeaExe = Join-Path $BinDir "tsp_mpi_dea.exe"

New-Item -ItemType Directory -Force -Path $BinDir, $ResultsDir, $TempDir | Out-Null

foreach ($path in @($InputPath, $SerialSource, $DeaSource)) {
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
    @{ Algorithm = "SERIAL"; NProc = 1; MigrationInterval = 0; LocalColonySize = 100 },
    @{ Algorithm = "DEA"; NProc = 2; MigrationInterval = $MigrationInterval; LocalColonySize = 50 },
    @{ Algorithm = "DEA"; NProc = 4; MigrationInterval = $MigrationInterval; LocalColonySize = 25 }
)

Compile-Serial
Compile-MpiProgram "DEA" $DeaSource $DeaExe

if (Test-Path -LiteralPath $ResultsPath) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = "$ResultsPath.bak-$timestamp"
    Move-Item -LiteralPath $ResultsPath -Destination $backup
    Write-Host "backed up existing equal-budget results to $backup"
}

Set-Content -LiteralPath $ResultsPath -Encoding UTF8 -Value `
    "algorithm,nproc,maxGen,migration_interval,local_to_global_ratio,num_groups,local_colony_size,total_colony_size,base_seed,global_best,elapsed_sec"

Write-Host "equal-budget settings: input=$InputPath maxGen=$MaxGen total_colony_size=100 migration_interval=$MigrationInterval seeds=$($seedList -join ',') results=$ResultsPath"

foreach ($case in $cases) {
    foreach ($seed in $seedList) {
        Invoke-ExperimentCase $case $seed
    }
}

$rows = @(Import-Csv -LiteralPath $ResultsPath)
$expectedRows = $cases.Count * $seedList.Count
if ($rows.Count -ne $expectedRows) {
    throw "Expected $expectedRows result rows, got $($rows.Count)"
}

Remove-Item -LiteralPath $TempDir -Recurse -Force
Write-Host "wrote $($rows.Count) result rows to $ResultsPath"
