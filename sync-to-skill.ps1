# Sync the workspace master copy to the global skill folder.
# Usage (recommended): double-click sync-all.cmd (both skills) or sync-to-skill.cmd
#   or: powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-to-skill.ps1
# This file is intentionally ASCII-only. Windows PowerShell 5.1 reads UTF-8 files
#       without BOM as ANSI, which breaks on Chinese characters.
# Source : the folder containing this script (works on any machine / drive)
# Target : %USERPROFILE%\.agents\skills\latam-tiktok-listing
#   Override the target with: -SkillDir <path>   (used by setup-new-pc.ps1 / testing)
# Safety : refuses to run when source and target resolve to the same folder.
#          A copy of this script used to live inside the skill folder; running it
#          there deleted qa/skill/kb and then copied from the already-wiped folder.
# Verify : every copied file is SHA256-compared with its source (per file); any
#          missing / mismatched / stale file is listed and the script exits 1.
param(
    [string]$SkillDir = (Join-Path $env:USERPROFILE ".agents\skills\latam-tiktok-listing")
)

$ErrorActionPreference = "Stop"

$src = $PSScriptRoot
$dst = $SkillDir

if (-not (Test-Path $dst)) {
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
}

$srcFull = (Resolve-Path -LiteralPath $src).Path.TrimEnd('\')
$dstFull = (Resolve-Path -LiteralPath $dst).Path.TrimEnd('\')
if ($srcFull -eq $dstFull) {
    Write-Host "[FAIL] source and target are the same folder: $srcFull" -ForegroundColor Red
    Write-Host "       Run this script from the workspace folder, not from inside the skill folder."
    exit 1
}

# Remove the copied sub-folders first so deleted/renamed files do not linger.
# NOTE: On some Windows setups (DSH sandbox / read-only skill dir), Remove-Item
# may be denied. In that case, Copy-Item -Force below will overwrite existing
# files; stale files from a previous sync are handled by the SHA256 check after.
foreach ($d in @("skill", "qa", "source-gemini", "kb")) {
    $p = Join-Path $dst $d
    if (Test-Path $p) {
        try {
            Remove-Item $p -Recurse -Force -ErrorAction Stop
        } catch {
            # Silently skip removal; Copy-Item -Force will overwrite files anyway.
            # The SHA256 verification step below will catch any stale extras.
        }
    }
}

# Old versions copied the sync scripts themselves into the skill folder. They are
# self-destructive there (src == dst), so remove any leftovers.
foreach ($stale in @("sync-to-skill.ps1", "sync-to-skill.cmd")) {
    $p = Join-Path $dst $stale
    if (Test-Path $p) {
        Remove-Item $p -Force
        Write-Host "[..] removed stale copy from target: $stale"
    }
}

# Only content the skill needs. Do NOT copy input\ and output\ (raw product data
# and generated listings stay in the workspace; they would bloat the skill folder).
# kb\ IS required: check_facts.py loads kb\_schemas\<category>.schema.json.
# The sync scripts are intentionally NOT in this list: they belong to the workspace.
$items = @("SKILL.md", "README.md", "skill", "qa", "kb", "source-gemini")
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
Write-Host "[OK] copied: $src -> $dst"

# ---- SHA256 verification: source vs target, per file ----
function Get-SkillFileHash {
    param([string]$Root, [string[]]$Names)
    $map = @{}
    foreach ($name in $Names) {
        $p = Join-Path $Root $name
        if (-not (Test-Path $p)) { continue }
        $files = @()
        if (Test-Path $p -PathType Leaf) {
            $files = @(Get-Item -LiteralPath $p)
        } else {
            $files = @(Get-ChildItem -LiteralPath $p -Recurse -File -ErrorAction SilentlyContinue)
        }
        foreach ($f in $files) {
            $rel = $f.FullName.Substring($Root.Length + 1).Replace('\', '/')
            if ($rel -match '(^|/)__pycache__/') { continue }
            if ($rel -like '*.pyc') { continue }
            if ($rel -like 'kb/_index/*') { continue }
            if ($rel -like 'qa/*/*') { continue }   # generated qa sub-folders (reports)
            $map[$rel] = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
        }
    }
    return $map
}

$srcMap = Get-SkillFileHash -Root $srcFull -Names $items
$dstMap = Get-SkillFileHash -Root $dstFull -Names $items
$problems = @()
foreach ($rel in ($srcMap.Keys | Sort-Object)) {
    if (-not $dstMap.ContainsKey($rel)) {
        $problems += "missing in target: $rel"
    } elseif ($dstMap[$rel] -ne $srcMap[$rel]) {
        $problems += "hash mismatch: $rel"
    }
}
foreach ($rel in ($dstMap.Keys | Sort-Object)) {
    if (-not $srcMap.ContainsKey($rel)) {
        $problems += "stale extra file in target: $rel"
    }
}
if ($problems.Count -gt 0) {
    Write-Host ""
    Write-Host "[FAIL] hash verification failed ($($problems.Count) problem(s)):" -ForegroundColor Red
    foreach ($p in $problems) { Write-Host "       - $p" }
    exit 1
}
Write-Host "[OK] synced $($srcMap.Count) files, hash OK"

# ---- self-test: a broken copy must fail here, not in the middle of a listing ----
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
    Write-Host "[!] python not found; skipped the self-test. Install Python (or DSH) then re-run." -ForegroundColor Yellow
    exit 0
}
Write-Host "[..] self-test with the 9 V3.2 golden cases ($py):"
# Run from the SOURCE qa folder and write reports to TEMP: running it inside
# $dst\qa would drop generated report folders right back into the skill.
$demoOut = Join-Path $env:TEMP ("dsh-listing-demo-" + [guid]::NewGuid().ToString("N"))
Push-Location (Join-Path $src "qa")
try {
    & $py check_listing.py --demo --site MX --out $demoOut
    $rc = $LASTEXITCODE
} finally {
    Pop-Location
    Remove-Item $demoOut -Recurse -Force -ErrorAction SilentlyContinue
}
if ($rc -ne 0) {
    Write-Host "[FAIL] self-test failed (check_listing.py --demo exit=$rc). Do not use this skill copy." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] self-test passed (9 golden cases)"
