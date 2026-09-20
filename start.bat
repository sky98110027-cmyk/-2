@echo off
chcp 65001 >nul
rem 윈도우에서 두 번 눌러 켜는 파일.
rem 오류가 나면 창이 안 닫히고 이유를 보여준다.
title 결 (Gyeol)
cd /d "%~dp0"

set "PYCMD="

where py >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD (
  where python >nul 2>nul && set "PYCMD=python"
)

if not defined PYCMD (
  echo.
  echo  파이썬이 안 깔려 있습니다.
  echo.
  echo  1. python.org/downloads 에서 받아 깔아주세요.
  echo  2. 깔 때 맨 아래 "Add Python to PATH" 에 꼭 체크하세요.
  echo  3. 다 깔았으면 이 파일을 다시 눌러주세요.
  echo.
  pause
  exit /b 1
)

%PYCMD% start.py
set "CODE=%errorlevel%"

if not "%CODE%"=="0" (
  echo.
  echo  ────────────────────────────────────────────
  echo   멈췄습니다. 위에 적힌 글을 확인해주세요.
  echo   그대로 알려주시면 같이 풀 수 있습니다.
  echo  ────────────────────────────────────────────
  echo.
  pause
)

exit /b %CODE%
