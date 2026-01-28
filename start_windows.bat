@echo off
setlocal

set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

set PORT=%1
if "%PORT%"=="" set PORT=8090

set DB_FILE=%2
if "%DB_FILE%"=="" set DB_FILE=app.db

set REQUIREMENTS=requirements.txt
if exist "%REQUIREMENTS%" (
  echo Checking dependencies in %REQUIREMENTS%...
  python -m pip install -r "%REQUIREMENTS%"
  if errorlevel 1 (
    echo Failed to install requirements.
    popd
    exit /b 1
  )
) else (
  echo requirements.txt not found, skip dependency install.
)

set APP_DB_FILE=%DB_FILE%
echo Starting API on port %PORT% using %DB_FILE%

python -m uvicorn backend.main:app --host 0.0.0.0 --port %PORT%

popd
endlocal
