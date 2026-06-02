@echo off
setlocal

pushd "%~dp0..\.." || exit /b 1

python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
  echo PyInstaller is not installed. Run: python -m pip install -r requirements-dev.txt
  popd
  exit /b 1
)

if exist build rmdir /s /q build
if not exist dist mkdir dist
if exist "dist\djvu-to-pdf-converter-0.1.0-win64.exe" del /q "dist\djvu-to-pdf-converter-0.1.0-win64.exe"

set "VERSION_FILE=%CD%\packaging\windows\version_info.txt"
set "GUI_ENTRY=%CD%\packaging\windows\gui_entry.py"

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onefile ^
  --name djvu-to-pdf-converter-0.1.0-win64 ^
  --distpath dist ^
  --workpath build ^
  --specpath build ^
  --version-file "%VERSION_FILE%" ^
  "%GUI_ENTRY%"

set "exit_code=%ERRORLEVEL%"
popd
exit /b %exit_code%
