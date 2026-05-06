@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR="
set "PUSHD_DONE=0"
set "EXIT_CODE=0"

if not "%PHONETOOL_HOME%"=="" set "ROOT_DIR=%PHONETOOL_HOME%"
if not "%~3"=="" set "ROOT_DIR=%~3"
if "%ROOT_DIR%"=="" set "ROOT_DIR=%SCRIPT_DIR%"

if exist "%ROOT_DIR%\backend\main.py" goto root_found

set "CURRENT_DIR=%SCRIPT_DIR%"
:find_root
if exist "%CURRENT_DIR%\backend\main.py" (
  set "ROOT_DIR=%CURRENT_DIR%"
  goto root_found
)
for %%A in ("%CURRENT_DIR%\..") do set "PARENT_DIR=%%~fA"
if /I "%PARENT_DIR%"=="%CURRENT_DIR%" goto root_not_found
set "CURRENT_DIR=%PARENT_DIR%"
goto find_root

:root_not_found
echo [ERROR] Project root not found.
echo Put start_windows.bat in the project root, pass the project path, or set PHONETOOL_HOME.
echo Usage: start_windows.bat [PORT] [DB_FILE] [PROJECT_DIR]
echo Example: start_windows.bat 8090 app.db G:\devicestool\Devices-Platform
set "EXIT_CODE=1"
goto finish

:root_found
pushd "%ROOT_DIR%"
if errorlevel 1 (
  echo [ERROR] Failed to enter project root: "%ROOT_DIR%"
  set "EXIT_CODE=1"
  goto finish
)
set "PUSHD_DONE=1"

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8090"

set "DB_FILE=%~2"
if "%DB_FILE%"=="" set "DB_FILE=app.db"

if exist ".env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" set "%%A=%%B"
  )
)

set "REQUIREMENTS=requirements.txt"
if exist "%REQUIREMENTS%" (
  echo Checking dependencies in %REQUIREMENTS%...
  python -m pip install -r "%REQUIREMENTS%"
  if errorlevel 1 (
    echo Failed to install requirements.
    set "EXIT_CODE=1"
    goto finish
  )
) else (
  echo requirements.txt not found, skip dependency install.
)

if not exist "%ROOT_DIR%\frontend\package.json" (
  echo [ERROR] frontend\package.json not found.
  set "EXIT_CODE=1"
  goto finish
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm not found. Please install Node.js and ensure npm is in PATH.
  set "EXIT_CODE=1"
  goto finish
)

echo Building frontend...
pushd "%ROOT_DIR%\frontend"
if errorlevel 1 (
  echo [ERROR] Failed to enter frontend directory: "%ROOT_DIR%\frontend"
  set "EXIT_CODE=1"
  goto finish
)
call npm run build
set "BUILD_EXIT_CODE=%ERRORLEVEL%"
popd
if not "%BUILD_EXIT_CODE%"=="0" (
  echo Frontend build failed.
  set "EXIT_CODE=%BUILD_EXIT_CODE%"
  goto finish
)

set "APP_DB_FILE=%DB_FILE%"
echo Starting API on port %PORT% using %DB_FILE%

python -m uvicorn backend.main:app --host 0.0.0.0 --port %PORT%
set "EXIT_CODE=%ERRORLEVEL%"
goto finish

:finish
if "%PUSHD_DONE%"=="1" popd
if not "%EXIT_CODE%"=="0" (
  echo.
  echo [ERROR] Script stopped with exit code %EXIT_CODE%.
  echo Press any key to close this window...
  pause >nul
)
endlocal & exit /b %EXIT_CODE%
