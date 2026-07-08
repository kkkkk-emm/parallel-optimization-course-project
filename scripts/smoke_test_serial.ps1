param(
    [string]$Source = "src/tsp_serial_fixed.c",
    [string]$InputFile = "data/pcb442.tsp",
    [int]$MaxGen = 100,
    [string]$OutputFile = "results/serial_result.txt"
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
$OutputPath = Resolve-ProjectPath $OutputFile
$BinDir = Join-Path $ProjectRoot "bin"
$ExePath = Join-Path $BinDir "tsp_serial_fixed.exe"

New-Item -ItemType Directory -Force -Path $BinDir, (Split-Path -Parent $OutputPath) | Out-Null

if (-not (Test-Path -LiteralPath $SourcePath)) {
    throw "Missing source file: $SourcePath"
}

if (-not (Test-Path -LiteralPath $InputPath)) {
    throw "Missing input file: $InputPath"
}

if (Test-Path -LiteralPath $ExePath) {
    Remove-Item -LiteralPath $ExePath -Force
}

gcc -x c -std=c11 -Wall -Wextra -O2 $SourcePath -lm -o $ExePath
if ($LASTEXITCODE -ne 0) {
    throw "gcc failed with exit code $LASTEXITCODE"
}

if (Test-Path -LiteralPath $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
}

$output = & $ExePath $InputPath $MaxGen $OutputPath 2>&1
if ($LASTEXITCODE -ne 0) {
    $output | ForEach-Object { Write-Host $_ }
    throw "program failed with exit code $LASTEXITCODE"
}

$required = @(
    "read 442 cities",
    "distance matrix initialized",
    "colony initialized",
    "init success",
    "1:",
    "Final solution"
)

foreach ($needle in $required) {
    if (($output -join "`n") -notmatch [regex]::Escape($needle)) {
        $output | ForEach-Object { Write-Host $_ }
        throw "missing expected output marker: $needle"
    }
}

if (-not (Test-Path -LiteralPath $OutputPath)) {
    throw "serial result file was not created: $OutputPath"
}

$output | ForEach-Object { Write-Host $_ }
Write-Host "serial smoke test passed"
