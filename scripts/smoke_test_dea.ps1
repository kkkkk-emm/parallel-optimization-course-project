param(
    [string]$Source = "src/tsp_mpi_dea.c",
    [string]$InputFile = "data/pcb442.tsp",
    [int]$MaxGen = 100,
    [int]$MigrationInterval = 20,
    [int]$BaseSeed = 12345,
    [string]$CsvFile = "results/dea_result.csv"
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

function Get-LineCount([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        return (Get-Content -LiteralPath $Path).Count
    }
    return 0
}

$ProjectRoot = Get-ProjectRoot
$SourcePath = Resolve-ProjectPath $Source
$InputPath = Resolve-ProjectPath $InputFile
$CsvPath = Resolve-ProjectPath $CsvFile
$BinDir = Join-Path $ProjectRoot "bin"
$ExePath = Join-Path $BinDir "tsp_mpi_dea.exe"

New-Item -ItemType Directory -Force -Path $BinDir, (Split-Path -Parent $CsvPath) | Out-Null

if (-not (Test-Path -LiteralPath $SourcePath)) {
    throw "Missing source file: $SourcePath"
}

if (-not (Test-Path -LiteralPath $InputPath)) {
    throw "Missing input file: $InputPath"
}

if (-not (Get-Command mpiexec -ErrorAction SilentlyContinue)) {
    throw "mpiexec not found"
}

if (Test-Path -LiteralPath $ExePath) {
    Remove-Item -LiteralPath $ExePath -Force
}

if (Get-Command mpicc -ErrorAction SilentlyContinue) {
    Write-Host "compile: mpicc"
    & mpicc -std=c11 -Wall -Wextra -O2 $SourcePath -lm -o $ExePath
} elseif ((Get-Command gcc -ErrorAction SilentlyContinue) -and $env:MSMPI_INC -and $env:MSMPI_LIB64) {
    Write-Host "compile: gcc + MS-MPI SDK"
    $msmpiInc = $env:MSMPI_INC.TrimEnd('\')
    $msmpiLibDir = $env:MSMPI_LIB64.TrimEnd('\')
    & gcc -std=c11 -Wall -Wextra -O2 "-I$msmpiInc" $SourcePath "-L$msmpiLibDir" -lmsmpi -lm -o $ExePath
} else {
    throw "No usable MPI C compiler found. Need mpicc, or gcc with MSMPI_INC/MSMPI_LIB64."
}

if ($LASTEXITCODE -ne 0) {
    throw "MPI compile failed with exit code $LASTEXITCODE"
}

$before = Get-LineCount $CsvPath

foreach ($n in @(1, 2, 4)) {
    Write-Host "run: mpiexec -n $n $ExePath $InputPath $MaxGen $MigrationInterval $BaseSeed $CsvPath"
    $output = & mpiexec -n $n $ExePath $InputPath $MaxGen $MigrationInterval $BaseSeed $CsvPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        $output | ForEach-Object { Write-Host $_ }
        throw "mpiexec -n $n failed with exit code $LASTEXITCODE"
    }

    $text = $output -join "`n"
    $required = @(
        "MPI size: $n",
        "read 442 cities",
        "maxGen=$MaxGen",
        "migration_interval=$MigrationInterval",
        "initial best",
        "final local best",
        "final global best",
        "elapsed time"
    )

    foreach ($needle in $required) {
        if ($text -notmatch [regex]::Escape($needle)) {
            $output | ForEach-Object { Write-Host $_ }
            throw "mpiexec -n $n missing expected output marker: $needle"
        }
    }

    $output | Select-Object -First 8 | ForEach-Object { Write-Host $_ }
    Write-Host "..."
    $output | Select-Object -Last 8 | ForEach-Object { Write-Host $_ }
}

$after = Get-LineCount $CsvPath
$expectedGrowth = if ($before -eq 0) { 4 } else { 3 }
if (($after - $before) -ne $expectedGrowth) {
    throw "CSV line count grew by $($after - $before), expected $expectedGrowth"
}

Write-Host "CSV appended rows:"
Get-Content -LiteralPath $CsvPath | Select-Object -Last 3 | ForEach-Object { Write-Host $_ }
Write-Host "DEA smoke test passed"
