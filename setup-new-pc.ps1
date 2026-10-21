# One-time setup on a new machine (e.g. the office PC).
# Usage: double-click setup-new-pc.cmd
#   or: powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-new-pc.ps1 -FullCheck
# This file is intentionally ASCII-only. Windows PowerShell 5.1 reads UTF-8
# files without BOM as ANSI, which breaks on Chinese characters.
param(
    [switch]$FullCheck,
    [string]$SkillDir
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Step([string]$n, [string]$msg) { Write-Host ""; Write-Host "=== $n. $msg ===" -ForegroundColor Cyan }
function Ok([string]$msg) { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "[ .. ] $msg" -ForegroundColor Yellow }
function Fail([string]$msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red; exit 1 }

Step 1 "Check the workspace"
foreach ($f in @("SKILL.md", "README.md", "skill", "qa")) {
    if (-not (Test-Path (Join-Path $root $f))) { Fail "missing '$f' - is this the listing-pipeline folder?" }
}
Ok "workspace: $root"

Step 2 "Resolve Python"
$py = $null
$dshPy = Join-Path $env:USERPROFILE ".dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if (Test-Path $dshPy) { $py = $dshPy }
if (-not $py) {
    $c = Get-Command python -ErrorAction SilentlyContinue
    if ($c) { $py = $c.Source }
}
if (-not $py) { Fail "python not found. Install DSH (or Python 3.9+) first." }
$ver = & $py -c "import sys; print(sys.version.split()[0])"
Ok "python $ver -> $py"
& $py -c "import openpyxl" 2>$null
if ($LASTEXITCODE -ne 0) { Warn "openpyxl missing in this python; run_batch.py auto-switches to the DSH runtime" }

Step 3 "Install / refresh the global skill"
$sync = Join-Path $root "sync-to-skill.ps1"
$target = $SkillDir
if (-not $target) { $target = Join-Path $env:USERPROFILE ".agents\skills\latam-tiktok-listing" }
if ($SkillDir) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $sync -SkillDir $target
} else {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $sync
}
if ($LASTEXITCODE -ne 0) { Fail "sync-to-skill.ps1 failed (exit=$LASTEXITCODE)" }
Ok "skill installed: $target"

Step "3b" "Install the collector skill (Mercado Libre -> input\<SKU>\)"
$syncCollector = Join-Path $root "sync-collector-skill.ps1"
if (Test-Path $syncCollector) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $syncCollector
    if ($LASTEXITCODE -ne 0) { Fail "sync-collector-skill.ps1 failed (exit=$LASTEXITCODE)" }
    Ok "collector skill installed: $env:USERPROFILE\.agents\skills\mercadolibre-listing-collector"
} else {
    Warn "sync-collector-skill.ps1 not found; collector skill not installed"
}

Step 4 "Checker self-test (9 golden cases)"
Push-Location (Join-Path $root "qa")
try {
    & $py check_listing.py --demo --site MX
    $rc = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($rc -ne 0) { Fail "demo self-test failed (exit=$rc)" }
Ok "demo self-test passed"

if ($FullCheck) {
    Step 5 "Full batch check (replay the archived batch -> xlsx)"
    $self = Join-Path $root "output\_smoke"
    if (Test-Path $self) { Remove-Item $self -Recurse -Force }
    New-Item -ItemType Directory -Path $self | Out-Null
    $batch = Get-ChildItem (Join-Path $root "output") -Directory |
        Where-Object { $_.Name -ne "_smoke" -and (Get-ChildItem $_.FullName -Filter "listing-*.txt" -ErrorAction SilentlyContinue) } |
        Select-Object -First 1
    if (-not $batch) {
        Warn "no archived batch with listing-*.txt found; skipped"
    }
    else {
        Copy-Item (Join-Path $batch.FullName "listing-*.txt") $self
        & $py (Join-Path $root "qa\run_batch.py") --input-root (Join-Path $root "input") --listing-dir $self --site MX
        $xlsx = @(Get-ChildItem $self -Filter "*.xlsx")
        if ($xlsx.Count -lt 2) { Fail "expected 2 xlsx, got $($xlsx.Count) in $self" }
        Ok "batch check passed: $($xlsx.Count) xlsx -> $self"
    }
}

Write-Host ""
Write-Host "ALL DONE." -ForegroundColor Green
Write-Host "Next:"
Write-Host "  1) Open DSH and ask it to load the skill 'latam-tiktok-listing'."
Write-Host "  2) Put the product images back under input\ (same folder layout)."
Write-Host "  3) Run a batch when ready."
Write-Host "  4) To collect new listings, make sure a residential exit is up FIRST,"
Write-Host "     then load the skill 'mercadolibre-listing-collector' (collector\SKILL.md)."
