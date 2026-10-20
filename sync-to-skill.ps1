# Sync the workspace master copy to the global skill folder.
# Usage (recommended): double-click sync-to-skill.cmd
#   or: powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-to-skill.ps1
# Note: this file is intentionally ASCII-only. Windows PowerShell 5.1 reads
#       UTF-8 files without BOM as ANSI, which breaks on Chinese characters.
# Source : the folder containing this script (works on any machine / drive)
# Target : %USERPROFILE%\.agents\skills\latam-tiktok-listing
#   Override the target with: -SkillDir <path>   (used by setup-new-pc.ps1 / testing)
param(
    [string]$SkillDir = (Join-Path $env:USERPROFILE ".agents\skills\latam-tiktok-listing")
)

$ErrorActionPreference = "Stop"

$src = $PSScriptRoot
$dst = $SkillDir

if (-not (Test-Path $dst)) {
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
}

# Remove the copied sub-folders first so deleted/renamed files do not linger.
foreach ($d in @("skill", "qa", "source-gemini")) {
    $p = Join-Path $dst $d
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}

# Only content the skill needs. Do NOT copy input\ and output\ (raw product data
# and generated listings stay in the workspace; they would bloat the skill folder).
$items = @("SKILL.md", "README.md", "skill", "qa", "source-gemini", "sync-to-skill.cmd", "sync-to-skill.ps1")
foreach ($item in $items) {
    $p = Join-Path $src $item
    if (Test-Path $p) {
        Copy-Item $p $dst -Recurse -Force
    }
}
Write-Host "[OK] synced: $src -> $dst (input/output excluded)"

# Resolve a Python interpreter: prefer the DSH bundled runtime, then PATH.
$py = $null
$dshPy = Join-Path $env:USERPROFILE ".dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if (Test-Path $dshPy) { $py = $dshPy }
if (-not $py) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $py = $cmd.Source }
}

Write-Host ""
if (-not $py) {
    Write-Host "[!] python not found. Install Python or run DSH once, then retry the self-test."
    exit 1
}
Write-Host "[..] self-test with the 9 V3.2 golden cases ($py):"
Push-Location (Join-Path $dst "qa")
try {
    & $py check_listing.py --demo --site MX
} finally {
    Pop-Location
}
