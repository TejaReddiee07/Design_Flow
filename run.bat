@echo off
setlocal
title Designflow
cd /d "%~dp0backend"

echo.
echo   ================================================
echo     DESIGNFLOW - starting everything for you...
echo   ================================================
echo.

REM ---- [1/4] Python environment (created automatically the first time) ----
if not exist "..\.venv\Scripts\python.exe" (
  echo  [1/4] First-time setup: creating the Python environment...
  python -m venv ..\.venv
  ..\.venv\Scripts\python.exe -m pip install -r requirements.txt
) else (
  echo  [1/4] Python environment ready.
)

REM ---- [2/4] Stop any old copy so the port is always free ----
echo  [2/4] Making sure no old copy of the server is running...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn app.main:app*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul

REM ---- [3/4] Ollama, the local AI the agents use (started hidden) ----
where ollama >nul 2>nul
if %errorlevel%==0 (
  curl -s -o nul --max-time 2 http://localhost:11434/api/tags 2>nul
  if errorlevel 1 (
    echo  [3/4] Starting Ollama in the background...
    powershell -NoProfile -Command "Start-Process -WindowStyle Hidden ollama -ArgumentList 'serve'" >nul 2>nul
    timeout /t 3 /nobreak >nul
  ) else (
    echo  [3/4] Ollama is already running.
  )
  ollama list 2>nul | findstr /i "llama3.2" >nul
  if errorlevel 1 (
    echo        Downloading the AI model llama3.2:3b - first time only, a few minutes...
    ollama pull llama3.2:3b
  )
) else (
  echo  [3/4] Ollama is not installed - agents will use placeholder text.
  echo        Install it later from https://ollama.com and run this file again.
)

REM ---- [4/4] Start the website; the browser opens BY ITSELF once it is ready ----
echo  [4/4] Starting the website... the first start takes 30-60 seconds
echo        while it connects to the database. Please wait.
echo.
echo        Your browser will open http://localhost:8000 automatically.
echo        Admin: /admin    Client portal: /portal    Stop: Ctrl+C here.
echo.
start "" /MIN powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 120;$i++){ try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost:8000/health; Start-Process 'http://localhost:8000'; break } catch { Start-Sleep -Seconds 1 } }"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
