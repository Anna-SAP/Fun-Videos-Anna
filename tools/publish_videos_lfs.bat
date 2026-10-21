@echo off
rem Double-click to upload the videos in this folder to GitHub (Git LFS).
rem Put this file and publish_videos_lfs.ps1 in the folder that holds the videos.
cd /d "%~dp0"
title Uploading videos to GitHub (Git LFS)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish_videos_lfs.ps1" -SourceDir "%~dp0."
echo.
pause
