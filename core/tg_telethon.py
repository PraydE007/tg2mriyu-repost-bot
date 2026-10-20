"""
Telethon (MTProto Client API) integration for Repost Bot MRIYU.
Allows fetching posts from public channels, private channels, groups,
and supergroups using Telegram api_id and api_hash.
"""

from __future__ import annotations
import os
import re
import asyncio
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from telethon import TelegramClient, errors
    from telethon.tl.types import (
        MessageMediaPhoto,
        MessageMediaDocument,
        Channel,
        Chat,
        User
    )
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    TelegramClient = None
    errors = None

from .tg_scraper import TelegramPost

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MEDIA_DIR = os.path.join(DATA_DIR, "media")


class TelethonService:
    """Singleton service to manage Telethon lifecycle in a dedicated event loop thread."""

    _instance: Optional[TelethonService] = None
    _lock = threading.Lock()

    def __init__(self, session_name: str = "telethon_session"):
        self.session_name = session_name
        self.session_path = os.path.join(DATA_DIR, session_name)
        self.client: Optional[TelegramClient] = None
        self._current_api_id: Optional[int] = None
        self._current_api_hash: Optional[str] = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._loop_ready = threading.Event()
        self._pending_phone_code_hash: Optional[str] = None
        self._pending_phone: Optional[str] = None

        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(MEDIA_DIR, exist_ok=True)

        self._start_loop()

    @classmethod
    def get_instance(cls, session_name: str = "telethon_session") -> TelethonService:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(session_name)
            return cls._instance

    def _start_loop(self):
        """Starts a background daemon thread with its own asyncio event loop."""
        def run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop_ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=run, daemon=True, name="TelethonLoopThread")
        self._thread.start()
        self._loop_ready.wait(timeout=5)

    def _run(self, coro, timeout: float = 30.0) -> Any:
        """Executes an async coroutine thread-safely inside the Telethon loop."""
        if not self._loop or not self._loop.is_running():
            raise RuntimeError("Telethon event loop is not running")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def is_available(self) -> bool:
        return TELETHON_AVAILABLE

    def _init_client(self, api_id: int | str, api_hash: str) -> TelegramClient:
        """Initializes client if parameters changed or client is None."""
        if not TELETHON_AVAILABLE:
            raise RuntimeError("Бібліотеку telethon не встановлено (pip install telethon)")

        clean_id = int(str(api_id).strip())
        clean_hash = str(api_hash).strip()

        if (
            self.client is None
            or self._current_api_id != clean_id
            or self._current_api_hash != clean_hash
        ):
            if self.client is not None:
                try:
                    self._run(self.client.disconnect(), timeout=5)
                except Exception:
                    pass

            self._current_api_id = clean_id
            self._current_api_hash = clean_hash
            self.client = TelegramClient(
                self.session_path,
                clean_id,
                clean_hash,
                loop=self._loop
            )

        return self.client

    def get_status(self, api_id: str = "", api_hash: str = "") -> Dict[str, Any]:
        """Returns the current connection and authorization status."""
        if not TELETHON_AVAILABLE:
            return {
                "available": False,
                "configured": False,
                "authorized": False,
                "error": "Модуль telethon не встановлено в системі"
            }

        session_file_exists = os.path.exists(f"{self.session_path}.session")

        effective_id = api_id or (str(self._current_api_id) if self._current_api_id else "")
        effective_hash = api_hash or self._current_api_hash or ""

        if not effective_id or not effective_hash:
            return {
                "available": True,
                "configured": False,
                "authorized": False,
                "session_exists": session_file_exists,
                "message": "Введіть api_id та api_hash"
            }

        try:
            client = self._init_client(effective_id, effective_hash)

            async def _check():
                if not client.is_connected():
                    await client.connect()
                is_auth = await client.is_user_authorized()
                user_info = None
                if is_auth:
                    me = await client.get_me()
                    if me:
                        user_info = {
                            "id": me.id,
                            "first_name": me.first_name or "",
                            "last_name": me.last_name or "",
                            "username": me.username or "",
                            "phone": me.phone or "",
                            "is_bot": getattr(me, "bot", False)
                        }
                return is_auth, user_info

            is_auth, user_info = self._run(_check(), timeout=15)
            return {
                "available": True,
                "configured": True,
                "authorized": is_auth,
                "session_exists": session_file_exists,
                "user": user_info
            }
        except Exception as e:
            return {
                "available": True,
                "configured": True,
                "authorized": False,
                "session_exists": session_file_exists,
                "error": str(e)
            }

    def send_auth_code(self, phone: str, api_id: str, api_hash: str) -> Dict[str, Any]:
        """Sends confirmation code to the user via Telegram."""
        if not TELETHON_AVAILABLE:
            return {"ok": False, "error": "Модуль telethon не встановлено"}

        phone = phone.strip().replace(" ", "").replace("-", "")
        if not phone:
            return {"ok": False, "error": "Вкажіть номер телефону"}

        try:
            client = self._init_client(api_id, api_hash)

            async def _send():
                if not client.is_connected():
                    await client.connect()
                res = await client.send_code_request(phone)
                return res

            sent_code_obj = self._run(_send(), timeout=25)
            code_hash = sent_code_obj.phone_code_hash
            self._pending_phone = phone
            self._pending_phone_code_hash = code_hash

            # Detect delivery destination type
            sent_type_name = type(sent_code_obj.type).__name__
            if "App" in sent_type_name:
                delivery_type = "app"
                msg = (
                    "Код надіслано в ОФІЦІЙНИЙ ДОДАТОК TELEGRAM! "
                    "Будь ласка, відкрийте Telegram на телефоні або комп'ютері та перевірте чат від 'Telegram' (зі синьою зіркою/галочкою). "
                    "Увага: у звичайні SMS на телефон код НЕ надходить!"
                )
            elif "Email" in sent_type_name:
                delivery_type = "email"
                msg = "Код надіслано на вашу електронну пошту, прив'язану до Telegram!"
            elif "Sms" in sent_type_name:
                delivery_type = "sms"
                msg = f"Код надіслано в SMS на номер {phone}."
            elif "Call" in sent_type_name:
                delivery_type = "call"
                msg = f"Telegram телефонує на номер {phone} для передачі коду."
            else:
                delivery_type = "telegram"
                msg = f"Код надіслано через Telegram ({sent_type_name}). Перевірте додаток Telegram або SMS."

            return {
                "ok": True,
                "phone_code_hash": code_hash,
                "phone": phone,
                "delivery_type": delivery_type,
                "message": msg
            }
        except errors.FloodWaitError as e:
            return {
                "ok": False,
                "error": f"Забагато спроб (FloodWait). Telegram обмежив запити на {e.seconds} секунд. Зачекайте цей час."
            }
        except errors.PhoneNumberInvalidError:
            return {
                "ok": False,
                "error": "Неправильний формат номера телефону. Введіть номер у міжнародному форматі (наприклад: +380955755505)."
            }
        except errors.PhoneNumberBannedError:
            return {
                "ok": False,
                "error": "Цей номер телефону заблоковано в Telegram."
            }
        except (errors.ApiIdInvalidError, errors.ApiIdPublishedFloodError):
            return {
                "ok": False,
                "error": "Невірний api_id або api_hash. Перевірте значення на my.telegram.org."
            }
        except errors.PhoneNumberAppSignupForbiddenError:
            return {
                "ok": False,
                "error": "Telegram забороняє реєстрацію нових акаунтів через сторонні застосунки. Використовуйте існуючий активний акаунт."
            }
        except Exception as e:
            return {"ok": False, "error": f"Помилка відправки коду: {e}"}

    def sign_in(
        self,
        phone: str,
        code: str,
        phone_code_hash: Optional[str] = None,
        password: str = "",
        api_id: str = "",
        api_hash: str = ""
    ) -> Dict[str, Any]:
        """Signs in using received verification code (and optional 2FA password)."""
        if not TELETHON_AVAILABLE:
            return {"ok": False, "error": "Модуль telethon не встановлено"}

        effective_id = api_id or str(self._current_api_id)
        effective_hash = api_hash or self._current_api_hash
        effective_phone = (phone or self._pending_phone or "").strip().replace(" ", "").replace("-", "")
        effective_hash_code = phone_code_hash or self._pending_phone_code_hash

        if not effective_phone or not code:
            return {"ok": False, "error": "Вкажіть номер телефону та код з Telegram"}

        try:
            client = self._init_client(effective_id, effective_hash)

            async def _do_sign_in():
                if not client.is_connected():
                    await client.connect()

                try:
                    await client.sign_in(
                        phone=effective_phone,
                        code=code.strip(),
                        phone_code_hash=effective_hash_code
                    )
                except errors.SessionPasswordNeededError:
                    if not password.strip():
                        return {"needs_password": True}
                    await client.sign_in(password=password.strip())

                me = await client.get_me()
                return {
                    "ok": True,
                    "first_name": me.first_name or "",
                    "username": me.username or "",
                    "phone": me.phone or ""
                }

            res = self._run(_do_sign_in(), timeout=25)
            if res.get("needs_password"):
                return {
                    "ok": False,
                    "needs_password": True,
                    "message": "Обліковий запис захищено двофакторною автентифікацією (2FA). Введіть хмарний пароль."
                }

            self._pending_phone = None
            self._pending_phone_code_hash = None
            return {
                "ok": True,
                "message": f"Успішно авторизовано як {res.get('first_name')} (@{res.get('username')})",
                "user": res
            }
        except errors.PhoneCodeInvalidError:
            return {"ok": False, "error": "Невірний код підтвердження. Перевірте код з повідомлення Telegram та спробуйте ще раз."}
        except errors.PhoneCodeExpiredError:
            return {"ok": False, "error": "Термін дії коду минув. Натисніть «Надіслати код» знову."}
        except errors.PasswordHashInvalidError:
            return {"ok": False, "error": "Невірний пароль 2FA."}
        except Exception as e:
            return {"ok": False, "error": f"Помилка авторизації: {e}"}

    def sign_in_bot(self, bot_token: str, api_id: str, api_hash: str) -> Dict[str, Any]:
        """Signs in Telethon using a Telegram Bot Token."""
        if not TELETHON_AVAILABLE:
            return {"ok": False, "error": "Модуль telethon не встановлено"}

        bot_token = bot_token.strip()
        if not bot_token:
            return {"ok": False, "error": "Токен бота не може бути порожнім"}

        try:
            client = self._init_client(api_id, api_hash)

            async def _bot_start():
                if not client.is_connected():
                    await client.connect()
                await client.start(bot_token=bot_token)
                me = await client.get_me()
                return {
                    "id": me.id,
                    "first_name": me.first_name,
                    "username": me.username
                }

            bot_info = self._run(_bot_start(), timeout=20)
            return {
                "ok": True,
                "message": f"Telethon авторизовано як бот @{bot_info.get('username')}",
                "user": bot_info
            }
        except Exception as e:
            return {"ok": False, "error": f"Помилка авторизації бота: {e}"}

    def logout(self) -> Dict[str, Any]:
        """Disconnects and removes the current session."""
        try:
            if self.client:
                async def _disconnect():
                    try:
                        if self.client.is_connected():
                            await self.client.log_out()
                    except Exception:
                        pass
                    try:
                        await self.client.disconnect()
                    except Exception:
                        pass

                try:
                    self._run(_disconnect(), timeout=10)
                except Exception:
                    pass
                self.client = None

            # Remove session files
            for ext in [".session", ".session-journal"]:
                f = f"{self.session_path}{ext}"
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass

            return {"ok": True, "message": "Сесію успішно скинуто та видалено"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def parse_channel_input(channel_str: str) -> Any:
        """
        Parses various Telegram channel link formats:
        - https://web.telegram.org/k/#-1224603898 -> int -1224603898
        - https://web.telegram.org/a/#-1224603898 -> int -1224603898
        - https://t.me/c/1224603898/456 -> int -1001224603898
        - https://t.me/durov -> "durov"
        - @durov -> "durov"
        - -1001224603898 -> int -1001224603898
        - -1224603898 -> int -1224603898
        """
        s = channel_str.strip()

        # Web Telegram format: web.telegram.org/.../#-1224603898 or #?tgaddr=...
        web_m = re.search(r'web\.telegram\.org/[ka]/#(-?\d+)', s, flags=re.IGNORECASE)
        if web_m:
            try:
                return int(web_m.group(1))
            except ValueError:
                pass

        # Private channel URL: https://t.me/c/1224603898/123
        c_m = re.search(r't\.me/c/(\d+)', s, flags=re.IGNORECASE)
        if c_m:
            try:
                # Convert to supergroup peer format -100xxxxxxxxx
                return int(f"-100{c_m.group(1)}")
            except ValueError:
                pass

        # Invite links: https://t.me/+... or https://t.me/joinchat/...
        if "t.me/+" in s or "t.me/joinchat/" in s:
            return s

        # Standard t.me link: https://t.me/channel_name
        s = re.sub(r'^https?://t\.me/(s/)?', '', s, flags=re.IGNORECASE)
        s = s.lstrip('@')
        s = s.split('/')[0].split('?')[0].strip()

        # Pure integer ID
        if re.match(r'^-?\d+$', s):
            try:
                return int(s)
            except ValueError:
                pass

        return s

    def fetch_channel_posts(
        self,
        channel_input: str,
        limit: int = 20,
        api_id: str = "",
        api_hash: str = ""
    ) -> List[TelegramPost]:
        """
        Fetches the latest posts from a channel or group using Telethon.
        Works with public channels, private channels, and groups where the account is present.
        """
        if not TELETHON_AVAILABLE:
            raise RuntimeError("Бібліотеку telethon не знайдено")

        effective_id = api_id or str(self._current_api_id)
        effective_hash = api_hash or self._current_api_hash

        if not effective_id or not effective_hash:
            raise ValueError("Не налаштовано api_id та api_hash для Telethon")

        client = self._init_client(effective_id, effective_hash)
        parsed_target = self.parse_channel_input(channel_input)

        async def _fetch():
            if not client.is_connected():
                await client.connect()

            if not await client.is_user_authorized():
                raise PermissionError("Telethon клієнт не авторизований. Авторизуйтесь у налаштуваннях бота.")

            entity = None

            # If target is an integer ID, search directly or among dialogs
            if isinstance(parsed_target, int):
                target_num = parsed_target
                # Try direct get_entity first
                candidates_to_try = [target_num]
                # If negative without -100, try supergroup prefix
                if target_num < 0 and not str(target_num).startswith("-100"):
                    candidates_to_try.append(int(f"-100{abs(target_num)}"))
                elif target_num > 0:
                    candidates_to_try.append(int(f"-100{target_num}"))
                    candidates_to_try.append(-target_num)

                for cand in candidates_to_try:
                    try:
                        entity = await client.get_entity(cand)
                        if entity:
                            break
                    except Exception:
                        pass

                # If still not found, search in user dialogs
                if not entity:
                    target_abs_str = str(abs(target_num))
                    async for dialog in client.iter_dialogs():
                        d_id_str = str(dialog.id)
                        if dialog.id == target_num or d_id_str.endswith(target_abs_str):
                            entity = dialog.entity
                            break
            else:
                # Username, invite link, or slug
                try:
                    entity = await client.get_entity(parsed_target)
                except Exception as e:
                    # Search by title in dialogs as fallback
                    target_lower = str(parsed_target).lower()
                    async for dialog in client.iter_dialogs():
                        if dialog.title and target_lower in dialog.title.lower():
                            entity = dialog.entity
                            break
                    if not entity:
                        raise e

            if not entity:
                raise ValueError(f"Не вдалося знайти чат або канал: {channel_input}")

            # Channel display name / slug
            entity_id = getattr(entity, "id", 0)
            username = getattr(entity, "username", "")
            chan_name = username or str(entity_id)

            messages = await client.get_messages(entity, limit=limit)
            posts: List[TelegramPost] = []

            for msg in messages:
                if not msg:
                    continue

                # Ignore service messages
                if getattr(msg, "action", None) is not None:
                    continue

                raw_text = msg.text or msg.message or ""
                photos: List[str] = []

                # Handle Photos and image documents
                if msg.photo:
                    try:
                        file_name = f"tg_{entity_id}_{msg.id}.jpg"
                        dest_path = os.path.join(MEDIA_DIR, file_name)
                        if not os.path.exists(dest_path):
                            await client.download_media(msg.photo, file=dest_path)
                        if os.path.exists(dest_path):
                            photos.append(dest_path)
                    except Exception as err:
                        print(f"[Telethon] Error downloading photo for msg {msg.id}: {err}")

                # Datetime
                dt_str = msg.date.isoformat() if msg.date else ""
                is_forward = bool(msg.forward)
                views = str(getattr(msg, "views", "") or "")

                # URL
                if username:
                    post_url = f"https://t.me/{username}/{msg.id}"
                else:
                    post_url = f"https://t.me/c/{entity_id}/{msg.id}"

                post_id = f"{chan_name}/{msg.id}"

                # Only include posts that have text or photos
                if raw_text.strip() or photos:
                    posts.append(
                        TelegramPost(
                            post_id=post_id,
                            channel=chan_name,
                            message_id=msg.id,
                            raw_text=raw_text,
                            datetime_str=dt_str,
                            photos=photos,
                            is_forward=is_forward,
                            views=views,
                            post_url=post_url,
                        )
                    )

            # Sort ascending: oldest first, newest last
            posts.sort(key=lambda x: x.message_id)
            return posts

        return self._run(_fetch(), timeout=40)
