# Build GamerScroll as a single .exe using PyInstaller.
# Run from the repository root.

$ErrorActionPreference = "Stop"
$venvPython = ".\.venv\Scripts\python.exe"

# Ensure PyInstaller is available.
& $venvPython -m pip install pyinstaller

# Generate icon if it doesn't exist.
if (-not (Test-Path "assets\icon.ico")) {
    & $venvPython scripts\make_icon.py
}

# Clean previous build artifacts.
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist, build

# Build.
& $venvPython -m PyInstaller GamerScroll.spec --clean

Write-Host "Build complete. Output: dist\GamerScroll.exe" -ForegroundColor Green
