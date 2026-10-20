"""
Core Reposter Engine.
Runs in the background, coordinates Telegram polling, filtering, formatting,
and publishing to MRIYU via Bot API.
"""

from __future__ import annotations
import threading
import time
import datetime
from typing import Dict, Any, Optional, List

from .config import ConfigManager, AppConfig
from .database import Database
from .formatter import MessageFormatter
from .mriyu_client import MriyuClient
from .tg_scraper import TelegramScraper, TelegramPost
from .tg_bot import TelegramBotClient


class ReposterEngine:
    def __init__(self, config_manager: ConfigManager, database: Database):
        self.config_manager = config_manager
        self.db = database

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._trigger_event = threading.Event()
        self._lock = threading.Lock()

        self.last_check_time: Optional[str] = None
        self.next_check_time: Optional[str] = None
        self.last_error: Optional[str] = None
        self._is_first_run = True

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._trigger_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ReposterEngineThread")
            self._thread.start()
            self.db.add_log("INFO", "Рушій репостингу запущено")

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()
            self._trigger_event.set()
            self.db.add_log("INFO", "Рушій репостингу зупинено")

    def trigger_manual_check(self):
        """Immediately trigger a check cycle."""
        self._trigger_event.set()
        self.db.add_log("INFO", "Запущено позачергову ручну перевірку")

    def get_status(self) -> Dict[str, Any]:
        cfg = self.config_manager.config
        stats = self.db.get_stats()
        return {
            "running": self._running,
            "last_check_time": self.last_check_time,
            "next_check_time": self.next_check_time,
            "last_error": self.last_error,
            "channel": cfg.telegram.channel,
            "mriyu_target_id": cfg.mriyu.target_id,
            "mriyu_target_type": cfg.mriyu.target_type,
            "stats": stats,
        }

    def _run_loop(self):
        while not self._stop_event.is_set():
            cfg = self.config_manager.config
            poll_interval = max(10, cfg.telegram.poll_interval)

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.last_check_time = now_str
            next_dt = datetime.datetime.now() + datetime.timedelta(seconds=poll_interval)
            self.next_check_time = next_dt.strftime("%Y-%m-%d %H:%M:%S")

            try:
                self._execute_cycle(cfg)
                self.last_error = None
            except Exception as e:
                err_msg = f"Критична помилка в циклі рушія: {str(e)}"
                self.last_error = err_msg
                self.db.add_log("ERROR", err_msg)
                print(f"[Engine] Exception: {e}")

            # Wait for poll_interval seconds or until triggered / stopped
            self._trigger_event.clear()
            self._stop_event.wait(timeout=poll_interval)

    def _execute_cycle(self, cfg: AppConfig):
        # Validation
        if not cfg.telegram.channel.strip():
            self.db.add_log("WARNING", "Не вказано Telegram канал у налаштуваннях")
            return

        if not cfg.mriyu.token.strip():
            self.db.add_log("WARNING", "Не вказано токен бота MRIYU")
            return

        if not cfg.mriyu.target_id.strip():
            self.db.add_log("WARNING", "Не вказано ID цільового каналу або користувача MRIYU")
            return

        # Fetch posts
        posts = self._fetch_posts(cfg)
        if not posts:
            return

        # Handle first run synchronization logic
        if self._is_first_run:
            self._handle_first_run(cfg, posts)
            self._is_first_run = False
            return

        # Process each post
        formatter = MessageFormatter(cfg.filter, cfg.formatting)
        mriyu = MriyuClient(cfg.mriyu.token)

        for post in posts:
            if self._stop_event.is_set():
                break

            if self.db.is_post_processed(post.post_id):
                continue

            self._process_single_post(post, cfg, formatter, mriyu)

    def _fetch_posts(self, cfg: AppConfig) -> List[TelegramPost]:
        if cfg.telegram.mode == "bot_api" and cfg.telegram.bot_token.strip():
            # Bot API mode
            bot_client = TelegramBotClient(cfg.telegram.bot_token)
            updates = bot_client.get_updates()
            posts: List[TelegramPost] = []
            for up in updates:
                cp = up.get("channel_post")
                if not cp:
                    continue
                msg_id = cp.get("message_id", 0)
                text = cp.get("text") or cp.get("caption") or ""
                post_id = f"{cfg.telegram.channel}/{msg_id}"
                photos = []
                if "photo" in cp and cp["photo"]:
                    best_photo = cp["photo"][-1]
                    photos.append(best_photo.get("file_id"))
                posts.append(TelegramPost(
                    post_id=post_id,
                    channel=cfg.telegram.channel,
                    message_id=msg_id,
                    raw_text=text,
                    datetime_str=str(cp.get("date", "")),
                    photos=photos,
                    post_url=f"https://t.me/{cfg.telegram.channel}/{msg_id}"
                ))
            return posts
        else:
            # Scraper mode (default)
            return TelegramScraper.fetch_channel_posts(cfg.telegram.channel)

    def _handle_first_run(self, cfg: AppConfig, posts: List[TelegramPost]):
        """
        On the very first launch:
        - If initial_sync_count == 0: mark all current posts as processed (repost only new ones).
        - If initial_sync_count > 0: mark older posts as processed, and leave the last N to be reposted.
        """
        sync_count = cfg.telegram.initial_sync_count
        self.db.add_log("INFO", f"Перший запуск: знайдено {len(posts)} постів у каналі (sync_count={sync_count})")

        if sync_count <= 0:
            # Mark all existing as processed
            for p in posts:
                self.db.mark_post_processed(
                    post_id=p.post_id,
                    channel=p.channel,
                    source_date=p.datetime_str,
                    text_snippet=p.raw_text,
                    has_photo=bool(p.photos),
                    status="filtered",
                    error_detail="Пропущено під час первинної ініціалізації",
                )
            self.db.add_log("INFO", "Всі наявні пости позначено як оброблені (репоститимуться лише нові)")
        else:
            # Leave the latest `sync_count` posts for processing
            to_skip = posts[:-sync_count] if len(posts) > sync_count else []
            for p in to_skip:
                self.db.mark_post_processed(
                    post_id=p.post_id,
                    channel=p.channel,
                    source_date=p.datetime_str,
                    text_snippet=p.raw_text,
                    has_photo=bool(p.photos),
                    status="filtered",
                    error_detail="Старіший пост до початкового ліміту",
                )

    def _process_single_post(
        self,
        post: TelegramPost,
        cfg: AppConfig,
        formatter: MessageFormatter,
        mriyu: MriyuClient
    ):
        has_photo = bool(post.photos)
        should_post, reason = formatter.should_repost(
            raw_text=post.raw_text,
            has_photo=has_photo,
            is_forward=post.is_forward,
        )

        if not should_post:
            self.db.mark_post_processed(
                post_id=post.post_id,
                channel=post.channel,
                source_date=post.datetime_str,
                text_snippet=post.raw_text,
                has_photo=has_photo,
                status="filtered",
                error_detail=reason,
            )
            self.db.add_log("INFO", f"Фільтр відхилив {post.post_id}: {reason}")
            return

        # Prepare Buttons
        buttons: Optional[List[List[Dict[str, str]]]] = None
        if cfg.mriyu.add_button:
            btn_text = cfg.mriyu.button_text.strip() or "Читати в Telegram"
            btn_url = cfg.mriyu.button_url.strip() or post.post_url
            if btn_url:
                buttons = [[{"text": btn_text, "url": btn_url}]]

        # Repost with Photo
        if has_photo:
            image_url = post.photos[0]
            caption = formatter.format_text(
                raw_text=post.raw_text,
                post_url=post.post_url,
                is_caption=True
            )

            # Download photo bytes
            photo_bytes = TelegramScraper.download_image_bytes(image_url)

            # Send photo to MRIYU
            res = mriyu.send_photo(
                target_id=cfg.mriyu.target_id,
                target_type=cfg.mriyu.target_type,
                photo_bytes=photo_bytes,
                photo_url=image_url if not photo_bytes else None,
                caption=caption,
                buttons=buttons,
                silent=cfg.mriyu.silent,
            )

            if res.get("ok"):
                msg_id = res.get("result", {}).get("id")
                self.db.mark_post_processed(
                    post_id=post.post_id,
                    channel=post.channel,
                    source_date=post.datetime_str,
                    text_snippet=caption,
                    has_photo=True,
                    status="reposted",
                    mriyu_msg_id=msg_id,
                )
                self.db.add_log("SUCCESS", f"Успішно репостнуто фото-пост {post.post_id} в MRIYU (ID: {msg_id})")
            else:
                desc = res.get("description", "Невідома помилка")
                err_code = res.get("error_code", "")
                self.db.add_log("ERROR", f"Помилка відправки фото {post.post_id} в MRIYU: {desc} (код: {err_code})")
                
                # Fallback: try sending as text message if photo failed
                text_content = formatter.format_text(
                    raw_text=f"{post.raw_text}\n\n[Переглянути фото]({image_url})",
                    post_url=post.post_url,
                    is_caption=False
                )
                fb_res = self._send_text_mriyu(mriyu, cfg, text_content, buttons)
                if fb_res.get("ok"):
                    fb_msg_id = fb_res.get("result", {}).get("id")
                    self.db.mark_post_processed(
                        post_id=post.post_id,
                        channel=post.channel,
                        source_date=post.datetime_str,
                        text_snippet=text_content,
                        has_photo=True,
                        status="reposted",
                        mriyu_msg_id=fb_msg_id,
                        error_detail="Відправлено як текст (fallback)",
                    )
                    self.db.add_log("WARNING", f"Пост {post.post_id} надіслано в текстовому форматі через помилку фото")
                else:
                    self.db.mark_post_processed(
                        post_id=post.post_id,
                        channel=post.channel,
                        source_date=post.datetime_str,
                        text_snippet=caption,
                        has_photo=True,
                        status="error",
                        error_detail=f"{desc} (код {err_code})",
                    )

        # Repost Text Only
        else:
            formatted_text = formatter.format_text(
                raw_text=post.raw_text,
                post_url=post.post_url,
                is_caption=False
            )
            if not formatted_text:
                return

            res = self._send_text_mriyu(mriyu, cfg, formatted_text, buttons)

            if res.get("ok"):
                msg_id = res.get("result", {}).get("id")
                self.db.mark_post_processed(
                    post_id=post.post_id,
                    channel=post.channel,
                    source_date=post.datetime_str,
                    text_snippet=formatted_text,
                    has_photo=False,
                    status="reposted",
                    mriyu_msg_id=msg_id,
                )
                self.db.add_log("SUCCESS", f"Успішно репостнуто текст {post.post_id} в MRIYU (ID: {msg_id})")
            else:
                desc = res.get("description", "Невідома помилка")
                err_code = res.get("error_code", "")
                self.db.mark_post_processed(
                    post_id=post.post_id,
                    channel=post.channel,
                    source_date=post.datetime_str,
                    text_snippet=formatted_text,
                    has_photo=False,
                    status="error",
                    error_detail=f"{desc} (код {err_code})",
                )
                self.db.add_log("ERROR", f"Помилка репосту тексту {post.post_id} в MRIYU: {desc} (код: {err_code})")

        # Rate limit safety sleep (2 seconds)
        time.sleep(2.0)

    def _send_text_mriyu(
        self,
        mriyu: MriyuClient,
        cfg: AppConfig,
        text: str,
        buttons: Optional[List[List[Dict[str, str]]]]
    ) -> Dict[str, Any]:
        if cfg.mriyu.target_type == "chat":
            return mriyu.send_chat_message(
                chat_id=cfg.mriyu.target_id,
                text=text,
                buttons=buttons,
                silent=cfg.mriyu.silent,
            )
        else:
            return mriyu.send_message(
                user_id=cfg.mriyu.target_id,
                text=text,
                buttons=buttons,
                silent=cfg.mriyu.silent,
            )

