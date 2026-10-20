"""
Official MRIYU Bot API Client.
Documentation: https://mriyu.com/wiki/bot-api
API Base: https://mriyu.com/api/bot/v1/
"""

from __future__ import annotations
import json
import time
import requests
from typing import Dict, Any, Optional, List, Union


class MriyuClient:
    BASE_URL = "https://mriyu.com/api/bot/v1/"

    def __init__(self, token: str, timeout: int = 15):
        self.token = token.strip()
        self.timeout = timeout

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
        }

    def _post(self, method: str, json_data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None, form_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send POST request to MRIYU API with error handling and rate limit backoff."""
        url = f"{self.BASE_URL}{method}"

        for attempt in range(3):
            try:
                if files:
                    # Multipart request for file uploads
                    resp = requests.post(
                        url,
                        headers=self.headers,
                        data=form_data or {},
                        files=files,
                        timeout=self.timeout + 15
                    )
                else:
                    # JSON request
                    headers = dict(self.headers)
                    headers["Content-Type"] = "application/json"
                    resp = requests.post(
                        url,
                        headers=headers,
                        json=json_data or {},
                        timeout=self.timeout
                    )

                try:
                    res_json = resp.json()
                except Exception:
                    return {
                        "ok": False,
                        "error_code": resp.status_code,
                        "description": f"Invalid JSON response: {resp.text[:200]}"
                    }

                # Handle Rate Limit (429)
                if resp.status_code == 429:
                    retry_wait = 2.0 * (attempt + 1)
                    time.sleep(retry_wait)
                    continue

                return res_json

            except requests.exceptions.Timeout:
                if attempt == 2:
                    return {"ok": False, "error_code": 408, "description": "Request timeout to MRIYU API"}
                time.sleep(1.5)
            except requests.exceptions.RequestException as e:
                if attempt == 2:
                    return {"ok": False, "error_code": 500, "description": f"Network error: {str(e)}"}
                time.sleep(1.5)

        return {"ok": False, "error_code": 500, "description": "Failed after 3 retries"}

    def get_me(self) -> Dict[str, Any]:
        """Verify token and get bot details."""
        return self._post("getMe")

    def get_chats(self) -> Dict[str, Any]:
        """
        Get list of chats and channels where the bot is added.
        Returns array: [{id, title, type, role}, ...]
        """
        return self._post("getChats")

    def get_chat(self, chat_id: Union[int, str]) -> Dict[str, Any]:
        """Get details about a specific chat or channel."""
        return self._post("getChat", json_data={"chat_id": chat_id})

    def send_chat_message(
        self,
        chat_id: Union[int, str],
        text: str,
        buttons: Optional[List[List[Dict[str, str]]]] = None,
        reply_to: Optional[int] = None,
        silent: bool = False,
    ) -> Dict[str, Any]:
        """Publish a text message to a channel or group chat."""
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "silent": silent,
        }
        if buttons:
            payload["buttons"] = buttons
        if reply_to:
            payload["reply_to"] = reply_to

        return self._post("sendChatMessage", json_data=payload)

    def send_message(
        self,
        user_id: Union[int, str],
        text: str,
        buttons: Optional[List[List[Dict[str, str]]]] = None,
        reply_to: Optional[int] = None,
        silent: bool = False,
    ) -> Dict[str, Any]:
        """Send direct text message to a user."""
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "text": text,
            "silent": silent,
        }
        if buttons:
            payload["buttons"] = buttons
        if reply_to:
            payload["reply_to"] = reply_to

        return self._post("sendMessage", json_data=payload)

    def send_photo(
        self,
        target_id: Union[int, str],
        target_type: str = "chat",
        photo_bytes: Optional[bytes] = None,
        photo_filename: str = "image.jpg",
        photo_url: Optional[str] = None,
        caption: Optional[str] = None,
        buttons: Optional[List[List[Dict[str, str]]]] = None,
        silent: bool = False,
    ) -> Dict[str, Any]:
        """
        Send photo to chat/channel or user.
        Supports multipart file upload or direct HTTPS image URL.
        """
        id_field = "chat_id" if target_type == "chat" else "user_id"

        # Case 1: Upload via file bytes (multipart/form-data)
        if photo_bytes:
            form_data = {
                id_field: str(target_id),
                "silent": "true" if silent else "false",
            }
            if caption:
                form_data["caption"] = caption
            if buttons:
                form_data["buttons"] = json.dumps(buttons)

            files = {
                "file": (photo_filename, photo_bytes, "image/jpeg")
            }
            return self._post("sendPhoto", files=files, form_data=form_data)

        # Case 2: Send via direct image URL
        payload: Dict[str, Any] = {
            id_field: target_id,
            "url": photo_url,
            "silent": silent,
        }
        if caption:
            payload["caption"] = caption
        if buttons:
            payload["buttons"] = buttons

        return self._post("sendPhoto", json_data=payload)

    def send_document(
        self,
        target_id: Union[int, str],
        target_type: str = "chat",
        doc_bytes: Optional[bytes] = None,
        doc_filename: str = "file.bin",
        doc_url: Optional[str] = None,
        caption: Optional[str] = None,
        buttons: Optional[List[List[Dict[str, str]]]] = None,
        silent: bool = False,
    ) -> Dict[str, Any]:
        """Send document/file to chat or user."""
        id_field = "chat_id" if target_type == "chat" else "user_id"

        if doc_bytes:
            form_data = {
                id_field: str(target_id),
                "silent": "true" if silent else "false",
            }
            if caption:
                form_data["caption"] = caption
            if buttons:
                form_data["buttons"] = json.dumps(buttons)

            files = {
                "file": (doc_filename, doc_bytes, "application/octet-stream")
            }
            return self._post("sendDocument", files=files, form_data=form_data)

        payload: Dict[str, Any] = {
            id_field: target_id,
            "url": doc_url,
            "silent": silent,
        }
        if caption:
            payload["caption"] = caption
        if buttons:
            payload["buttons"] = buttons

        return self._post("sendDocument", json_data=payload)

