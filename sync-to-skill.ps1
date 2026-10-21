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
foreach ($d in @("skill", "qa", "source-gemini", "kb")) {
    $p = Join-Path $dst $d
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}

# Only content the skill needs. Do NOT copy input\ and output\ (raw product data
# and generated listings stay in the workspace; they would bloat the skill folder).
# kb\ IS required: check_facts.py loads kb\_schemas\<category>.schema.json.
$items = @("SKILL.md", "README.md", "skill", "qa", "kb", "source-gemini", "sync-to-skill.cmd", "sync-to-skill.ps1")
foreach ($item in $items) {
    $p = Join-Path $src $item
    if (Test-Path $p) {
        Copy-Item $p $dst -Recurse -Force
    }
}

# Generated artifacts are not part of the skill; scripts rebuild them on demand.
# NEVER put a Chinese folder name in this file: it is ASCII-only on purpose, and
# Windows PowerShell 5.1 reads BOM-less UTF-8 as ANSI, so a literal CJK path
# becomes mojibake and Test-Path silently returns false - which is exactly how
# 40 stray report files used to survive every sync. Delete qa sub-folders by
# enumeration instead.
Remove-Item (Join-Path $dst "kb\_index") -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem (Join-Path $dst "qa") -Directory -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "[OK] synced: $src -> $dst (input/output/index excluded)"

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
# Run from the SOURCE qa folder and write reports to TEMP: running it inside
# $dst\qa would drop the generated report folder right back into the skill.
$demoOut = Join-Path $env:TEMP ("dsh-listing-demo-" + [guid]::NewGuid().ToString("N"))
Push-Location (Join-Path $src "qa")
try {
    & $py check_listing.py --demo --site MX --out $demoOut
} finally {
    Pop-Location
    Remove-Item $demoOut -Recurse -Force -ErrorAction SilentlyContinue
}
