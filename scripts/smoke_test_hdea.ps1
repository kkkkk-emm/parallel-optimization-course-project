param(
    [string]$Source = "src/tsp_mpi_hdea.c",
    [string]$InputFile = "data/pcb442.tsp",
    [int]$MaxGen = 100,
    [int]$LocalMigrationInterval = 20,
    [int]$LocalToGlobalRatio = 2,
    [int]$BaseSeed = 12345,
    [string]$CsvFile = "results/hdea_result.csv"
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

$ProjectRoot = Get-ProjectRoot
$SourcePath = Resolve-ProjectPath $Source
$InputPath = Resolve-ProjectPath $InputFile
$CsvPath = Resolve-ProjectPath $CsvFile
$BinDir = Join-Path $ProjectRoot "bin"
$ExePath = Join-Path $BinDir "tsp_mpi_hdea.exe"

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
    Write-Host "backed up existing HDEA result CSV to $backup"
}

foreach ($case in @(
    @{ N = 4; Groups = 2 },
    @{ N = 6; Groups = 3 }
)) {
    $n = $case.N
    $groups = $case.Groups
    Write-Host "run: mpiexec -n $n $ExePath $InputPath $MaxGen $LocalMigrationInterval $LocalToGlobalRatio $groups $BaseSeed $CsvPath"
    $output = & mpiexec -n $n $ExePath $InputPath $MaxGen $LocalMigrationInterval $LocalToGlobalRatio $groups $BaseSeed $CsvPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        $output | ForEach-Object { Write-Host $_ }
        throw "mpiexec -n $n failed with exit code $LASTEXITCODE"
    }

    $text = $output -join "`n"
    $subpopsPerGroup = [int]($n / $groups)
    $required = @(
        "MPI size: $n",
        "num_groups=$groups",
        "subpops_per_group=$subpopsPerGroup",
        "maxGen=$MaxGen",
        "local_migration_interval=$LocalMigrationInterval",
        "local_to_global_ratio=$LocalToGlobalRatio",
        "group_id",
        "local_id",
        "initial best",
        "local migration generation",
        "global migration generation",
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

    $output | Select-Object -First 10 | ForEach-Object { Write-Host $_ }
    Write-Host "..."
    $output | Select-Object -Last 10 | ForEach-Object { Write-Host $_ }
}

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
    throw "HDEA result CSV was not created: $CsvPath"
}

$rows = Import-Csv -LiteralPath $CsvPath
if ($rows.Count -ne 2) {
    throw "Expected 2 HDEA result rows, got $($rows.Count)"
}

foreach ($row in $rows) {
    if ($row.algorithm -ne "HDEA") {
        throw "Unexpected algorithm in CSV: $($row.algorithm)"
    }
}

Write-Host "HDEA CSV rows:"
Get-Content -LiteralPath $CsvPath | ForEach-Object { Write-Host $_ }
Write-Host "HDEA smoke test passed"
