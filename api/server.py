"""
FastAPI Server providing REST API endpoints and serving the Web UI.
Enables full remote management from web browser (desktop, tablet, or Android smartphone).
"""

from __future__ import annotations
import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from core.config import ConfigManager
from core.database import Database
from core.engine import ReposterEngine
from core.mriyu_client import MriyuClient
from core.tg_scraper import TelegramScraper

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

def create_app(engine: ReposterEngine, config_manager: ConfigManager, database: Database) -> FastAPI:
    app = FastAPI(title="Repost Bot MRIYU", version="1.0.0")

    # API Routes
    @app.get("/api/status")
    def get_status():
        return engine.get_status()

    @app.post("/api/engine/start")
    def start_engine():
        engine.start()
        return {"ok": True, "message": "Рушій успішно запущено"}

    @app.post("/api/engine/stop")
    def stop_engine():
        engine.stop()
        return {"ok": True, "message": "Рушій зупинено"}

    @app.post("/api/engine/trigger")
    def trigger_check():
        engine.trigger_manual_check()
        return {"ok": True, "message": "Позачергову перевірку запущено"}

    @app.get("/api/config")
    def get_config():
        return config_manager.config.to_dict()

    @app.post("/api/config")
    def update_config(payload: Dict[str, Any]):
        updated = config_manager.update(payload)
        database.add_log("INFO", "Оновлено конфігурацію бота через Web UI")
        return {"ok": True, "config": updated.to_dict()}

    @app.get("/api/logs")
    def get_logs(limit: int = 100, level: Optional[str] = None):
        return database.get_recent_logs(limit=limit, level=level)

    @app.post("/api/logs/clear")
    def clear_logs():
        database.clear_logs()
        return {"ok": True, "message": "Журнал логів очищено"}

    @app.get("/api/posts")
    def get_posts(limit: int = 50):
        return database.get_recent_posts(limit=limit)

    @app.post("/api/posts/clear")
    def clear_posts():
        database.clear_processed_posts()
        database.add_log("WARNING", "Історію оброблених постів скинуто")
        return {"ok": True, "message": "Історію оброблених постів очищено"}

    class TestMriyuRequest(BaseModel):
        token: str

    @app.post("/api/test/mriyu")
    def test_mriyu(req: TestMriyuRequest):
        token = req.token.strip()
        if not token:
            raise HTTPException(status_code=400, detail="Токен не може бути порожнім")

        client = MriyuClient(token)
        me_res = client.get_me()
        if not me_res.get("ok"):
            return {
                "ok": False,
                "error": me_res.get("description", "Не вдалося з'єднатися з MRIYU Bot API"),
                "error_code": me_res.get("error_code")
            }

        chats_res = client.get_chats()
        chats = chats_res.get("result", []) if chats_res.get("ok") else []

        return {
            "ok": True,
            "bot": me_res.get("result"),
            "chats": chats
        }

    class TestTelegramRequest(BaseModel):
        channel: str

    @app.post("/api/test/telegram")
    def test_telegram(req: TestTelegramRequest):
        ch = req.channel.strip()
        if not ch:
            raise HTTPException(status_code=400, detail="Вкажіть назву Telegram каналу")

        posts = TelegramScraper.fetch_channel_posts(ch)
        if not posts:
            return {
                "ok": False,
                "channel": ch,
                "message": "Не вдалося отримати пости. Перевірте, чи канал є публічним та чи правильно введено назву."
            }

        return {
            "ok": True,
            "channel": TelegramScraper.clean_channel_name(ch),
            "count": len(posts),
            "posts": [p.to_dict() for p in posts[-5:]]  # return last 5 posts
        }

    # Static Web UI files
    if os.path.exists(WEB_DIR):
        app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

        @app.get("/")
        def serve_index():
            return FileResponse(os.path.join(WEB_DIR, "index.html"))

    return app

