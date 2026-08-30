@echo off
setlocal
cd /d "%~dp0"
title Dashboard theo doi thi CDR SV TTV DHDN

where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py"
) else (
  where python >nul 2>&1
  if %errorlevel%==0 (
    set "PY=python"
  ) else (
    echo.
    echo [LOI] Chua tim thay Python.
    echo Hay cai Python 3.10+ va chon "Add Python to PATH" khi cai dat.
    echo.
    pause
    exit /b 1
  )
)

if not exist "venv\Scripts\python.exe" (
  echo [1/3] Dang tao moi truong chay lan dau...
  %PY% -m venv venv
  if errorlevel 1 goto :error
)

if not exist "venv\Scripts\python.exe" goto :error

echo [2/3] Dang kiem tra/cai thu vien...
"venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo.
  echo [LOI] Khong cai duoc thu vien. Kiem tra Internet va thu lai.
  pause
  exit /b 1
)

echo [3/3] Dang khoi dong Dashboard...
start "" "http://127.0.0.1:5000"
"venv\Scripts\python.exe" app.py

if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo [LOI] Khong the khoi dong Dashboard.
echo Thu muc hien tai: %CD%
echo.
pause
exit /b 1
