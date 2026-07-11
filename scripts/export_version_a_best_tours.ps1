param(
    [string]$InputFile = "data/pcb442.tsp",
    [string]$ResultsFile = "results/final_experiment_results.csv",
    [string]$TourDir = "results/version_a_best_tours"
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

function Format-ConfigName($Row) {
    if ([int]$Row.num_groups -gt 0) {
        return ("{0}_n{1}_groups{2}_seed{3}" -f $Row.algorithm, $Row.nproc, $Row.num_groups, $Row.base_seed)
    }
    return ("{0}_n{1}_seed{2}" -f $Row.algorithm, $Row.nproc, $Row.base_seed)
}

function Read-LastResultRow([string]$Path) {
    $rows = @(Import-Csv -LiteralPath $Path)
    if ($rows.Count -lt 1) {
        throw "Temporary result CSV has no data rows: $Path"
    }
    return $rows[$rows.Count - 1]
}

function Invoke-TourExport($Row) {
    $name = Format-ConfigName $Row
    $tempPath = Join-Path $TempDir ("tmp_{0}.csv" -f $name)
    $tourPath = Join-Path $TourPath ("best_{0}.tour" -f $name)
    if (Test-Path -LiteralPath $tempPath) {
        Remove-Item -LiteralPath $tempPath -Force
    }

    $algorithm = [string]$Row.algorithm
    $nproc = [int]$Row.nproc
    $maxGen = [string]$Row.maxGen
    $migration = [string]$Row.migration_interval
    $ratio = [string]$Row.local_to_global_ratio
    $groups = [string]$Row.num_groups
    $seed = [string]$Row.base_seed

    if ($algorithm -eq "SERIAL") {
        Invoke-NativeCommand "export tour $name" @(
            $SerialExe, $InputPath, $maxGen, $seed, $tempPath, "100", $tourPath
        ) | Out-Null
    } elseif ($algorithm -eq "DEA") {
        Invoke-NativeCommand "export tour $name" @(
            "mpiexec", "-n", "$nproc", $DeaExe, $InputPath, $maxGen, $migration, $seed, $tempPath, "100", $tourPath
        ) | Out-Null
    } elseif ($algorithm -eq "HDEA") {
        Invoke-NativeCommand "export tour $name" @(
            "mpiexec", "-n", "$nproc", $HdeaExe, $InputPath, $maxGen, $migration, $ratio, $groups, $seed, $tempPath, "100", $tourPath
        ) | Out-Null
    } elseif ($algorithm -eq "MOVING_HDEA") {
        Invoke-NativeCommand "export tour $name" @(
            "mpiexec", "-n", "$nproc", $MovingHdeaExe, $InputPath, $maxGen, $migration, $ratio, $groups, $seed, $tempPath, "100", $tourPath
        ) | Out-Null
    } else {
        throw "Unknown algorithm: $algorithm"
    }

    $rerun = Read-LastResultRow $tempPath
    if ([double]$rerun.global_best -ne [double]$Row.global_best) {
        throw "Rerun mismatch for ${name}: expected $($Row.global_best), got $($rerun.global_best)"
    }
    Remove-Item -LiteralPath $tempPath -Force
    Write-Host "wrote $tourPath"
}

$ProjectRoot = Get-ProjectRoot
$InputPath = Resolve-ProjectPath $InputFile
$ResultsPath = Resolve-ProjectPath $ResultsFile
$TourPath = Resolve-ProjectPath $TourDir
$TempDir = Join-Path (Split-Path -Parent $TourPath) "_tmp_version_a_tours"
$BinDir = Join-Path $ProjectRoot "bin"

$SerialSource = Join-Path $ProjectRoot "src/tsp_serial_exp.c"
$DeaSource = Join-Path $ProjectRoot "src/tsp_mpi_dea.c"
$HdeaSource = Join-Path $ProjectRoot "src/tsp_mpi_hdea.c"
$MovingHdeaSource = Join-Path $ProjectRoot "src/tsp_mpi_moving_hdea.c"
$SerialExe = Join-Path $BinDir "tsp_serial_exp.exe"
$DeaExe = Join-Path $BinDir "tsp_mpi_dea.exe"
$HdeaExe = Join-Path $BinDir "tsp_mpi_hdea.exe"
$MovingHdeaExe = Join-Path $BinDir "tsp_mpi_moving_hdea.exe"

foreach ($path in @($InputPath, $ResultsPath, $SerialSource, $DeaSource, $HdeaSource, $MovingHdeaSource)) {
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

New-Item -ItemType Directory -Force -Path $BinDir, $TourPath, $TempDir | Out-Null

Compile-Serial
Compile-MpiProgram "DEA" $DeaSource $DeaExe
Compile-MpiProgram "HDEA" $HdeaSource $HdeaExe
Compile-MpiProgram "MOVING_HDEA" $MovingHdeaSource $MovingHdeaExe

$rows = @(Import-Csv -LiteralPath $ResultsPath)
$bestRows = $rows |
    Group-Object algorithm,nproc,migration_interval,local_to_global_ratio,num_groups |
    ForEach-Object {
        $_.Group | Sort-Object {[double]$_.global_best}, {[int]$_.base_seed} | Select-Object -First 1
    }

foreach ($row in $bestRows) {
    Invoke-TourExport $row
}

Remove-Item -LiteralPath $TempDir -Recurse -Force
Write-Host "exported $($bestRows.Count) Version A best tours to $TourPath"
