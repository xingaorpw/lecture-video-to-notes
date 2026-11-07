@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set "SKILL_DIR=%~dp0.."
set "PY=%SKILL_DIR%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo venv not found. Run: powershell -ExecutionPolicy Bypass -File "%SKILL_DIR%\scripts\setup.ps1"
  exit /b 2
)
"%PY%" "%SKILL_DIR%\scripts\lecture.py" %*
exit /b %ERRORLEVEL%
