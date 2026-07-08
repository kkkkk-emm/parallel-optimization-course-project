param(
    [string]$ResultsFile = "results/quick_experiment_results.csv"
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
$ResultsPath = Resolve-ProjectPath $ResultsFile
$AnalysisTxt = Join-Path $ProjectRoot "results/quick_analysis_summary.txt"
$AnalysisCsv = Join-Path $ProjectRoot "results/quick_analysis_summary.csv"
$RunScript = Join-Path $ProjectRoot "scripts/run_experiments.ps1"
$AnalyzeScript = Join-Path $ProjectRoot "scripts/analyze_results.py"

$requiredFiles = @(
    "src/tsp_serial_exp.c",
    "src/tsp_mpi_dea.c",
    "scripts/run_experiments.ps1",
    "scripts/analyze_results.py",
    "data/pcb442.tsp"
)

foreach ($file in $requiredFiles) {
    $path = Resolve-ProjectPath $file
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing required file: $path"
    }
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ResultsPath) | Out-Null

foreach ($path in @($ResultsPath, $AnalysisTxt, $AnalysisCsv)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

powershell -ExecutionPolicy Bypass -File $RunScript `
    -MaxGen 100 `
    -MigrationInterval 20 `
    -Seeds "12345,22345,32345" `
    -ResultsFile $ResultsPath `
    -IncludeDea1

if (-not (Test-Path -LiteralPath $ResultsPath)) {
    throw "Quick results file was not created: $ResultsPath"
}

$rows = Import-Csv -LiteralPath $ResultsPath
if ($rows.Count -ne 12) {
    throw "Expected 12 quick result rows, got $($rows.Count)"
}

$groups = $rows | Group-Object algorithm,nproc
$requiredGroups = @("SERIAL, 1", "DEA, 1", "DEA, 2", "DEA, 4")
foreach ($groupName in $requiredGroups) {
    if (-not ($groups | Where-Object { $_.Name -eq $groupName -and $_.Count -eq 3 })) {
        throw "Missing expected quick result group: $groupName"
    }
}

python $AnalyzeScript $ResultsPath $AnalysisTxt $AnalysisCsv

if (-not (Test-Path -LiteralPath $AnalysisTxt)) {
    throw "Quick analysis summary was not created: $AnalysisTxt"
}

Get-Content -LiteralPath $ResultsPath | Select-Object -First 5
Write-Host "..."
Get-Content -LiteralPath $ResultsPath | Select-Object -Last 5
Write-Host "quick experiment pipeline smoke test passed"
