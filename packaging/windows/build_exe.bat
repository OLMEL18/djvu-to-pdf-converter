@echo off
setlocal

pushd "%~dp0..\.." || exit /b 1

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

set "VERSION_FILE=%CD%\packaging\windows\version_info.txt"
set "GUI_ENTRY=%CD%\packaging\windows\gui_entry.py"

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onedir ^
  --name djvu-to-pdf-converter ^
  --distpath dist ^
  --workpath build ^
  --specpath build ^
  --version-file "%VERSION_FILE%" ^
  "%GUI_ENTRY%"

set "exit_code=%ERRORLEVEL%"
popd
exit /b %exit_code%
