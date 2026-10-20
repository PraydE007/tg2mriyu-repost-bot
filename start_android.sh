#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Скрипт запуску Репост Бота MRIYU на Android (Termux)
# ==============================================================================

set -e

echo "----------------------------------------------------"
echo "🤖 Запуск Репост Бота Telegram ➔ MRIYU на Android"
echo "----------------------------------------------------"

# Перевірка та встановлення python
if ! command -v python >/dev/null 2>&1; then
    echo "📦 Встановлення python..."
    pkg update -y && pkg install -y python
fi

# Встановлення єдиної необхідної залежності (requests)
# Більше ніяких проблем з pydantic, rust чи PySide6!
echo "📦 Перевірка бібліотеки requests..."
pip install -r requirements.txt --quiet

PORT=8080

echo ""
echo "🚀 Запуск фонового веб-сервера..."
echo "📱 Адреса панелі керування: http://localhost:${PORT}"
echo ""

# Автоматичне відкриття у браузері, якщо доступний termux-open-url
if command -v termux-open-url >/dev/null 2>&1; then
    (sleep 2 && termux-open-url "http://localhost:${PORT}") &
fi

# Запуск сервера
python run_server.py --host 0.0.0.0 --port ${PORT}
