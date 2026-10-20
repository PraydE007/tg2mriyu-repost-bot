"""
Public Telegram channel scraper using web preview (https://t.me/s/{channel}).
Requires NO API keys or credentials.
Parses text, HTML formatting, photos, forwards, and post metadata.
"""

from __future__ import annotations
import os
import re
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class TelegramPost:
    post_id: str  # e.g. "telegram/460"
    channel: str  # e.g. "telegram"
    message_id: int  # e.g. 460
    raw_text: str  # HTML text content
    datetime_str: str  # ISO string or ""
    photos: List[str] = field(default_factory=list)  # list of image URLs or local paths
    is_forward: bool = False
    views: str = ""
    post_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "post_id": self.post_id,
            "channel": self.channel,
            "message_id": self.message_id,
            "raw_text": self.raw_text,
            "datetime_str": self.datetime_str,
            "photos": self.photos,
            "is_forward": self.is_forward,
            "views": self.views,
            "post_url": self.post_url,
        }


class TelegramScraper:
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    @staticmethod
    def clean_channel_name(channel_input: str) -> str:
        """Extract clean channel username from URL, @mention, or string."""
        s = channel_input.strip()
        # Remove https://t.me/s/ or https://t.me/
        s = re.sub(r'^https?://t\.me/(s/)?', '', s, flags=re.IGNORECASE)
        # Remove @ prefix
        s = s.lstrip('@')
        # Remove trailing slash or query params
        s = s.split('/')[0].split('?')[0].strip()
        return s

    @classmethod
    def fetch_channel_posts(cls, channel_name: str, timeout: int = 12) -> List[TelegramPost]:
        """Fetch latest posts from a public Telegram channel."""
        clean_name = cls.clean_channel_name(channel_name)
        if not clean_name:
            return []

        url = f"https://t.me/s/{clean_name}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": cls.USER_AGENT, "Accept-Language": "uk,en;q=0.9"}
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                html_content = response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"[TelegramScraper] Error fetching channel '{clean_name}': {e}")
            return []

        return cls._parse_posts(clean_name, html_content)

    @classmethod
    def _parse_posts(cls, channel_name: str, html_text: str) -> List[TelegramPost]:
        posts: List[TelegramPost] = []

        # Split into individual message wraps
        blocks = re.findall(
            r'(<div class="tgme_widget_message\b.*?)(?=<div class="tgme_widget_message\b|\Z)',
            html_text,
            re.DOTALL
        )

        for block in blocks:
            # Extract post identifier: data-post="channel/123"
            post_id_m = re.search(r'data-post="([^"]+)"', block)
            if not post_id_m:
                continue

            full_post_id = post_id_m.group(1).strip()
            parts = full_post_id.split('/')
            if len(parts) == 2:
                chan, msg_num = parts[0], parts[1]
                try:
                    message_id = int(msg_num)
                except ValueError:
                    message_id = 0
            else:
                chan = channel_name
                message_id = 0

            # Extract message text
            text_m = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
            raw_text = text_m.group(1).strip() if text_m else ""

            # Check if forwarded
            is_forward = "tgme_widget_message_forwarded_from" in block

            # Extract photos: background-image:url('...')
            photos = re.findall(r"background-image:url\('([^']+)'\)", block)
            # Deduplicate while preserving order
            unique_photos = []
            for p in photos:
                if p not in unique_photos:
                    unique_photos.append(p)

            # Datetime
            dt_m = re.search(r'<time datetime="([^"]+)"', block)
            datetime_str = dt_m.group(1).strip() if dt_m else ""

            # Views
            views_m = re.search(r'<span class="tgme_widget_message_views">([^<]+)</span>', block)
            views = views_m.group(1).strip() if views_m else ""

            post_url = f"https://t.me/{chan}/{message_id}" if message_id else f"https://t.me/{chan}"

            # Only add if post has either text or photo
            if raw_text or unique_photos:
                posts.append(
                    TelegramPost(
                        post_id=full_post_id,
                        channel=chan,
                        message_id=message_id,
                        raw_text=raw_text,
                        datetime_str=datetime_str,
                        photos=unique_photos,
                        is_forward=is_forward,
                        views=views,
                        post_url=post_url,
                    )
                )

        # Sort posts by message_id ascending (oldest first, newest last)
        posts.sort(key=lambda x: x.message_id)
        return posts

    @classmethod
    def download_image_bytes(cls, image_url: str, timeout: int = 15) -> Optional[bytes]:
        """Download image bytes from CDN or read from local disk for multipart upload."""
        if not image_url:
            return None

        # Check if local file path on disk (e.g. from Telethon cache)
        if os.path.isfile(image_url):
            try:
                with open(image_url, "rb") as f:
                    return f.read()
            except Exception as e:
                print(f"[TelegramScraper] Failed to read local image file {image_url}: {e}")
                return None

        req = urllib.request.Request(
            image_url,
            headers={"User-Agent": cls.USER_AGENT}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            print(f"[TelegramScraper] Failed to download image from {image_url}: {e}")
            return None
