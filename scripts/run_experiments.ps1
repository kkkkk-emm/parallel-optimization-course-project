param(
    [string]$InputFile = "data/pcb442.tsp",
    [int]$MaxGen = 1000,
    [int]$MigrationInterval = 100,
    [string]$Seeds = "12345,22345,32345,42345,52345,62345,72345,82345,92345,102345",
    [string]$ResultsFile = "results/experiment_results.csv",
    [switch]$IncludeDea1,
    [switch]$KeepExistingResults
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

function Compile-Serial {
    Write-Host "compile serial: gcc -std=c11 -Wall -Wextra -O2 $SerialSource -lm -o $SerialExe"
    & gcc -std=c11 -Wall -Wextra -O2 $SerialSource -lm -o $SerialExe
    if ($LASTEXITCODE -ne 0) {
        throw "serial compile failed with exit code $LASTEXITCODE"
    }
}

function Compile-Dea {
    if (Get-Command mpicc -ErrorAction SilentlyContinue) {
        Write-Host "compile DEA: mpicc -std=c11 -Wall -Wextra -O2 $DeaSource -lm -o $DeaExe"
        & mpicc -std=c11 -Wall -Wextra -O2 $DeaSource -lm -o $DeaExe
    } elseif ((Get-Command gcc -ErrorAction SilentlyContinue) -and $env:MSMPI_INC -and $env:MSMPI_LIB64) {
        $msmpiInc = $env:MSMPI_INC.TrimEnd('\')
        $msmpiLibDir = $env:MSMPI_LIB64.TrimEnd('\')
        Write-Host "compile DEA: gcc + MS-MPI SDK"
        & gcc -std=c11 -Wall -Wextra -O2 "-I$msmpiInc" $DeaSource "-L$msmpiLibDir" -lmsmpi -lm -o $DeaExe
    } else {
        throw "No usable MPI C compiler found. Need mpicc, or gcc with MSMPI_INC/MSMPI_LIB64."
    }

    if ($LASTEXITCODE -ne 0) {
        throw "DEA compile failed with exit code $LASTEXITCODE"
    }
}

function Invoke-CheckedCommand([string]$Label, [string[]]$Command) {
    Write-Host $Label
    & $Command[0] @($Command[1..($Command.Length - 1)])
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

$ProjectRoot = Get-ProjectRoot
$InputPath = Resolve-ProjectPath $InputFile
$ResultsPath = Resolve-ProjectPath $ResultsFile
$SerialSource = Join-Path $ProjectRoot "src/tsp_serial_exp.c"
$DeaSource = Join-Path $ProjectRoot "src/tsp_mpi_dea.c"
$BinDir = Join-Path $ProjectRoot "bin"
$ResultsDir = Split-Path -Parent $ResultsPath
$SerialExe = Join-Path $BinDir "tsp_serial_exp.exe"
$DeaExe = Join-Path $BinDir "tsp_mpi_dea.exe"

New-Item -ItemType Directory -Force -Path $BinDir, $ResultsDir | Out-Null

if (-not (Test-Path -LiteralPath $InputPath)) {
    throw "Input TSP file not found: $InputPath"
}

if (-not (Test-Path -LiteralPath $SerialSource)) {
    throw "Serial source not found: $SerialSource"
}

if (-not (Test-Path -LiteralPath $DeaSource)) {
    throw "DEA source not found: $DeaSource"
}

if (-not (Get-Command gcc -ErrorAction SilentlyContinue)) {
    throw "gcc not found"
}

if (-not (Get-Command mpiexec -ErrorAction SilentlyContinue)) {
    throw "mpiexec not found"
}

$seedList = @()
foreach ($seedText in ($Seeds -split ",")) {
    $trimmed = $seedText.Trim()
    if ($trimmed.Length -eq 0) {
        continue
    }
    $seedList += [int]$trimmed
}

if ($seedList.Count -eq 0) {
    throw "No seeds provided"
}

Compile-Serial
Compile-Dea

if ((Test-Path -LiteralPath $ResultsPath) -and -not $KeepExistingResults) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = "$ResultsPath.bak-$timestamp"
    Move-Item -LiteralPath $ResultsPath -Destination $backup
    Write-Host "backed up existing results to $backup"
}

Write-Host "experiment settings: input=$InputPath maxGen=$MaxGen migration_interval=$MigrationInterval seeds=$($seedList -join ',') results=$ResultsPath"

foreach ($seed in $seedList) {
    Invoke-CheckedCommand "run SERIAL seed=$seed" @($SerialExe, $InputPath, "$MaxGen", "$seed", $ResultsPath)
}

if ($IncludeDea1) {
    foreach ($seed in $seedList) {
        Invoke-CheckedCommand "run DEA n=1 seed=$seed" @("mpiexec", "-n", "1", $DeaExe, $InputPath, "$MaxGen", "$MigrationInterval", "$seed", $ResultsPath)
    }
}

foreach ($seed in $seedList) {
    Invoke-CheckedCommand "run DEA n=2 seed=$seed" @("mpiexec", "-n", "2", $DeaExe, $InputPath, "$MaxGen", "$MigrationInterval", "$seed", $ResultsPath)
}

foreach ($seed in $seedList) {
    Invoke-CheckedCommand "run DEA n=4 seed=$seed" @("mpiexec", "-n", "4", $DeaExe, $InputPath, "$MaxGen", "$MigrationInterval", "$seed", $ResultsPath)
}

$rows = Import-Csv -LiteralPath $ResultsPath
Write-Host "wrote $($rows.Count) result rows to $ResultsPath"
$rows | Group-Object algorithm,nproc | ForEach-Object {
    Write-Host ("group {0}: {1} rows" -f $_.Name, $_.Count)
}
