param(
    [string]$InputFile = "data/pcb442.tsp",
    [string]$Seeds = "12345,22345,32345",
    [double]$TimeBudgetSec = 1.0,
    [int]$IterationBudget = 80,
    [string]$ResultsFile = "results/scratch_algorithm_trials.csv",
    [string]$SummaryFile = "results/scratch_algorithm_trials_summary.txt"
)

$ErrorActionPreference = "Stop"

function Get-ProjectRoot {
    $scriptDir = $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($scriptDir)) {
        $scriptDir = (Get-Location).Path
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
            throw "Refusing to write protected Version A result file: $resolved"
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
    Invoke-NativeCommand "compile scratch serial" @(
        "gcc", "-std=c11", "-Wall", "-Wextra", "-O2",
        $SerialSource, "-lm", "-o", $SerialExe
    ) | Out-Null
}

function Compile-Mpi {
    if (Get-Command mpicc -ErrorAction SilentlyContinue) {
        Invoke-NativeCommand "compile scratch MPI with mpicc" @(
            "mpicc", "-std=c11", "-Wall", "-Wextra", "-O2",
            $MpiSource, "-lm", "-o", $MpiExe
        ) | Out-Null
    } elseif ((Get-Command gcc -ErrorAction SilentlyContinue) -and $env:MSMPI_INC -and $env:MSMPI_LIB64) {
        $msmpiInc = $env:MSMPI_INC.TrimEnd('\')
        $msmpiLibDir = $env:MSMPI_LIB64.TrimEnd('\')
        Invoke-NativeCommand "compile scratch MPI with gcc + MS-MPI SDK" @(
            "gcc", "-std=c11", "-Wall", "-Wextra", "-O2",
            "-I$msmpiInc", $MpiSource, "-L$msmpiLibDir", "-lmsmpi", "-lm", "-o", $MpiExe
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

function Backup-Existing([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        Move-Item -LiteralPath $Path -Destination "$Path.bak-$timestamp"
    }
}

$ProjectRoot = Get-ProjectRoot
$InputPath = Resolve-ProjectPath $InputFile
$ResultsPath = Resolve-ProjectPath $ResultsFile
$SummaryPath = Resolve-ProjectPath $SummaryFile
$SummaryCsvPath = [System.IO.Path]::GetFullPath((Join-Path ([System.IO.Path]::GetTempPath()) "scratch_algorithm_trials_summary.csv"))
$BinDir = Resolve-ProjectPath "bin"
$SerialSource = Resolve-ProjectPath "src_scratch/tsp_scratch_serial.c"
$MpiSource = Resolve-ProjectPath "src_scratch/tsp_scratch_mpi.c"
$SerialExe = Resolve-ProjectPath "bin/tsp_scratch_serial.exe"
$MpiExe = Resolve-ProjectPath "bin/tsp_scratch_mpi.exe"

Assert-NotProtectedResultPath $ResultsFile
Assert-NotProtectedResultPath $SummaryFile
Assert-NotProtectedResultPath $SummaryCsvPath

foreach ($path in @($InputPath, $SerialSource, $MpiSource)) {
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

New-Item -ItemType Directory -Force -Path $BinDir,(Split-Path -Parent $ResultsPath) | Out-Null
Backup-Existing $ResultsPath
Backup-Existing $SummaryPath
Backup-Existing $SummaryCsvPath

Compile-Serial
Compile-Mpi
Invoke-NativeCommand "scratch smoke test" @($SerialExe, "--smoke") | Out-Null

$seedList = Parse-Seeds $Seeds
$algorithms = @("nn2opt", "greedy2opt", "ils2opt")

foreach ($algorithm in $algorithms) {
    foreach ($seed in $seedList) {
        Invoke-NativeCommand "trial serial $algorithm seed=$seed" @(
            $SerialExe, $InputPath, $algorithm, "$seed", "$TimeBudgetSec", "$IterationBudget", $ResultsPath
        ) | Out-Null
        Invoke-NativeCommand "trial mpi n=4 $algorithm seed=$seed" @(
            "mpiexec", "-n", "4", $MpiExe, $InputPath, $algorithm, "$seed",
            "$TimeBudgetSec", "$IterationBudget", $ResultsPath
        ) | Out-Null
    }
}

python (Resolve-ProjectPath "scripts/analyze_scratch_results.py") $ResultsPath $SummaryCsvPath $SummaryPath
if (Test-Path -LiteralPath $SummaryCsvPath) {
    Remove-Item -LiteralPath $SummaryCsvPath -Force
}
Write-Host "wrote scratch trial results to $ResultsPath"
