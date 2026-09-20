@echo off
chcp 65001 >nul
rem 윈도우에서 두 번 눌러 켜는 파일.
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 start.py
  goto end
)

where python >nul 2>nul
if %errorlevel%==0 (
  python start.py
  goto end
)

echo.
echo 파이썬이 안 깔려 있습니다.
echo python.org 에서 받아 깔아주신 뒤 다시 눌러주세요.
echo.
pause

:end
