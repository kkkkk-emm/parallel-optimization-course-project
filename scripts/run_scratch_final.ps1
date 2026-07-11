param(
    [string]$InputFile = "data/pcb442.tsp",
    [string]$Algorithm = "ils2opt",
    [string]$Seeds = "12345,22345,32345,42345,52345,62345,72345,82345,92345,102345",
    [double]$TimeBudgetSec = 2.0,
    [int]$IterationBudget = 180,
    [string]$ResultsFile = "results/scratch_experiment_results.csv",
    [string]$SummaryCsv = "results/scratch_analysis_summary.csv",
    [string]$SummaryTxt = "results/scratch_analysis_summary.txt"
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

function Get-AlgorithmLabel([string]$Name) {
    if ($Name -eq "nn2opt") { return "SCRATCH_NN_2OPT" }
    if ($Name -eq "greedy2opt") { return "SCRATCH_GREEDY_2OPT" }
    if ($Name -eq "ils2opt") { return "SCRATCH_ILS_2OPT" }
    return $Name
}

$ProjectRoot = Get-ProjectRoot
$InputPath = Resolve-ProjectPath $InputFile
$ResultsPath = Resolve-ProjectPath $ResultsFile
$SummaryCsvPath = Resolve-ProjectPath $SummaryCsv
$SummaryTxtPath = Resolve-ProjectPath $SummaryTxt
$TourDir = Resolve-ProjectPath "results/scratch_best_tours"
$BinDir = Resolve-ProjectPath "bin"
$SerialSource = Resolve-ProjectPath "src_scratch/tsp_scratch_serial.c"
$MpiSource = Resolve-ProjectPath "src_scratch/tsp_scratch_mpi.c"
$SerialExe = Resolve-ProjectPath "bin/tsp_scratch_serial.exe"
$MpiExe = Resolve-ProjectPath "bin/tsp_scratch_mpi.exe"
$AlgorithmLabel = Get-AlgorithmLabel $Algorithm

Assert-NotProtectedResultPath $ResultsFile
Assert-NotProtectedResultPath $SummaryCsv
Assert-NotProtectedResultPath $SummaryTxt

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
Backup-Existing $SummaryCsvPath
Backup-Existing $SummaryTxtPath
Backup-Existing $TourDir
New-Item -ItemType Directory -Force -Path $TourDir | Out-Null

Compile-Serial
Compile-Mpi
Invoke-NativeCommand "scratch smoke test" @($SerialExe, "--smoke") | Out-Null

$seedList = Parse-Seeds $Seeds

foreach ($seed in $seedList) {
    $tourPath = Join-Path $TourDir ("run_{0}_serial_n1_seed{1}.tour" -f $AlgorithmLabel, $seed)
    Invoke-NativeCommand "final serial $Algorithm seed=$seed" @(
        $SerialExe, $InputPath, $Algorithm, "$seed", "$TimeBudgetSec", "$IterationBudget", $ResultsPath, $tourPath
    ) | Out-Null
}

foreach ($nproc in @(2, 4, 6)) {
    foreach ($seed in $seedList) {
        $tourPath = Join-Path $TourDir ("run_{0}_mpi_n{1}_seed{2}.tour" -f $AlgorithmLabel, $nproc, $seed)
        Invoke-NativeCommand "final mpi n=$nproc $Algorithm seed=$seed" @(
            "mpiexec", "-n", "$nproc", $MpiExe, $InputPath, $Algorithm, "$seed",
            "$TimeBudgetSec", "$IterationBudget", $ResultsPath, $tourPath
        ) | Out-Null
    }
}

python (Resolve-ProjectPath "scripts/analyze_scratch_results.py") $ResultsPath $SummaryCsvPath $SummaryTxtPath

$rows = @(Import-Csv -LiteralPath $ResultsPath)
foreach ($group in ($rows | Group-Object algorithm,mode,nproc)) {
    $bestRow = @($group.Group | Sort-Object {[int]$_.best_length}, {[int]$_.seed} | Select-Object -First 1)[0]
    $source = Join-Path $TourDir ("run_{0}_{1}_n{2}_seed{3}.tour" -f $bestRow.algorithm, $bestRow.mode, $bestRow.nproc, $bestRow.seed)
    $target = Join-Path $TourDir ("best_{0}_{1}_n{2}.tour" -f $bestRow.algorithm, $bestRow.mode, $bestRow.nproc)
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Expected per-run tour file not found: $source"
    }
    Copy-Item -LiteralPath $source -Destination $target -Force
}

Write-Host "wrote scratch final results to $ResultsPath"
Write-Host "wrote scratch final summary to $SummaryCsvPath and $SummaryTxtPath"
Write-Host "wrote scratch best tours to $TourDir"
