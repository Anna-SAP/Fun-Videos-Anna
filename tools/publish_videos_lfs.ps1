# publish_videos_lfs.ps1
# Upload the repository's video files with Git LFS, from the PC that holds them.
#
# Why this runs locally: the cloud workspace that builds this repo cannot reach
# GitHub's LFS storage hosts, so docs are pushed from there and the videos are
# pushed from here. See docs/storage-policy.md.
#
# What it does
#   1. makes sure Git and Git LFS are installed (installs them with winget if not)
#   2. clones https://github.com/Anna-SAP/Fun-Videos-Anna (or updates an existing clone)
#   3. reads tools/video-manifest.csv: repo_path, local_file, bytes, sha256, note
#   4. for every row whose local_file exists in -SourceDir: verifies the SHA-256,
#      copies it to repo_path and stages it (the repo's .gitattributes routes it to LFS)
#   5. refuses to commit if any staged video is not an LFS pointer, then commits and pushes
#
# Usage: double-click publish_videos_lfs.bat placed in the folder with the videos, or
#   powershell -ExecutionPolicy Bypass -File publish_videos_lfs.ps1 [-SourceDir <folder>]
# Safe to run again: unchanged videos are skipped and nothing is committed twice.

param(
    [string]$SourceDir = $PSScriptRoot,
    [string]$RepoUrl = 'https://github.com/Anna-SAP/Fun-Videos-Anna.git'
)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

function Fail([string]$msg) {
    Write-Host ''
    Write-Host ('ERROR: ' + $msg) -ForegroundColor Red
    exit 1
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

# ---------------------------------------------------------------- 1. tools
Write-Host '[1/5] Checking Git and Git LFS ...'
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host '      Git not found - installing Git for Windows with winget (one-time) ...'
    winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements
    Refresh-Path
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Fail 'Git is still not available. Close this window and run the script again.'
    }
}
git lfs version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host '      Git LFS not found - installing with winget (one-time) ...'
    winget install -e --id GitHub.GitLFS --accept-source-agreements --accept-package-agreements
    Refresh-Path
    git lfs version *> $null
    if ($LASTEXITCODE -ne 0) { Fail 'Git LFS is still not available. Close this window and run the script again.' }
}
git lfs install *> $null
git lfs version

# ---------------------------------------------------------------- 2. repository
Write-Host ''
Write-Host '[2/5] Getting the repository ...'
$parent = Split-Path -Parent $PSScriptRoot
$runningInsideRepo = ((Split-Path -Leaf $PSScriptRoot) -eq 'tools') -and
                     (Test-Path -LiteralPath (Join-Path $parent '.git')) -and
                     (Test-Path -LiteralPath (Join-Path (Join-Path $parent 'tools') 'video-manifest.csv'))
if ($runningInsideRepo) {
    $RepoDir = $parent                                   # script is running from <repo>\tools
    git -C $RepoDir pull --ff-only
} else {
    $RepoDir = Join-Path $SourceDir 'Fun-Videos-Anna'    # keep a clone next to the videos
    if (Test-Path -LiteralPath (Join-Path $RepoDir '.git')) {
        git -C $RepoDir pull --ff-only
    } else {
        git clone $RepoUrl $RepoDir
    }
}
if ($LASTEXITCODE -ne 0) { Fail 'Could not clone or update the repository. Check the network and your GitHub sign-in.' }
Write-Host ('      repository: ' + $RepoDir)

$gname = git -C $RepoDir config user.name
$gmail = git -C $RepoDir config user.email
if (-not $gname -or -not $gmail) {
    git -C $RepoDir config user.name 'Anna-SAP'
    git -C $RepoDir config user.email 'Anna-SAP@users.noreply.github.com'
    Write-Host '      (no Git identity configured - using Anna-SAP for this repository only)'
}

# ---------------------------------------------------------------- 3. copy + verify
Write-Host ''
Write-Host ('[3/5] Copying videos listed in tools\video-manifest.csv from ' + $SourceDir + ' ...')
$manifest = Join-Path (Join-Path $RepoDir 'tools') 'video-manifest.csv'
if (-not (Test-Path -LiteralPath $manifest)) { Fail 'tools\video-manifest.csv not found in the repository.' }
$rows = Import-Csv -LiteralPath $manifest -Encoding UTF8

$missing = @(); $mismatch = @(); $ready = 0
foreach ($r in $rows) {
    $src = Join-Path $SourceDir $r.local_file
    if (-not (Test-Path -LiteralPath $src)) { $missing += $r.local_file; continue }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $src).Hash.ToLower()
    if ($r.sha256 -and ($hash -ne $r.sha256.ToLower())) { $mismatch += $r.local_file; continue }

    $dst = Join-Path $RepoDir ($r.repo_path -replace '/', [IO.Path]::DirectorySeparatorChar)
    $dstDir = Split-Path -Parent $dst
    if (-not (Test-Path -LiteralPath $dstDir)) { New-Item -ItemType Directory -Force -Path $dstDir | Out-Null }
    $same = (Test-Path -LiteralPath $dst) -and
            ((Get-FileHash -Algorithm SHA256 -LiteralPath $dst).Hash.ToLower() -eq $hash)
    if (-not $same) { Copy-Item -LiteralPath $src -Destination $dst -Force }
    git -C $RepoDir add -- $r.repo_path
    if ($LASTEXITCODE -ne 0) { Fail ('git add failed for ' + $r.repo_path) }
    $ready++
    Write-Host ('      ok   ' + $r.repo_path + '   (' + [math]::Round([double]$r.bytes / 1MB, 1) + ' MB)')
}
foreach ($m in $missing)  { Write-Host ('      skip (not in folder): ' + $m) -ForegroundColor Yellow }
foreach ($m in $mismatch) { Write-Host ('      skip (checksum differs from manifest): ' + $m) -ForegroundColor Yellow }

# ---------------------------------------------------------------- 4. LFS safety check
Write-Host ''
Write-Host '[4/5] Checking that every staged video is an LFS pointer ...'
$staged = @(git -C $RepoDir -c core.quotepath=false diff --cached --name-only)
if ($staged.Count -eq 0 -or -not $staged[0]) {
    Write-Host '      Nothing new to upload - GitHub already has these videos.' -ForegroundColor Green
    exit 0
}
foreach ($p in $staged) {
    $size = [int64](git -C $RepoDir cat-file -s (':' + $p))
    if ($size -gt 1024) {
        git -C $RepoDir reset -q
        Fail ($p + ' would be committed as a normal Git file (' + $size + ' bytes), not via LFS. Nothing was committed.')
    }
    Write-Host ('      lfs  ' + $p)
}

# ---------------------------------------------------------------- 5. commit + push
Write-Host ''
Write-Host ('[5/5] Committing ' + $staged.Count + ' file(s) and pushing to GitHub (a browser sign-in may open) ...')
$msgFile = [System.IO.Path]::GetTempFileName()
$msg = @(
    'Add video assets via Git LFS',
    '',
    'Uploaded from the local video folder with tools/publish_videos_lfs.ps1;',
    'files and SHA-256 checksums are listed in tools/video-manifest.csv.',
    '',
    'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>',
    'Claude-Session: https://claude.ai/code/session_017cBtauyTJwAy2ELaUqyUPx'
)
Set-Content -LiteralPath $msgFile -Value $msg -Encoding ASCII
git -C $RepoDir commit -q -F $msgFile
$rc = $LASTEXITCODE
Remove-Item -LiteralPath $msgFile -ErrorAction SilentlyContinue
if ($rc -ne 0) { Fail 'git commit failed (see the message above).' }

git -C $RepoDir push origin HEAD
if ($LASTEXITCODE -ne 0) {
    Fail 'Push failed. Your commit is kept locally - fix the sign-in / network issue and run this script again.'
}

Write-Host ''
Write-Host 'Files now stored in Git LFS:'
git -C $RepoDir -c core.quotepath=false lfs ls-files
Write-Host ''
Write-Host 'Done. The videos are on GitHub.' -ForegroundColor Green
exit 0
