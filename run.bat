@echo off
rem Dubplates.net Client: run from source (Windows). First start: makes .venv, installs PyTorch + the engine, builds the UI.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Making .venv ...
  python -m venv .venv || goto :fail
  .venv\Scripts\python.exe -m pip install --upgrade pip
  where nvidia-smi >nul 2>nul && (
    echo NVIDIA GPU found: installing PyTorch with CUDA
    .venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128 || goto :fail
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :fail
    .venv\Scripts\python.exe -m pip install --force-reinstall --no-deps torch torchaudio --index-url https://download.pytorch.org/whl/cu128 || goto :fail
  ) || (
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :fail
  )
)
if not exist ui\dist\index.html (
  pushd ui && call npm install && call npx vite build && popd || goto :fail
)
.venv\Scripts\python.exe -m dubplates_client.main
exit /b 0
:fail
echo Something went wrong. See the messages above.
pause
exit /b 1
