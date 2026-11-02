# 🤖 Repost Bot: Telegram ➔ MRIYU

A powerful, standalone repost bot for automatic broadcasting of posts from specified Telegram channels to the **[MRIYU](https://mriyu.com)** social network according to the official [MRIYU Bot API](https://mriyu.com/wiki/bot-api) documentation.

<p align="center">
  <b>💖 Підтримати проєкт / Support the project:</b><br><br>
  <a href="https://send.monobank.ua/jar/5uPPFW5FqV" target="_blank" rel="noopener noreferrer">
    <img src="./icons/UAH.png" alt="UAH" width="128" height="128" style="vertical-align: middle; margin-right: 6px;" />
  </a>
  &nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://send.monobank.ua/jar/5uPPFW5FqV" target="_blank" rel="noopener noreferrer">
    <img src="./icons/DOLLAR.png" alt="USD" width="128" height="128" style="vertical-align: middle; margin-right: 6px;" />
  </a>
  &nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://send.monobank.ua/jar/5uPPFW5FqV" target="_blank" rel="noopener noreferrer">
    <img src="./icons/EURO.png" alt="EUR" width="128" height="128" style="vertical-align: middle; margin-right: 6px;" />
  </a>
</p>

---

## 🌟 Key Features

- **Core Reposter Engine:**
  - Runs in the background 24/7.
  - Automatic polling of Telegram channels with configurable interval.
  - Duplicate protection (SQLite database of processed posts).
  - Support for formatted text, photos, and inline buttons.
- **3 Control Interfaces:**
  1. 📱 **Web + JS (Mobile and desktop browsers):** Runs on Python's built-in multi-threaded HTTP server — zero heavy dependencies, works seamlessly on Android (Termux).
  2. 💻 **Python Desktop GUI:** Graphical interface based on **PySide6 (Qt)**.
  3. ⌨️ **Python CLI:** Interactive console menu and command-line runner.
- **3 Telegram Source Modes:**
  - 🔓 **Public Web Scraper:** Instant zero-key scraping for public channels.
  - 🔑 **Telethon Client (`api_id` + `api_hash`):** Full support for private channels, closed groups, and web URLs (`web.telegram.org/k/#...`).
  - 🤖 **Telegram Bot API:** Standard bot token mode.
- **Content Filtering & Moderation:**
  - Blacklist & whitelist keywords.
  - Text length limits (min/max characters).
  - Allow/disallow photos or text-only posts.
  - Skip forwarded posts or posts with external links.
- **Formatting & Text Transformation:**
  - Automatic Markdown conversion for MRIYU (`**bold**`, `__italic__`, etc.).
  - Header (prefix) and footer (suffix).
  - Source links and custom inline buttons.
  - Search and replace rules.

---

## 🚀 Quick Start

### Android (Termux)
```bash
pkg update -y && pkg install -y python git
cd "$HOME"
git clone https://github.com/PraydE007/tg2mriyu-repost-bot.git
cd tg2mriyu-repost-bot
pip install -r requirements.txt
chmod +x start_android.sh
./start_android.sh
```
Open browser at: `http://localhost:8080`

### Desktop (Windows / Linux / macOS)
```bash
pip install -r requirements.txt
python run_server.py
```
Open browser at: `http://localhost:8080`

---

## 💖 Support the Project (Donate)

If you find this project helpful and want to support its active development:

| Currency | Link | Note |
| :---: | :---: | :---: |
| **UAH (₴)** | [Monobank Jar (UAH)](https://send.monobank.ua/jar/5uPPFW5FqV) | Direct Monobank transfer |
| **USD ($)** | [Monobank Jar (USD)](https://send.monobank.ua/jar/5uPPFW5FqV) | International cards, Apple Pay, Google Pay |
| **EUR (€)** | [Monobank Jar (EUR)](https://send.monobank.ua/jar/5uPPFW5FqV) | International cards, Apple Pay, Google Pay |

