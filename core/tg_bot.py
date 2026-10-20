"""
Telegram Bot API integration (alternative to web scraper).
Fetches channel posts using official Telegram Bot API if the bot is added as an administrator.
"""

from __future__ import annotations
import requests
from typing import List, Optional, Dict, Any
from .tg_scraper import TelegramPost


class TelegramBotClient:
    def __init__(self, bot_token: str, timeout: int = 15):
        self.bot_token = bot_token.strip()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/"
        self.file_base_url = f"https://api.telegram.org/file/bot{self.bot_token}/"
        self.timeout = timeout

    def get_updates(self, offset: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        url = f"{self.base_url}getUpdates"
        params: Dict[str, Any] = {
            "allowed_updates": ["channel_post"],
            "limit": limit
        }
        if offset is not None:
            params["offset"] = offset

        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            data = resp.json()
            if data.get("ok"):
                return data.get("result", [])
        except Exception as e:
            print(f"[TelegramBotClient] getUpdates error: {e}")

        return []

    def get_file_bytes(self, file_id: str) -> Optional[bytes]:
        try:
            resp = requests.get(f"{self.base_url}getFile", params={"file_id": file_id}, timeout=self.timeout)
            data = resp.json()
            if data.get("ok"):
                file_path = data["result"]["file_path"]
                dl_url = f"{self.file_base_url}{file_path}"
                dl_resp = requests.get(dl_url, timeout=self.timeout + 10)
                if dl_resp.status_code == 200:
                    return dl_resp.content
        except Exception as e:
            print(f"[TelegramBotClient] get_file_bytes error: {e}")
        return None

