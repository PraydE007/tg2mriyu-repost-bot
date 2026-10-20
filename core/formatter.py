"""
Message formatting, Markdown conversion (Telegram to MRIYU syntax),
keyword filtering, and custom text replacements.
"""

from __future__ import annotations
import re
import html
from typing import Tuple, Optional, List, Dict, Any
from .config import FilterConfig, FormattingConfig


class MessageFormatter:
    def __init__(self, filter_cfg: FilterConfig, format_cfg: FormattingConfig):
        self.filter_cfg = filter_cfg
        self.format_cfg = format_cfg

    def should_repost(
        self,
        raw_text: str,
        has_photo: bool,
        is_forward: bool = False,
        links_found: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """
        Evaluate post against filter criteria.
        Returns: (should_repost: bool, reason: str)
        """
        text_lower = (raw_text or "").lower()

        # Check media types
        if has_photo and not self.filter_cfg.allow_photos:
            return False, "Пропущено: налаштування забороняють репост фото"
        if not has_photo and not self.filter_cfg.allow_text_only:
            return False, "Пропущено: налаштування забороняють репост суто текстових повідомлень"

        # Check forwarded
        if is_forward and self.filter_cfg.ignore_forwards:
            return False, "Пропущено: пересланий пост (ignore_forwards увімкнено)"

        # Check length
        clean_text_len = len(re.sub(r'<[^>]+>', '', raw_text or "").strip())
        if self.filter_cfg.min_length > 0 and clean_text_len < self.filter_cfg.min_length:
            return False, f"Пропущено: довжина тексту ({clean_text_len}) менша за мінімум ({self.filter_cfg.min_length})"
        if self.filter_cfg.max_length > 0 and clean_text_len > self.filter_cfg.max_length:
            return False, f"Пропущено: довжина тексту ({clean_text_len}) більша за максимум ({self.filter_cfg.max_length})"

        # Check links
        if self.filter_cfg.skip_links:
            has_link = bool(links_found) or bool(re.search(r'https?://', raw_text or "", re.IGNORECASE))
            if has_link:
                return False, "Пропущено: містить зовнішнє посилання (skip_links увімкнено)"

        # Check blacklist keywords
        for word in self.filter_cfg.keyword_blacklist:
            word = word.strip().lower()
            if word and word in text_lower:
                return False, f"Пропущено: чорний список слів ('{word}')"

        # Check whitelist keywords (if specified, at least one must match)
        active_whitelist = [w.strip().lower() for w in self.filter_cfg.keyword_whitelist if w.strip()]
        if active_whitelist:
            matches_whitelist = any(w in text_lower for w in active_whitelist)
            if not matches_whitelist:
                return False, "Пропущено: не містить жодного слова з білого списку"

        return True, "OK"

    def format_text(
        self,
        raw_text: str,
        post_url: Optional[str] = None,
        is_caption: bool = False,
    ) -> str:
        """
        Transform Telegram text into MRIYU-compatible markdown text.
        Handles bold (**text**), italic (__text__), links ([text](url)), code (`code`),
        custom replacements, prefix/suffix, and character limits.
        """
        if not raw_text:
            raw_text = ""

        # Step 1: Convert HTML tags to MRIYU markdown
        formatted = raw_text
        if self.format_cfg.convert_markdown:
            formatted = self._html_to_mriyu_markdown(formatted)
        else:
            # Simple strip HTML tags
            formatted = re.sub(r'<br\s*/?>', '\n', formatted, flags=re.IGNORECASE)
            formatted = re.sub(r'<[^>]+>', '', formatted)
            formatted = html.unescape(formatted)

        # Step 2: Custom text replacements
        for rep in self.format_cfg.replacements:
            find_pat = rep.get("find", "")
            replace_with = rep.get("replace", "")
            is_regex = rep.get("is_regex", False)
            if not find_pat:
                continue

            try:
                if is_regex:
                    formatted = re.sub(find_pat, replace_with, formatted)
                else:
                    # Case-insensitive literal replacement
                    pattern = re.compile(re.escape(find_pat), re.IGNORECASE)
                    formatted = pattern.sub(replace_with, formatted)
            except Exception as e:
                print(f"[Formatter] Replacement error for '{find_pat}': {e}")

        # Step 3: Remove URLs if enabled
        if self.format_cfg.remove_urls:
            formatted = re.sub(r'https?://[^\s<>"]+|www\.[^\s<>"]+', '', formatted)

        # Step 4: Remove hashtags if enabled
        if self.format_cfg.remove_hashtags:
            formatted = re.sub(r'#[a-zA-Z0-9_\u0400-\u04FF]+', '', formatted)

        formatted = formatted.strip()

        # Step 5: Add Header Prefix
        if self.format_cfg.header_prefix:
            prefix = self.format_cfg.header_prefix.strip()
            formatted = f"{prefix}\n\n{formatted}" if formatted else prefix

        # Step 6: Add Source Link
        if self.format_cfg.add_source_link and post_url:
            source_label = self.format_cfg.source_link_text or "Джерело в Telegram"
            source_link = f"[{source_label}]({post_url})"
            formatted = f"{formatted}\n\n{source_link}" if formatted else source_link

        # Step 7: Add Footer Suffix
        if self.format_cfg.footer_suffix:
            suffix = self.format_cfg.footer_suffix.strip()
            formatted = f"{formatted}\n\n{suffix}" if formatted else suffix

        # Step 8: Apply MRIYU character limits
        # sendMessage / sendChatMessage: up to 4000 chars
        # sendPhoto / sendDocument caption: up to 1000 chars
        max_chars = 1000 if is_caption else 4000
        if len(formatted) > max_chars:
            cutoff = max_chars - 3
            formatted = formatted[:cutoff] + "..."

        return formatted.strip()

    def _html_to_mriyu_markdown(self, text: str) -> str:
        """
        Converts Telegram web/bot HTML tags to MRIYU markdown.
        MRIYU markdown specification:
          **жирний**
          __курсив__
          [текст](посилання)
          `код`
        """
        # Replace line breaks
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)

        # Bold: <b>text</b> or <strong>text</strong> -> **text**
        text = re.sub(r'<b\b[^>]*>(.*?)</b>', r'**\1**', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<strong\b[^>]*>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL | re.IGNORECASE)

        # Italic: <i>text</i> or <em>text</em> -> __text__
        text = re.sub(r'<i\b[^>]*>(.*?)</i>', r'__\1__', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<em\b[^>]*>(.*?)</em>', r'__\1__', text, flags=re.DOTALL | re.IGNORECASE)

        # Code: <code>text</code> -> `text`
        text = re.sub(r'<code\b[^>]*>(.*?)</code>', r'`\1`', text, flags=re.DOTALL | re.IGNORECASE)

        # Pre: <pre>text</pre> -> ```text```
        text = re.sub(r'<pre\b[^>]*>(.*?)</pre>', r'```\n\1\n```', text, flags=re.DOTALL | re.IGNORECASE)

        # Links: <a href="url">text</a> -> [text](url)
        def replace_link(match):
            href = match.group(1)
            content = match.group(2)
            # Remove nested tags inside link text
            clean_content = re.sub(r'<[^>]+>', '', content).strip()
            if not clean_content:
                clean_content = href
            return f"[{clean_content}]({href})"

        text = re.sub(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', replace_link, text, flags=re.DOTALL | re.IGNORECASE)

        # Strip remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Unescape HTML entities (&amp; -> &, &#39; -> ', &quot; -> ", etc.)
        text = html.unescape(text)

        return text

