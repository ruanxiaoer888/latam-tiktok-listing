# Sync the Mercado Libre collector skill (source: .\collector) to the global skill folder.
# Usage (recommended): double-click sync-all.cmd (both skills) or sync-collector-skill.cmd
#   or: powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-collector-skill.ps1
# This file is intentionally ASCII-only. Windows PowerShell 5.1 reads UTF-8 files
#       without BOM as ANSI, which breaks on Chinese characters.
# Source : <repo>\collector
# Target : %USERPROFILE%\.agents\skills\mercadolibre-listing-collector
#   Override the target with: -SkillDir <path>   (used by setup-new-pc.ps1 / testing)
# Safety : refuses to run when source and target resolve to the same folder.
# Verify : every copied file is SHA256-compared with its source (per file).
#          Syntax check compiles the scripts into a TEMP folder, so no __pycache__
#          is ever written into the skill folder.
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

$srcFull = (Resolve-Path -LiteralPath $src).Path.TrimEnd('\')
$dstFull = (Resolve-Path -LiteralPath $dst).Path.TrimEnd('\')
if ($srcFull -eq $dstFull) {
    Write-Host "[FAIL] source and target are the same folder: $srcFull" -ForegroundColor Red
    Write-Host "       Run this script from the workspace folder, not from inside the skill folder."
    exit 1
}

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

# ---- syntax check: compile into TEMP so no __pycache__ lands in the skill ----
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
    Write-Host "[!] python not found; skipped the syntax check. Install Python (or DSH) then re-run." -ForegroundColor Yellow
    exit 0
}

$scripts = @(Get-ChildItem (Join-Path $dst "scripts") -Filter "*.py" -File)
$pycTmp = Join-Path $env:TEMP ("dsh-mlpyc-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $pycTmp | Out-Null
$failed = @()
try {
    foreach ($s in $scripts) {
        $cf = Join-Path $pycTmp ($s.BaseName + ".pyc")
        & $py -W error::SyntaxWarning -c "import py_compile, sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)" $s.FullName $cf
        if ($LASTEXITCODE -ne 0) { $failed += $s.Name }
    }
} finally {
    Remove-Item $pycTmp -Recurse -Force -ErrorAction SilentlyContinue
}
if ($failed.Count -gt 0) {
    Write-Host "[FAIL] python compile check failed: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] compiled $($scripts.Count) scripts (temp dir, target stays clean)"
Write-Host ""
Write-Host "Next: read the skill's SKILL.md (section 'hard prerequisites') and make sure" -ForegroundColor Green
Write-Host "      a residential (non-datacenter) exit is available BEFORE collecting."
