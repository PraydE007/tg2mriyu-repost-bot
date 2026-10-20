"""
Main server runner: boots the background ReposterEngine and Web server.
Uses Python's standard library (ThreadingHTTPServer) — ZERO external server dependencies!
Runs seamlessly on Android (Termux with Python 3.14+), Linux VPS, macOS, or Windows.
"""

from __future__ import annotations
import sys
import os
import argparse
import socket

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.config import ConfigManager
from core.database import Database
from core.engine import ReposterEngine
from api.server import create_server


def get_local_ip() -> str:
    """Detect LAN IP address to display link for mobile / local network devices."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    parser = argparse.ArgumentParser(description="Запуск фонового сервера та веб-інтерфейсу Репост Бота")
    parser.add_argument("--host", type=str, default=None, help="IP адреса для прослуховування (за замовчуванням 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="Порт веб-сервера (за замовчуванням 8080)")
    parser.add_argument("--no-auto-start", action="store_true", help="Не запускати рушій репостингу автоматично при старті")
    args = parser.parse_args()

    config_manager = ConfigManager()
    database = Database()
    engine = ReposterEngine(config_manager, database)

    host = args.host or config_manager.config.server.host or "0.0.0.0"
    port = args.port or config_manager.config.server.port or 8080

    # Auto-start engine if configured
    if config_manager.config.server.auto_start and not args.no_auto_start:
        engine.start()

    server = create_server(engine, config_manager, database, host=host, port=port)
    local_ip = get_local_ip()

    print("\n" + "=" * 65)
    print("🚀  РЕПОСТ БОТ: TELEGRAM ➔ MRIYU ЗАПУЩЕНО!")
    print("=" * 65)
    print(f"📡  Локальний веб-інтерфейс:     http://localhost:{port}")
    if host == "0.0.0.0":
        print(f"📱  Доступ з Android / мережі:   http://{local_ip}:{port}")
    print(f"⚙️   Статус фонового рушія:       {'АКТИВНИЙ ▶' if engine.is_running else 'ЗУПИНЕНО ⏹'}")
    print("=" * 65)
    print("💡  Відкрийте посилання у браузері на смартфоні чи комп'ютері.")
    print("    Натисніть Ctrl+C для зупинки.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОтримано сигнал зупинки...")
    finally:
        server.shutdown()
        server.server_close()
        if engine.is_running:
            print("Зупиняємо рушій...")
            engine.stop()
        print("Сервер успішно зупинено.")


if __name__ == "__main__":
    main()
