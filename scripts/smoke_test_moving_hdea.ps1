param(
    [string]$Source = "src/tsp_mpi_moving_hdea.c",
    [string]$InputFile = "data/pcb442.tsp",
    [int]$MaxGen = 100,
    [int]$LocalMigrationInterval = 20,
    [int]$LocalToGlobalRatio = 2,
    [int]$BaseSeed = 12345,
    [string]$CsvFile = "results/moving_hdea_result.csv"
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

function Invoke-MpiRun([int]$NProc, [int]$Groups) {
    Write-Host "run: mpiexec -n $NProc $ExePath $InputPath $MaxGen $LocalMigrationInterval $LocalToGlobalRatio $Groups $BaseSeed $CsvPath"
    $output = & mpiexec -n $NProc $ExePath $InputPath $MaxGen $LocalMigrationInterval $LocalToGlobalRatio $Groups $BaseSeed $CsvPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        $output | ForEach-Object { Write-Host $_ }
        throw "mpiexec -n $NProc failed with exit code $LASTEXITCODE"
    }

    $text = $output -join "`n"
    $subpopsPerGroup = [int]($NProc / $Groups)
    $required = @(
        "MPI size: $NProc",
        "num_groups=$Groups",
        "subpops_per_group=$subpopsPerGroup",
        "maxGen=$MaxGen",
        "local_migration_interval=$LocalMigrationInterval",
        "local_to_global_ratio=$LocalToGlobalRatio",
        "initial group_members",
        "initial logical_group",
        "logical_pos",
        "initial best",
        "local migration plan generation",
        "local migration generation",
        "global moving colony generation",
        "moving_position",
        "before moving colony",
        "after moving colony",
        "local migration generation 60",
        "final local best",
        "final global best",
        "elapsed time"
    )

    foreach ($needle in $required) {
        if ($text -notmatch [regex]::Escape($needle)) {
            $output | ForEach-Object { Write-Host $_ }
            throw "mpiexec -n $NProc missing expected output marker: $needle"
        }
    }

    if ($NProc -eq 4 -and $text -notmatch "after moving colony: group 0=\[2,1\] group 1=\[0,3\]") {
        $output | ForEach-Object { Write-Host $_ }
        throw "n=4 moving colony ring rotation did not produce expected group_members map"
    }

    if ($NProc -eq 4 -and $text -notmatch "local migration plan generation 20: group 0=\[0->1,1->0\] group 1=\[2->3,3->2\]") {
        $output | ForEach-Object { Write-Host $_ }
        throw "n=4 initial local migration plan did not use the initial logical groups"
    }

    if ($NProc -eq 4 -and $text -notmatch "local migration plan generation 60: group 0=\[2->1,1->2\] group 1=\[0->3,3->0\]") {
        $output | ForEach-Object { Write-Host $_ }
        throw "n=4 local migration after moving colony did not use the updated logical groups"
    }

    if ($NProc -eq 6 -and $text -notmatch "after moving colony: group 0=\[4,1\] group 1=\[0,3\] group 2=\[2,5\]") {
        $output | ForEach-Object { Write-Host $_ }
        throw "n=6 moving colony ring rotation did not produce expected group_members map"
    }

    $output | Select-Object -First 12 | ForEach-Object { Write-Host $_ }
    Write-Host "..."
    $output | Select-Object -Last 14 | ForEach-Object { Write-Host $_ }
}

$ProjectRoot = Get-ProjectRoot
$SourcePath = Resolve-ProjectPath $Source
$InputPath = Resolve-ProjectPath $InputFile
$CsvPath = Resolve-ProjectPath $CsvFile
$BinDir = Join-Path $ProjectRoot "bin"
$ExePath = Join-Path $BinDir "tsp_mpi_moving_hdea.exe"

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

if (Test-Path -LiteralPath $CsvPath) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = "$CsvPath.bak-$timestamp"
    Move-Item -LiteralPath $CsvPath -Destination $backup
    Write-Host "backed up existing MOVING_HDEA result CSV to $backup"
}

Invoke-MpiRun 4 2
Invoke-MpiRun 6 3

Write-Host "run invalid parameter test: mpiexec -n 4 ... num_groups=3"
$oldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $badOutput = & mpiexec -n 4 $ExePath $InputPath $MaxGen $LocalMigrationInterval $LocalToGlobalRatio 3 $BaseSeed $CsvPath 2>&1
    $badExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $oldErrorActionPreference
}

if ($badExitCode -eq 0) {
    $badOutput | ForEach-Object { Write-Host $_ }
    throw "invalid parameter test unexpectedly succeeded"
}

$badText = $badOutput -join "`n"
if ($badText -notmatch "nproc must be divisible by num_groups") {
    $badOutput | ForEach-Object { Write-Host $_ }
    throw "invalid parameter test did not report expected error"
}
$badOutput | Select-Object -First 8 | ForEach-Object { Write-Host $_ }

if (-not (Test-Path -LiteralPath $CsvPath)) {
    throw "MOVING_HDEA result CSV was not created: $CsvPath"
}

$rows = @(Import-Csv -LiteralPath $CsvPath)
if ($rows.Count -ne 2) {
    throw "Expected 2 MOVING_HDEA result rows, got $($rows.Count)"
}

foreach ($row in $rows) {
    if ($row.algorithm -ne "MOVING_HDEA") {
        throw "Unexpected algorithm in CSV: $($row.algorithm)"
    }
}

Write-Host "MOVING_HDEA CSV rows:"
Get-Content -LiteralPath $CsvPath | ForEach-Object { Write-Host $_ }
Write-Host "MOVING_HDEA smoke test passed"
