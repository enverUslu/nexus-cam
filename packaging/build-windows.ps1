$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not on PATH. Install Python 3.11+ from python.org and enable 'Add python.exe to PATH'."
}

python -m pip install --upgrade pip
python -m pip install pyinstaller
python -m PyInstaller packaging\NexusCam.spec --clean --noconfirm

Write-Host ""
Write-Host "Built: dist\NexusCam\NexusCam.exe"
Write-Host "Run packaging\installer-windows.iss with Inno Setup to create the installer."
