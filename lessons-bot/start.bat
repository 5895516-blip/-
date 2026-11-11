@echo off
chcp 65001 >nul
title Бот с уроками
cd /d "%~dp0"
set PYTHONUTF8=1

if not exist ".env" (
  echo Нет файла .env с настройками. Скопируй .env.example в .env и впиши токен бота.
  pause
  exit /b 1
)

set PY=
py -3 --version >nul 2>nul && set PY=py -3
if not defined PY (
  python -c "import sys" >nul 2>nul && set PY=python
)
if not defined PY (
  echo Python не найден.
  echo Скачай его с https://www.python.org/downloads/ и при установке поставь галочку "Add python.exe to PATH".
  echo Потом запусти этот файл ещё раз.
  pause
  exit /b 1
)

echo Бот запускается. Это окно не закрывай: пока оно открыто, бот работает.
echo Панель управления: отправь боту в Telegram команду /panel
echo.
%PY% main.py
echo.
echo Бот остановлен.
pause
