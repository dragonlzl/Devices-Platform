@echo off
setlocal

set SCRIPT_DIR=%~dp0
set ROOT_DIR=

if not "%PHONETOOL_HOME%"=="" set ROOT_DIR=%PHONETOOL_HOME%
if not "%3"=="" set ROOT_DIR=%~3
if "%ROOT_DIR%"=="" set ROOT_DIR=%SCRIPT_DIR%

if not exist "%ROOT_DIR%\backend\main.py" (
  set CURRENT_DIR=%SCRIPT_DIR%
  :find_root
  if exist "%CURRENT_DIR%\backend\main.py" (
    set ROOT_DIR=%CURRENT_DIR%
    goto root_found
  )
  for %%A in ("%CURRENT_DIR%\..") do set PARENT_DIR=%%~fA
  if "%PARENT_DIR%"=="%CURRENT_DIR%" goto root_not_found
  set CURRENT_DIR=%PARENT_DIR%
  goto find_root
  :root_not_found
  echo [ERROR] 未找到项目目录。
  echo 请将 start_windows.bat 放在项目根目录，或传入项目路径:
  echo   start_windows.bat [PORT] [DB_FILE] [PROJECT_DIR]
  echo 或设置环境变量 PHONETOOL_HOME。
  pause
  exit /b 1
)
:root_found

pushd "%ROOT_DIR%"

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
    pause
    popd
    exit /b 1
  )
) else (
  echo requirements.txt not found, skip dependency install.
)

set APP_DB_FILE=%DB_FILE%
echo Starting API on port %PORT% using %DB_FILE%

python -m uvicorn backend.main:app --host 0.0.0.0 --port %PORT%
set EXIT_CODE=%ERRORLEVEL%
if not "%EXIT_CODE%"=="0" pause

popd
endlocal
exit /b %EXIT_CODE%
