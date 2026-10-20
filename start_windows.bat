@echo off
chcp 65001 >nul
title Репост Бот: Telegram ➔ MRIYU

echo ========================================================
echo   🤖 РЕПОСТ БОТ: TELEGRAM ➔ MRIYU (WINDOWS ЗАПУСК)
echo ========================================================
echo.
echo Оберіть інтерфейс для запуску:
echo [1] Web-інтерфейс (Сервер + Браузер, рекомендовано)
echo [2] Десктопний GUI (PySide6 вікно)
echo [3] Консольний CLI (Термінал)
echo.
set /p choice="Введіть 1, 2 або 3: "

if "%choice%"=="1" (
    echo.
    echo Запуск Веб-сервера...
    start http://localhost:8080
    python run_server.py
) else if "%choice%"=="2" (
    echo.
    echo Запуск Графічного інтерфейсу (GUI)...
    python run_gui.py
) else if "%choice%"=="3" (
    echo.
    echo Запуск Консольного інтерфейсу (CLI)...
    python run_cli.py
) else (
    echo Невірний вибір. Запускаємо Web-інтерфейс за замовчуванням...
    start http://localhost:8080
    python run_server.py
)

pause

