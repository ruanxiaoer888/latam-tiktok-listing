# Sync BOTH skills from this workspace to %USERPROFILE%\.agents\skills and report
# whether the DuMate-managed copies are fresh.
# Usage:
#   double-click sync-all.cmd
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-all.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-all.ps1 -DryRun
#     -DryRun only prints the status table and DuMate freshness; it never syncs.
# This file is intentionally ASCII-only. Windows PowerShell 5.1 reads UTF-8 files
#       without BOM as ANSI, which breaks on Chinese characters.
# Notes:
#   - The DuMate copies live under %APPDATA%\qianfan-desktop-app\...\data\skills\user\
#     and are managed by the DuMate app itself. This script NEVER writes there
#     (it would break DuMate's own _meta.json); it only warns and prints the hash.
#   - Exit code: 0 = sync + hash verification OK (DuMate mismatch is a warning),
#     1 = a sync script failed or file hashes do not match.
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$agentsRoot = Join-Path $env:USERPROFILE ".agents\skills"

function Get-Sha256 {
    param([string]$Path)
    if (-not $Path) { return "" }
    if (-not (Test-Path $Path -PathType Leaf)) { return "" }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Get-ShortHash {
    param([string]$Hash)
    if (-not $Hash) { return "-" }
    return $Hash.Substring(0, 12)
}

function Get-FileTime {
    param([string]$Path)
    if (-not $Path) { return "-" }
    if (-not (Test-Path $Path -PathType Leaf)) { return "-" }
    return (Get-Item -LiteralPath $Path).LastWriteTime.ToString("yyyy-MM-dd HH:mm")
}

function Invoke-SyncScript {
    param([string]$ScriptPath)
    # Pipe the child process output to the host. Without this, PowerShell captures
    # every stdout line of the child as pipeline objects and this function would
    # return an ARRAY (lines + exit code), breaking the -ne 0 test below.
    & powershell -NoProfile -ExecutionPolicy Bypass -File $ScriptPath | Out-Host
    return [int]$LASTEXITCODE
}

if (-not (Test-Path (Join-Path $root "sync-to-skill.ps1"))) {
    Write-Host "[FAIL] sync-to-skill.ps1 not found next to this script: $root" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $root "sync-collector-skill.ps1"))) {
    Write-Host "[FAIL] sync-collector-skill.ps1 not found next to this script: $root" -ForegroundColor Red
    exit 1
}

if ($DryRun) {
    Write-Host "[..] -DryRun: sync scripts were NOT executed."
} else {
    Write-Host "=== 1/2 latam-tiktok-listing ==="
    $rc = Invoke-SyncScript (Join-Path $root "sync-to-skill.ps1")
    if ($rc -ne 0) {
        Write-Host "[FAIL] sync-to-skill.ps1 failed (exit=$rc); stopping." -ForegroundColor Red
        exit 1
    }
    Write-Host ""
    Write-Host "=== 2/2 mercadolibre-listing-collector ==="
    $rc = Invoke-SyncScript (Join-Path $root "sync-collector-skill.ps1")
    if ($rc -ne 0) {
        Write-Host "[FAIL] sync-collector-skill.ps1 failed (exit=$rc); stopping." -ForegroundColor Red
        exit 1
    }
}

# ---- DuMate-managed copies: read-only freshness comparison ----
$dumateRoots = @()
$xdgRoot = $null
if ($env:APPDATA) {
    $xdgRoot = Join-Path $env:APPDATA "qianfan-desktop-app\qianfan_desk_xdg"
}
if ($xdgRoot -and (Test-Path $xdgRoot)) {
    $dumateRoots = @(Get-ChildItem -LiteralPath $xdgRoot -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "data\skills\user" })
}

function Find-DuMateSkill {
    param([string]$Name)
    foreach ($r in $dumateRoots) {
        $p = Join-Path $r $Name
        if (Test-Path $p) { return $p }
    }
    return ""
}

$skills = @(
    [pscustomobject]@{
        Name = "latam-tiktok-listing"
        RepoFile = (Join-Path $root "SKILL.md")
        AgentsFile = (Join-Path (Join-Path $agentsRoot "latam-tiktok-listing") "SKILL.md")
    },
    [pscustomobject]@{
        Name = "mercadolibre-listing-collector"
        RepoFile = (Join-Path $root "collector\SKILL.md")
        AgentsFile = (Join-Path (Join-Path $agentsRoot "mercadolibre-listing-collector") "SKILL.md")
    }
)

$rows = @()
$warnings = @()
foreach ($s in $skills) {
    $repoHash = Get-Sha256 $s.RepoFile
    $agentsHash = Get-Sha256 $s.AgentsFile
    $dumateDir = Find-DuMateSkill $s.Name
    $dumateFile = ""
    $dumateHash = ""
    if ($dumateDir) {
        $dumateFile = Join-Path $dumateDir "SKILL.md"
        $dumateHash = Get-Sha256 $dumateFile
    }

    $agentsMatch = "NO"
    if ($agentsHash -and $repoHash -and ($agentsHash -eq $repoHash)) { $agentsMatch = "yes" }

    $dumateMatch = "n/a"
    if ($dumateDir) {
        $dumateMatch = "NO"
        if ($dumateHash -and $repoHash -and ($dumateHash -eq $repoHash)) { $dumateMatch = "yes" }
    }

    $rows += [pscustomobject]@{
        Skill = $s.Name
        RepoHash = (Get-ShortHash $repoHash)
        RepoTime = (Get-FileTime $s.RepoFile)
        AgentsHash = (Get-ShortHash $agentsHash)
        AgentsTime = (Get-FileTime $s.AgentsFile)
        AgentsMatch = $agentsMatch
        DuMateHash = (Get-ShortHash $dumateHash)
        DuMateTime = (Get-FileTime $dumateFile)
        DuMateMatch = $dumateMatch
    }

    if ($dumateDir -and ($dumateHash -ne $repoHash)) {
        $warnings += "DuMate copy of '$($s.Name)' is stale -> update it inside the DuMate app"
        $warnings += "    path: $dumateFile"
    }
}

Write-Host ""
Write-Host "=== skill status: repo vs %USERPROFILE%\.agents vs DuMate ==="
$rows | Format-Table -AutoSize | Out-String -Width 240 | Write-Host

if ($warnings.Count -gt 0) {
    Write-Host "[!] WARNING: DuMate copies are stale (this script never writes there):" -ForegroundColor Yellow
    foreach ($w in $warnings) { Write-Host "    $w" -ForegroundColor Yellow }
    Write-Host ""
}

if ($DryRun) {
    Write-Host "[OK] sync-all dry run finished (nothing was written)."
} else {
    Write-Host "[OK] sync-all finished: both skills synced and hash-verified."
}
exit 0
