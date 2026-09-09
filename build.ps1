$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) { python -m venv .venv }
& ./.venv/Scripts/python.exe -m pip install -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& ./.venv/Scripts/python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name SRT-Voice-Studio --collect-all edge_tts --collect-all imageio_ffmpeg desktop.py
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
Write-Host 'EXE: dist/SRT-Voice-Studio.exe'
