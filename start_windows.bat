@echo off
chcp 65001 >nul
title Репост Бот: Telegram ➔ MRIYU

echo ========================================================
echo   Репост Бот: Telegram ➔ MRIYU [Windows Launcher]
echo ========================================================
echo.
echo Оберіть інтерфейс для запуску:
echo [1] Web-панель [Сервер + Браузер, рекомендовано]
echo [2] Десктопний GUI [PySide6 вікно]
echo [3] Консольний CLI [Термінал]
echo.

set "choice=1"
set /p "choice=Введіть 1, 2 або 3 [за замовчуванням 1]: "

if "%choice%"=="1" goto run_web
if "%choice%"=="2" goto run_gui
if "%choice%"=="3" goto run_cli

echo.
echo Запуск Web-панелі...
goto run_web

:run_web
echo.
echo Запуск Web-сервера...
start http://localhost:8080
python run_server.py
goto end

:run_gui
echo.
echo Запуск Десктопного GUI...
python run_gui.py
goto end

:run_cli
echo.
echo Запуск Консольного CLI...
python run_cli.py
goto end

:end
pause
