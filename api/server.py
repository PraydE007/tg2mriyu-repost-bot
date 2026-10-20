"""
Zero-dependency HTTP Web Server and REST API for Repost Bot MRIYU.
Uses Python's standard library (http.server.ThreadingHTTPServer).
Runs 100% out of the box on Android (Termux with Python 3.14+), Linux, Windows, macOS
without needing Rust, C compilers, FastAPI, Uvicorn, or Pydantic.
"""

from __future__ import annotations
import os
import json
import mimetypes
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

from core.config import ConfigManager
from core.database import Database
from core.engine import ReposterEngine
from core.mriyu_client import MriyuClient
from core.tg_scraper import TelegramScraper
from core.tg_telethon import TelethonService

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


class BotRequestHandler(BaseHTTPRequestHandler):
    # Bound by factory: engine, config_manager, database
    engine: ReposterEngine
    config_manager: ConfigManager
    database: Database

    def log_message(self, format, *args):
        # Suppress verbose default access logs to keep console clean
        pass

    def send_json(self, data: Any, status: int = 200):
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(content)

    def read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # API Routes
        if path == "/api/status":
            self.send_json(self.engine.get_status())
            return

        if path == "/api/config":
            self.send_json(self.config_manager.config.to_dict())
            return

        if path == "/api/logs":
            limit = int(query.get("limit", [100])[0])
            level = query.get("level", [None])[0]
            self.send_json(self.database.get_recent_logs(limit=limit, level=level))
            return

        if path == "/api/posts":
            limit = int(query.get("limit", [50])[0])
            self.send_json(self.database.get_recent_posts(limit=limit))
            return

        if path == "/api/telethon/status":
            cfg = self.config_manager.config
            service = TelethonService.get_instance(cfg.telegram.session_name or "telethon_session")
            api_id = query.get("api_id", [cfg.telegram.api_id])[0]
            api_hash = query.get("api_hash", [cfg.telegram.api_hash])[0]
            status = service.get_status(api_id=api_id, api_hash=api_hash)
            self.send_json(status)
            return

        # Static file serving
        self.serve_static(path)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/engine/start":
            self.engine.start()
            self.send_json({"ok": True, "message": "Рушій успішно запущено"})
            return

        if path == "/api/engine/stop":
            self.engine.stop()
            self.send_json({"ok": True, "message": "Рушій зупинено"})
            return

        if path == "/api/engine/trigger":
            self.engine.trigger_manual_check()
            self.send_json({"ok": True, "message": "Позачергову перевірку запущено"})
            return

        if path == "/api/config":
            payload = self.read_json_body()
            updated = self.config_manager.update(payload)
            self.database.add_log("INFO", "Оновлено конфігурацію бота через Web UI")
            self.send_json({"ok": True, "config": updated.to_dict()})
            return

        if path == "/api/logs/clear":
            self.database.clear_logs()
            self.send_json({"ok": True, "message": "Журнал логів очищено"})
            return

        if path == "/api/posts/clear":
            self.database.clear_processed_posts()
            self.database.add_log("WARNING", "Історію оброблених постів скинуто")
            self.send_json({"ok": True, "message": "Історію оброблених постів очищено"})
            return

        # Telethon Endpoints
        if path == "/api/telethon/send_code":
            payload = self.read_json_body()
            cfg = self.config_manager.config
            phone = (payload.get("phone") or cfg.telegram.phone or "").strip()
            api_id = (payload.get("api_id") or cfg.telegram.api_id or "").strip()
            api_hash = (payload.get("api_hash") or cfg.telegram.api_hash or "").strip()

            if not api_id or not api_hash:
                self.send_json({"ok": False, "error": "Вкажіть api_id та api_hash"}, 400)
                return
            if not phone:
                self.send_json({"ok": False, "error": "Вкажіть номер телефону"}, 400)
                return

            service = TelethonService.get_instance(cfg.telegram.session_name or "telethon_session")
            res = service.send_auth_code(phone=phone, api_id=api_id, api_hash=api_hash)
            if res.get("ok"):
                self.config_manager.update({
                    "telegram": {
                        "api_id": api_id,
                        "api_hash": api_hash,
                        "phone": phone
                    }
                })
            self.send_json(res)
            return

        if path == "/api/telethon/sign_in":
            payload = self.read_json_body()
            cfg = self.config_manager.config
            phone = (payload.get("phone") or cfg.telegram.phone or "").strip()
            code = (payload.get("code") or "").strip()
            phone_code_hash = (payload.get("phone_code_hash") or "").strip()
            password = (payload.get("password") or "").strip()
            api_id = (payload.get("api_id") or cfg.telegram.api_id or "").strip()
            api_hash = (payload.get("api_hash") or cfg.telegram.api_hash or "").strip()

            service = TelethonService.get_instance(cfg.telegram.session_name or "telethon_session")
            res = service.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash,
                password=password,
                api_id=api_id,
                api_hash=api_hash
            )
            if res.get("ok"):
                self.config_manager.update({
                    "telegram": {
                        "mode": "telethon",
                        "api_id": api_id,
                        "api_hash": api_hash,
                        "phone": phone
                    }
                })
                self.database.add_log("SUCCESS", f"Telethon успішно авторизовано: {res.get('message')}")
            self.send_json(res)
            return

        if path == "/api/telethon/sign_in_bot":
            payload = self.read_json_body()
            cfg = self.config_manager.config
            bot_token = (payload.get("bot_token") or cfg.telegram.bot_token or "").strip()
            api_id = (payload.get("api_id") or cfg.telegram.api_id or "").strip()
            api_hash = (payload.get("api_hash") or cfg.telegram.api_hash or "").strip()

            service = TelethonService.get_instance(cfg.telegram.session_name or "telethon_session")
            res = service.sign_in_bot(bot_token=bot_token, api_id=api_id, api_hash=api_hash)
            if res.get("ok"):
                self.config_manager.update({
                    "telegram": {
                        "mode": "telethon",
                        "api_id": api_id,
                        "api_hash": api_hash,
                        "bot_token": bot_token
                    }
                })
                self.database.add_log("SUCCESS", f"Telethon (Bot) успішно авторизовано: {res.get('message')}")
            self.send_json(res)
            return

        if path == "/api/telethon/logout":
            cfg = self.config_manager.config
            service = TelethonService.get_instance(cfg.telegram.session_name or "telethon_session")
            res = service.logout()
            self.database.add_log("WARNING", "Сесію Telethon скинуто")
            self.send_json(res)
            return

        if path == "/api/test/mriyu":
            payload = self.read_json_body()
            token = (payload.get("token") or "").strip()
            if not token:
                self.send_json({"ok": False, "error": "Токен не може бути порожнім"}, 400)
                return

            client = MriyuClient(token)
            me_res = client.get_me()
            if not me_res.get("ok"):
                self.send_json({
                    "ok": False,
                    "error": me_res.get("description", "Не вдалося з'єднатися з MRIYU Bot API"),
                    "error_code": me_res.get("error_code")
                })
                return

            chats_res = client.get_chats()
            chats = chats_res.get("result", []) if chats_res.get("ok") else []
            self.send_json({
                "ok": True,
                "bot": me_res.get("result"),
                "chats": chats
            })
            return

        if path == "/api/test/telegram":
            payload = self.read_json_body()
            cfg = self.config_manager.config
            channel = (payload.get("channel") or cfg.telegram.channel or "").strip()
            mode = (payload.get("mode") or cfg.telegram.mode or "scraper").strip()
            api_id = (payload.get("api_id") or cfg.telegram.api_id or "").strip()
            api_hash = (payload.get("api_hash") or cfg.telegram.api_hash or "").strip()

            if not channel:
                self.send_json({"ok": False, "message": "Вкажіть назву або посилання на Telegram канал"}, 400)
                return

            if mode == "telethon":
                service = TelethonService.get_instance(cfg.telegram.session_name or "telethon_session")
                try:
                    posts = service.fetch_channel_posts(channel_input=channel, limit=5, api_id=api_id, api_hash=api_hash)
                    if not posts:
                        self.send_json({
                            "ok": False,
                            "channel": channel,
                            "message": "Telethon не повернув постів з цього чату/каналу (перевірте, чи є ви учасником або чи є повідомлення)."
                        })
                        return
                    self.send_json({
                        "ok": True,
                        "channel": channel,
                        "count": len(posts),
                        "posts": [p.to_dict() for p in posts[-5:]]
                    })
                    return
                except Exception as e:
                    self.send_json({
                        "ok": False,
                        "channel": channel,
                        "message": f"Помилка Telethon: {str(e)}"
                    })
                    return

            # Scraper mode
            posts = TelegramScraper.fetch_channel_posts(channel)
            if not posts:
                self.send_json({
                    "ok": False,
                    "channel": channel,
                    "message": "Не вдалося отримати пости. Перевірте, чи канал є публічним та чи правильно введено назву (для приватних каналів оберіть режим Telethon)."
                })
                return

            self.send_json({
                "ok": True,
                "channel": TelegramScraper.clean_channel_name(channel),
                "count": len(posts),
                "posts": [p.to_dict() for p in posts[-5:]]
            })
            return

        self.send_json({"error": "Endpoint not found"}, 404)

    def serve_static(self, path: str):
        if path in ("", "/"):
            filepath = os.path.join(WEB_DIR, "index.html")
        elif path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            filepath = os.path.join(WEB_DIR, rel_path)
        else:
            filepath = os.path.join(WEB_DIR, path.lstrip("/"))

        # Prevent directory traversal
        norm_file = os.path.abspath(filepath)
        norm_dir = os.path.abspath(WEB_DIR)
        if not norm_file.startswith(norm_dir) or not os.path.isfile(norm_file):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"File not found")
            return

        content_type, _ = mimetypes.guess_type(norm_file)
        if not content_type:
            content_type = "application/octet-stream"

        try:
            with open(norm_file, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8" if "text" in content_type or "javascript" in content_type else content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))


def create_server(engine: ReposterEngine, config_manager: ConfigManager, database: Database, host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:
    """Create and return configured ThreadingHTTPServer instance."""
    class CustomHandler(BotRequestHandler):
        pass

    CustomHandler.engine = engine
    CustomHandler.config_manager = config_manager
    CustomHandler.database = database

    return ThreadingHTTPServer((host, port), CustomHandler)
