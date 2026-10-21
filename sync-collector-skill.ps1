# Sync the Mercado Libre collector skill (source: .\collector) to the global skill folder.
# Usage (recommended): double-click sync-collector-skill.cmd
#   or: powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-collector-skill.ps1
# This file is intentionally ASCII-only. Windows PowerShell 5.1 reads UTF-8 files
#       without BOM as ANSI, which breaks on Chinese characters.
# Source : <repo>\collector
# Target : %USERPROFILE%\.agents\skills\mercadolibre-listing-collector
#   Override the target with: -SkillDir <path>   (used by setup-new-pc.ps1 / testing)
param(
    [string]$SkillDir = (Join-Path $env:USERPROFILE ".agents\skills\mercadolibre-listing-collector")
)

$ErrorActionPreference = "Stop"

$src = Join-Path $PSScriptRoot "collector"
$dst = $SkillDir

if (-not (Test-Path $src)) {
    Write-Host "[FAIL] collector folder not found: $src" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $dst | Out-Null

# Remove the copied sub-folders first so deleted/renamed files do not linger.
foreach ($d in @("references", "scripts")) {
    $p = Join-Path $dst $d
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}

# Only content the skill needs. The collector skill NEVER bundles the workspace:
# input\ (raw product data) and _work\ (intermediate raw_*.json) stay in the repo.
$items = @("SKILL.md", "references", "scripts")
foreach ($item in $items) {
    $p = Join-Path $src $item
    if (Test-Path $p) { Copy-Item $p $dst -Recurse -Force }
}

# Generated artifacts are not part of the skill; scripts rebuild them on demand.
foreach ($junk in @("scripts\__pycache__", "_work")) {
    $p = Join-Path $dst $junk
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}
Write-Host "[OK] synced: $src -> $dst"

# Byte-compile the scripts so a broken copy fails here instead of mid-collection.
$py = $null
$dshPy = Join-Path $env:USERPROFILE ".dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if (Test-Path $dshPy) { $py = $dshPy }
if (-not $py) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $py = $cmd.Source }
}

Write-Host ""
if (-not $py) {
    Write-Host "[!] python not found; skipped the syntax check. Install Python (or DSH) then re-run." -ForegroundColor Yellow
    exit 0
}

$scripts = Get-ChildItem (Join-Path $dst "scripts") -Filter "*.py"
Push-Location (Join-Path $dst "scripts")
try {
    & $py -W error::SyntaxWarning -m py_compile @($scripts.Name)
    $rc = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($rc -ne 0) {
    Write-Host "[FAIL] python compile check failed (exit=$rc)" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] compiled $($scripts.Count) scripts with $py"
Write-Host ""
Write-Host "Next: read the skill's SKILL.md (section 'hard prerequisites') and make sure" -ForegroundColor Green
Write-Host "      a residential (non-datacenter) exit is available BEFORE collecting."