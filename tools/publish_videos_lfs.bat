@echo off
rem Double-click to upload the videos listed in tools/video-manifest.csv to GitHub (Git LFS).
rem Put this file and publish_videos_lfs.ps1 in a folder that holds the videos.
rem EXTRA_DIRS: more folders to look in, separated by ';' (missing folders are skipped).
set "EXTRA_DIRS=%USERPROFILE%\Downloads\Video"
cd /d "%~dp0"
title Uploading videos to GitHub (Git LFS)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish_videos_lfs.ps1" -SourceDir "%~dp0.;%EXTRA_DIRS%"
echo.
pause
