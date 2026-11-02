# Sync the Codex-style tiktok-shop-listing skill from codex-skill/ to global skills dir.
# This is a lightweight sync: only SKILL.md, references/, and agents/ are copied.
# No qa scripts, no kb schemas - those belong to latam-tiktok-listing.
param(
    [string]$SkillDir = (Join-Path $env:USERPROFILE ".agents\skills\tiktok-shop-listing")
)

$ErrorActionPreference = "Stop"
$src = Join-Path $PSScriptRoot "codex-skill"
$dst = $SkillDir

if (-not (Test-Path $dst)) {
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
}

$srcFull = (Resolve-Path -LiteralPath $src).Path.TrimEnd('\')
$dstFull = (Resolve-Path -LiteralPath $dst).Path.TrimEnd('\')
if ($srcFull -eq $dstFull) {
    Write-Host "[FAIL] source and target are the same folder: $srcFull" -ForegroundColor Red
    exit 1
}

# Copy only the Codex skill content (no qa, no kb, no input/output)
$items = @("SKILL.md", "references", "agents")
foreach ($item in $items) {
    $p = Join-Path $src $item
    if (Test-Path $p) {
        Copy-Item $p $dst -Recurse -Force
    }
}

Write-Host "[OK] copied Codex skill: $src -> $dst"

# SHA256 verification
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
if ($problems.Count -gt 0) {
    Write-Host "[FAIL] hash verification failed:" -ForegroundColor Red
    foreach ($p in $problems) { Write-Host "       - $p" }
    exit 1
}
Write-Host "[OK] synced $($srcMap.Count) files, hash OK"
