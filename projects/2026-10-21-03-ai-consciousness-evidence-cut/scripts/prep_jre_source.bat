@echo off
setlocal
cd /d "%~dp0"
set "SRC=Joe Rogan Experience #2541 - Thomas Campbell.mp4"
title Preparing JRE #2541 source for editing

if not exist "%SRC%" (
  echo [ERROR] Source video not found in this folder:
  echo         %SRC%
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ffmpeg not found - installing it with winget ^(one-time^)...
  winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
  set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WinGet\Links"
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [ERROR] ffmpeg is still not available. Please close this window and run the script again.
  pause
  exit /b 1
)

if not exist "jre_parts" mkdir "jre_parts"

echo.
echo [1/2] Extracting a small audio track for transcription...
ffmpeg -hide_banner -loglevel error -stats -y -i "%SRC%" -vn -ac 1 -ar 16000 -c:a aac -b:a 40k "jre_parts\jre_audio.m4a"

echo.
echo [2/2] Splitting the video into ~25-minute parts (lossless, no re-encode)...
ffmpeg -hide_banner -loglevel error -stats -y -i "%SRC%" -map 0:v:0 -map 0:a:0 -c copy -f segment -segment_time 1500 -reset_timestamps 1 -segment_list "jre_parts\parts.csv" "jre_parts\part_%%02d.mp4"

echo.
echo Done. Files are in the "jre_parts" folder. You can close this window.
pause
