"""
Configuration management for Repost Bot MRIYU.
Loads and saves settings from data/config.json with safe defaults.
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "config.json"
)


@dataclass
class TextReplacement:
    find: str = ""
    replace: str = ""
    is_regex: bool = False


@dataclass
class TelegramConfig:
    channel: str = ""  # channel username or link (e.g. 'durov' or 'https://t.me/durov')
    mode: str = "scraper"  # 'scraper' (public t.me/s), 'bot_api', or 'telethon'
    bot_token: str = ""  # optional: telegram bot token if using bot_api
    poll_interval: int = 60  # seconds between checks
    initial_sync_count: int = 3  # how many recent posts to sync on first run (0 = only future posts)
    # Telethon client settings
    api_id: str = ""  # Telegram API ID from https://my.telegram.org
    api_hash: str = ""  # Telegram API Hash from https://my.telegram.org
    phone: str = ""  # Phone number with country code (e.g. +380991234567)
    session_name: str = "telethon_session"  # Session name stored in data/


@dataclass
class FilterConfig:
    keyword_blacklist: List[str] = field(default_factory=list)  # skip post if contains any of these
    keyword_whitelist: List[str] = field(default_factory=list)  # only repost if contains any of these (if empty, allow all)
    min_length: int = 0  # minimum character length
    max_length: int = 0  # maximum character length (0 = no limit)
    ignore_forwards: bool = False  # skip forwarded posts
    allow_photos: bool = True  # repost photos
    allow_text_only: bool = True  # repost text-only posts
    skip_links: bool = False  # skip posts that have external links


@dataclass
class FormattingConfig:
    header_prefix: str = ""  # e.g. "📢 З каналу:"
    footer_suffix: str = ""  # e.g. "---"
    add_source_link: bool = True  # append [Джерело в Telegram](https://t.me/channel/123)
    source_link_text: str = "Джерело в Telegram"
    remove_urls: bool = False  # strip all URLs from post text
    remove_hashtags: bool = False  # strip #hashtags
    convert_markdown: bool = True  # convert HTML/TG tags to MRIYU markdown (**bold**, __italic__, etc.)
    replacements: List[Dict[str, Any]] = field(default_factory=list)  # list of {"find": "...", "replace": "..."}


@dataclass
class MriyuConfig:
    token: str = ""  # Bearer token from https://mriyu.com/developers?bots
    target_type: str = "chat"  # 'chat' (channel or group) or 'user' (direct)
    target_id: str = ""  # chat_id (e.g. 7 or "7") or user_id
    silent: bool = False  # post without sound notification
    add_button: bool = False  # attach inline button below post
    button_text: str = "Оригінал посту"
    button_url: str = ""  # if empty and add_button=True, uses original TG link


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"  # 0.0.0.0 allows access from phone browser over Wi-Fi / Termux localhost
    port: int = 8080
    auto_start: bool = True  # auto-start reposter engine when server boots


@dataclass
class AppConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)
    formatting: FormattingConfig = field(default_factory=FormattingConfig)
    mriyu: MriyuConfig = field(default_factory=MriyuConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppConfig:
        tg_data = data.get("telegram", {})
        flt_data = data.get("filter", {})
        fmt_data = data.get("formatting", {})
        mr_data = data.get("mriyu", {})
        srv_data = data.get("server", {})

        return cls(
            telegram=TelegramConfig(**{k: v for k, v in tg_data.items() if k in TelegramConfig.__annotations__}),
            filter=FilterConfig(**{k: v for k, v in flt_data.items() if k in FilterConfig.__annotations__}),
            formatting=FormattingConfig(**{k: v for k, v in fmt_data.items() if k in FormattingConfig.__annotations__}),
            mriyu=MriyuConfig(**{k: v for k, v in mr_data.items() if k in MriyuConfig.__annotations__}),
            server=ServerConfig(**{k: v for k, v in srv_data.items() if k in ServerConfig.__annotations__}),
        )


class ConfigManager:
    """Thread-safe manager for loading, updating, and saving configuration."""

    def __init__(self, filepath: str = DEFAULT_CONFIG_PATH):
        self.filepath = filepath
        self._ensure_dir()
        self.config: AppConfig = self.load()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

    def load(self) -> AppConfig:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.config = AppConfig.from_dict(data)
                return self.config
            except Exception as e:
                print(f"[Config] Error loading config from {self.filepath}: {e}, using defaults.")
        self.config = AppConfig()
        self.save()
        return self.config

    def save(self) -> bool:
        self._ensure_dir()
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[Config] Error saving config: {e}")
            return False

    def update(self, new_data: Dict[str, Any]) -> AppConfig:
        current_dict = self.config.to_dict()

        def deep_update(d, u):
            for k, v in u.items():
                if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                    deep_update(d[k], v)
                else:
                    d[k] = v

        deep_update(current_dict, new_data)
        self.config = AppConfig.from_dict(current_dict)
        self.save()
        return self.config
