"""
Command Line Interface (CLI) for Repost Bot MRIYU.
Supports direct terminal commands and an interactive menu.
"""

from __future__ import annotations
import sys
import os
import time
import argparse

# Ensure proper UTF-8 stdout encoding in Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.config import ConfigManager
from core.database import Database
from core.engine import ReposterEngine
from core.mriyu_client import MriyuClient
from core.tg_scraper import TelegramScraper


def print_banner():
    print("""
======================================================
  🤖 РЕПОСТ БОТ: TELEGRAM ➔ MRIYU (CLI)
======================================================
    """)


def cmd_status(cm: ConfigManager, db: Database):
    cfg = cm.config
    stats = db.get_stats()
    print("\n--- ПОТОЧНИЙ СТАН ---")
    print(f"Telegram канал:        {cfg.telegram.channel or '(не вказано)'}")
    print(f"Режим зчитування:      {cfg.telegram.mode}")
    print(f"Інтервал перевірки:    {cfg.telegram.poll_interval} сек.")
    print(f"MRIYU ціль:            {cfg.mriyu.target_type} ID: {cfg.mriyu.target_id or '(не вказано)'}")
    print(f"Токен MRIYU:           {'налаштовано' if cfg.mriyu.token else '(не вказано)'}")
    print("\n--- СТАТИСТИКА ---")
    print(f"Всього оброблено:      {stats['total_processed']}")
    print(f"Успішно репостнуто:    {stats['reposted']}")
    print(f"Відфільтровано:        {stats['filtered']}")
    print(f"Помилок:               {stats['errors']}")
    print(f"Останній репост:       {stats['last_repost_time'] or 'ще не було'}")
    print("-" * 30 + "\n")


def cmd_logs(db: Database, limit: int = 20):
    logs = db.get_recent_logs(limit=limit)
    print(f"\n--- ОСТАННІ {limit} ЛОГІВ ---")
    if not logs:
        print("Журнал порожній.")
        return
    for l in reversed(logs):
        print(f"[{l['timestamp']}] [{l['level']}] {l['message']} {l['details']}")
    print("-" * 30 + "\n")


def cmd_test_mriyu(cm: ConfigManager, token: str = None):
    t = token or cm.config.mriyu.token
    if not t:
        print("❌ Помилка: токен MRIYU не вказано. Передайте токен аргументом або збережіть у config.json")
        return

    print("🔍 Перевірка токена в MRIYU Bot API...")
    client = MriyuClient(t)
    me = client.get_me()
    if not me.get("ok"):
        print(f"❌ Помилка: {me.get('description')} (код: {me.get('error_code')})")
        return

    bot = me.get("result", {})
    print(f"✅ З'єднання успішне! Бот: {bot.get('name')} (@{bot.get('username')})")
    print(f"   ID: {bot.get('id')} | Підписників: {bot.get('subscribers')} | Офіційний: {bot.get('verified')}")

    chats_res = client.get_chats()
    if chats_res.get("ok"):
        chats = chats_res.get("result", [])
        print(f"\nКанали та групи з цим ботом ({len(chats)}):")
        for ch in chats:
            print(f" - [{ch.get('type')}] '{ch.get('title')}' (chat_id: {ch.get('id')}, роль: {ch.get('role')})")
    else:
        print("Не вдалося отримати список чатів бота.")


def cmd_test_tg(channel: str):
    if not channel:
        print("❌ Помилка: вкажіть назву каналу (наприклад: python run_cli.py test-tg durov)")
        return

    clean = TelegramScraper.clean_channel_name(channel)
    print(f"🔍 Опитування публічного каналу https://t.me/s/{clean} ...")
    posts = TelegramScraper.fetch_channel_posts(clean)
    if not posts:
        print(f"❌ Не вдалося отримати пости з каналу '{clean}'. Перевірте публічність каналу.")
        return

    print(f"✅ Знайдено {len(posts)} постів. Останні пости:\n")
    for p in posts[-3:]:
        print(f"[{p.post_id}] {p.datetime_str}")
        print(f"Фото: {len(p.photos)} шт. | Посилання: {p.post_url}")
        snippet = (p.raw_text or "").replace("\n", " ")[:120]
        print(f"Текст: {snippet}...\n")


def cmd_run(cm: ConfigManager, db: Database):
    engine = ReposterEngine(cm, db)
    engine.start()
    print("▶ Рушій репостингу запущено у консольному режимі.")
    print("Натисніть Ctrl+C для зупинки.\n")

    last_log_id = 0
    try:
        while True:
            time.sleep(2)
            # Print new logs
            logs = db.get_recent_logs(limit=10)
            if logs:
                for l in reversed(logs):
                    if l['id'] > last_log_id:
                        print(f"[{l['timestamp']}] [{l['level']}] {l['message']}")
                        last_log_id = max(last_log_id, l['id'])
    except KeyboardInterrupt:
        print("\nЗупиняємо рушій...")
        engine.stop()
        print("Зупинено.")


def interactive_menu(cm: ConfigManager, db: Database):
    while True:
        print_banner()
        print("1. Поточний статус та статистика")
        print("2. Запустити фоновий рушій у терміналі")
        print("3. Перевірити Telegram канал")
        print("4. Перевірити MRIYU токен та канали")
        print("5. Переглянути останні логи")
        print("6. Швидке налаштування (канал, токен, chat_id)")
        print("0. Вихід")
        choice = input("\nОберіть дію [0-6]: ").strip()

        if choice == "1":
            cmd_status(cm, db)
        elif choice == "2":
            cmd_run(cm, db)
        elif choice == "3":
            ch = input("Введіть назву Telegram каналу: ").strip()
            cmd_test_tg(ch)
        elif choice == "4":
            t = input(f"Введіть токен MRIYU [{cm.config.mriyu.token}]: ").strip() or cm.config.mriyu.token
            cmd_test_mriyu(cm, t)
        elif choice == "5":
            cmd_logs(db, limit=20)
        elif choice == "6":
            ch = input(f"Telegram канал [{cm.config.telegram.channel}]: ").strip()
            tok = input(f"Токен MRIYU [{cm.config.mriyu.token}]: ").strip()
            cid = input(f"MRIYU chat_id [{cm.config.mriyu.target_id}]: ").strip()
            upd = {}
            if ch: upd.setdefault("telegram", {})["channel"] = ch
            if tok: upd.setdefault("mriyu", {})["token"] = tok
            if cid: upd.setdefault("mriyu", {})["target_id"] = cid
            if upd:
                cm.update(upd)
                print("✅ Налаштування збережено!")
        elif choice == "0":
            break
        input("\nНатисніть Enter для продовження...")


def main():
    cm = ConfigManager()
    db = Database()

    parser = argparse.ArgumentParser(description="CLI для Репост Бота MRIYU")
    subparsers = parser.add_subparsers(dest="subcommand", help="Команди")

    subparsers.add_parser("status", help="Показати статус та статистику")
    subparsers.add_parser("run", help="Запустити рушій в консолі")
    subparsers.add_parser("logs", help="Показати останні логи")

    tg_p = subparsers.add_parser("test-tg", help="Перевірити публічний TG канал")
    tg_p.add_argument("channel", nargs="?", default="", help="Назва каналу")

    mr_p = subparsers.add_parser("test-mriyu", help="Перевірити токен та чати в MRIYU")
    mr_p.add_argument("token", nargs="?", default="", help="Токен бота")

    args = parser.parse_args()

    if args.subcommand == "status":
        cmd_status(cm, db)
    elif args.subcommand == "run":
        cmd_run(cm, db)
    elif args.subcommand == "logs":
        cmd_logs(db)
    elif args.subcommand == "test-tg":
        ch = args.channel or cm.config.telegram.channel
        cmd_test_tg(ch)
    elif args.subcommand == "test-mriyu":
        cmd_test_mriyu(cm, args.token)
    else:
        interactive_menu(cm, db)


if __name__ == "__main__":
    main()
