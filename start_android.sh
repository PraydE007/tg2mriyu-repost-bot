#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Скрипт швидкого запуску Репост Бота MRIYU на Android (Termux)
# ==============================================================================

echo "----------------------------------------------------"
echo "🤖 Запуск Репост Бота Telegram ➔ MRIYU на Android"
echo "----------------------------------------------------"

# Перевірка наявності Python
if ! command -v python &> /dev/null; then
    echo "📦 Python не знайдено. Встановлюємо python..."
    pkg update -y && pkg install python -y
fi

# Встановлення необхідних залежностей
echo "📦 Перевірка та встановлення залежностей..."
pip install -r requirements.txt --quiet

PORT=8080

echo ""
echo "🚀 Запускаємо фоновий сервер..."
echo "📱 Веб-панель керування: http://localhost:${PORT}"
echo ""

# Автоматичне відкриття у браузері, якщо доступний termux-open-url
if command -v termux-open-url &> /dev/null; then
    sleep 2 && termux-open-url "http://localhost:${PORT}" &
fi

# Запуск сервера
python run_server.py --host 0.0.0.0 --port ${PORT}

