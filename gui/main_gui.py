"""
Desktop Graphical User Interface (GUI) for Repost Bot MRIYU.
Built with PySide6 (Qt).
"""

from __future__ import annotations
import sys
import os
from typing import List, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QCheckBox, QComboBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QGroupBox, QFormLayout, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.config import ConfigManager
from core.database import Database
from core.engine import ReposterEngine
from core.mriyu_client import MriyuClient
from core.tg_scraper import TelegramScraper


DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: bold;
    color: #38bdf8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
}
QLineEdit, QSpinBox, QComboBox, QTextEdit {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    color: #ffffff;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #38bdf8;
}
QPushButton {
    background-color: #0088b0;
    color: white;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: bold;
    border: none;
}
QPushButton:hover {
    background-color: #0099c7;
}
QPushButton#btnStop {
    background-color: #ef4444;
}
QPushButton#btnStop:hover {
    background-color: #dc2626;
}
QPushButton#btnStart {
    background-color: #10b981;
}
QPushButton#btnStart:hover {
    background-color: #059669;
}
QPushButton#btnSecondary {
    background-color: #334155;
}
QPushButton#btnSecondary:hover {
    background-color: #475569;
}
QTabWidget::pane {
    border: 1px solid #334155;
    border-radius: 8px;
    background: #0f172a;
}
QTabBar::tab {
    background: #1e293b;
    color: #94a3b8;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background: #334155;
    color: #38bdf8;
    font-weight: bold;
}
QTableWidget {
    background-color: #1e293b;
    border: 1px solid #334155;
    gridline-color: #334155;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #0f172a;
    color: #94a3b8;
    padding: 6px;
    border: 1px solid #334155;
    font-weight: bold;
}
"""


class MainWindow(QMainWindow):
    def __init__(self, config_manager: ConfigManager, database: Database, engine: ReposterEngine):
        super().__init__()
        self.cm = config_manager
        self.db = database
        self.engine = engine

        self.setWindowTitle("Репост Бот: Telegram ➔ MRIYU")
        self.resize(920, 720)
        self.setStyleSheet(DARK_STYLESHEET)

        self._setup_ui()
        self._load_settings()

        # Timer for polling status and logs
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_status)
        self.timer.start(2500)

        # Auto-start engine if configured
        if self.cm.config.server.auto_start:
            self.engine.start()
        self._update_status()

    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Top Control Bar
        control_bar = QHBoxLayout()
        self.lbl_status = QLabel("Статус: Зупинено ⏹")
        self.lbl_status.setStyleSheet("font-size: 15px; font-weight: bold; color: #f87171;")
        control_bar.addWidget(self.lbl_status)

        control_bar.addStretch()

        self.btn_toggle = QPushButton("▶ Запустити")
        self.btn_toggle.setObjectName("btnStart")
        self.btn_toggle.clicked.connect(self._toggle_engine)
        control_bar.addWidget(self.btn_toggle)

        self.btn_check_now = QPushButton("⚡ Перевірити зараз")
        self.btn_check_now.setObjectName("btnSecondary")
        self.btn_check_now.clicked.connect(self._trigger_check)
        control_bar.addWidget(self.btn_check_now)

        main_layout.addLayout(control_bar)

        # Quick Stats Row
        stats_layout = QHBoxLayout()
        self.lbl_stat_reposted = QLabel("Репостнуто: 0")
        self.lbl_stat_filtered = QLabel("Відфільтровано: 0")
        self.lbl_stat_errors = QLabel("Помилок: 0")
        self.lbl_stat_total = QLabel("Всього: 0")

        for lbl, color in [
            (self.lbl_stat_reposted, "#34d399"),
            (self.lbl_stat_filtered, "#fbbf24"),
            (self.lbl_stat_errors, "#f87171"),
            (self.lbl_stat_total, "#38bdf8")
        ]:
            lbl.setStyleSheet(f"background: #1e293b; padding: 6px 12px; border-radius: 6px; font-weight: bold; color: {color};")
            stats_layout.addWidget(lbl)

        main_layout.addLayout(stats_layout)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._build_settings_tab(), "⚙️ Налаштування")
        tabs.addTab(self._build_history_tab(), "📋 Історія постів")
        tabs.addTab(self._build_logs_tab(), "📜 Логи")
        tabs.addTab(self._build_diag_tab(), "🧪 Діагностика")
        main_layout.addWidget(tabs)

    def _build_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Telegram Group
        tg_group = QGroupBox("📢 Telegram Джерело")
        tg_form = QFormLayout(tg_group)

        self.in_tg_channel = QLineEdit()
        self.in_tg_channel.setPlaceholderText("durov або https://t.me/durov або web.telegram.org/k/#-1224603898")

        self.in_tg_mode = QComboBox()
        self.in_tg_mode.addItems([
            "Web-скрейпер (без ключів, публічні)",
            "Telethon (api_id + hash, приватні та публічні)",
            "Telegram Bot API"
        ])
        self.in_tg_mode.currentIndexChanged.connect(self._on_tg_mode_changed)

        self.in_tg_api_id = QLineEdit()
        self.in_tg_api_id.setPlaceholderText("Telegram API ID з my.telegram.org")

        self.in_tg_api_hash = QLineEdit()
        self.in_tg_api_hash.setEchoMode(QLineEdit.Password)
        self.in_tg_api_hash.setPlaceholderText("Telegram API Hash з my.telegram.org")

        self.in_tg_phone = QLineEdit()
        self.in_tg_phone.setPlaceholderText("+380... (номер телефону для Telethon)")

        self.in_tg_bot_token = QLineEdit()
        self.in_tg_bot_token.setEchoMode(QLineEdit.Password)
        self.in_tg_bot_token.setPlaceholderText("Токен бота (лише для режиму Bot API)")

        self.in_tg_interval = QSpinBox()
        self.in_tg_interval.setRange(10, 3600)
        self.in_tg_interval.setValue(60)
        self.in_tg_interval.setSuffix(" сек.")

        self.in_tg_sync_count = QSpinBox()
        self.in_tg_sync_count.setRange(0, 50)
        self.in_tg_sync_count.setValue(3)

        tg_form.addRow("Канал Telegram:", self.in_tg_channel)
        tg_form.addRow("Режим зчитування:", self.in_tg_mode)
        tg_form.addRow("Telegram API ID:", self.in_tg_api_id)
        tg_form.addRow("Telegram API Hash:", self.in_tg_api_hash)
        tg_form.addRow("Номер телефону (Telethon):", self.in_tg_phone)
        tg_form.addRow("Токен бота TG:", self.in_tg_bot_token)
        tg_form.addRow("Інтервал перевірки:", self.in_tg_interval)
        tg_form.addRow("Синхронізація на старті:", self.in_tg_sync_count)
        layout.addWidget(tg_group)

        # MRIYU Group
        mr_group = QGroupBox("🛸 MRIYU Соцмережа")
        mr_form = QFormLayout(mr_group)

        token_row = QHBoxLayout()
        self.in_mr_token = QLineEdit()
        self.in_mr_token.setEchoMode(QLineEdit.Password)
        self.in_mr_token.setPlaceholderText("Токен з mriyu.com/developers?bots")
        btn_load_chats = QPushButton("🔍 Завантажити канали")
        btn_load_chats.clicked.connect(self._load_mriyu_chats)
        token_row.addWidget(self.in_mr_token)
        token_row.addWidget(btn_load_chats)

        self.in_mr_chats_combo = QComboBox()
        self.in_mr_chats_combo.currentIndexChanged.connect(self._on_mriyu_chat_selected)

        self.in_mr_target_type = QComboBox()
        self.in_mr_target_type.addItems(["chat (канал або група)", "user (особисті повідомлення)"])

        self.in_mr_target_id = QLineEdit()
        self.in_mr_target_id.setPlaceholderText("ID каналу/чату (наприклад: 7)")

        self.chk_mr_silent = QCheckBox("Публікувати без звуку (silent)")
        self.chk_mr_button = QCheckBox("Додавати кнопку під постом")
        self.in_mr_btn_text = QLineEdit("Оригінал посту")
        self.in_mr_btn_url = QLineEdit()
        self.in_mr_btn_url.setPlaceholderText("URL (порожньо = посилання на TG)")

        mr_form.addRow("Токен бота MRIYU:", token_row)
        mr_form.addRow("Канали бота:", self.in_mr_chats_combo)
        mr_form.addRow("Тип отримувача:", self.in_mr_target_type)
        mr_form.addRow("Цільовий ID:", self.in_mr_target_id)
        mr_form.addRow("", self.chk_mr_silent)
        mr_form.addRow("", self.chk_mr_button)
        mr_form.addRow("Текст кнопки:", self.in_mr_btn_text)
        mr_form.addRow("URL кнопки:", self.in_mr_btn_url)
        layout.addWidget(mr_group)

        # Filter Group
        flt_group = QGroupBox("🛡️ Фільтрація")
        flt_form = QFormLayout(flt_group)

        self.in_flt_blacklist = QLineEdit()
        self.in_flt_blacklist.setPlaceholderText("реклама, промокод, казино")
        self.chk_flt_photos = QCheckBox("Репостити фотографії")
        self.chk_flt_text_only = QCheckBox("Репостити суто текстові пости")
        self.chk_flt_forwards = QCheckBox("Пропускати переслані повідомлення")
        self.chk_flt_links = QCheckBox("Пропускати пости з посиланнями")

        flt_form.addRow("Чорний список слів:", self.in_flt_blacklist)
        flt_form.addRow("", self.chk_flt_photos)
        flt_form.addRow("", self.chk_flt_text_only)
        flt_form.addRow("", self.chk_flt_forwards)
        flt_form.addRow("", self.chk_flt_links)
        layout.addWidget(flt_group)

        # Formatting Group
        fmt_group = QGroupBox("✏️ Форматування")
        fmt_form = QFormLayout(fmt_group)

        self.in_fmt_prefix = QLineEdit()
        self.in_fmt_prefix.setPlaceholderText("📢 Новини:")
        self.in_fmt_suffix = QLineEdit()
        self.in_fmt_suffix.setPlaceholderText("Підписуйтесь!")
        self.chk_fmt_source = QCheckBox("Додавати посилання на першоджерело TG")
        self.chk_fmt_md = QCheckBox("Конвертувати розмітку у Markdown MRIYU")
        self.chk_fmt_rm_urls = QCheckBox("Видаляти зовнішні посилання з тексту")

        fmt_form.addRow("Шапка (префікс):", self.in_fmt_prefix)
        fmt_form.addRow("Підвал (суфікс):", self.in_fmt_suffix)
        fmt_form.addRow("", self.chk_fmt_source)
        fmt_form.addRow("", self.chk_fmt_md)
        fmt_form.addRow("", self.chk_fmt_rm_urls)
        layout.addWidget(fmt_group)

        # Save Button
        btn_save = QPushButton("💾 Зберегти всі налаштування")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)

        return widget

    def _on_tg_mode_changed(self, idx: int):
        is_telethon = (idx == 1)
        is_bot_api = (idx == 2)
        self.in_tg_api_id.setVisible(is_telethon)
        self.in_tg_api_hash.setVisible(is_telethon)
        self.in_tg_phone.setVisible(is_telethon)
        self.in_tg_bot_token.setVisible(is_bot_api)

    def _build_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        top_row = QHBoxLayout()
        btn_refresh = QPushButton("🔄 Оновити")
        btn_refresh.clicked.connect(self._load_history)
        btn_clear = QPushButton("🗑️ Очистити")
        btn_clear.clicked.connect(self._clear_history)
        top_row.addWidget(btn_refresh)
        top_row.addWidget(btn_clear)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.table_history = QTableWidget(0, 6)
        self.table_history.setHorizontalHeaderLabels(["ID посту", "Час", "Тип", "Статус", "Текст", "MRIYU ID"])
        self.table_history.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.table_history)

        return widget

    def _build_logs_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        top_row = QHBoxLayout()
        btn_refresh = QPushButton("🔄 Оновити")
        btn_refresh.clicked.connect(self._load_logs)
        btn_clear = QPushButton("🗑️ Очистити")
        btn_clear.clicked.connect(self._clear_logs)
        top_row.addWidget(btn_refresh)
        top_row.addWidget(btn_clear)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.text_logs = QTextEdit()
        self.text_logs.setReadOnly(True)
        self.text_logs.setStyleSheet("background-color: #090d16; font-family: Consolas, monospace; font-size: 12px;")
        layout.addWidget(self.text_logs)

        return widget

    def _build_diag_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # TG Test
        g1 = QGroupBox("🔍 Тест Telegram")
        l1 = QVBoxLayout(g1)
        h1 = QHBoxLayout()
        self.diag_tg_in = QLineEdit()
        self.diag_tg_in.setPlaceholderText("durov або посилання / ID")
        btn_test_tg = QPushButton("Перевірити канал")
        btn_test_tg.clicked.connect(self._diag_test_tg)
        h1.addWidget(self.diag_tg_in)
        h1.addWidget(btn_test_tg)
        l1.addLayout(h1)
        self.diag_tg_out = QTextEdit()
        self.diag_tg_out.setReadOnly(True)
        self.diag_tg_out.setMaximumHeight(150)
        l1.addWidget(self.diag_tg_out)
        layout.addWidget(g1)

        # MRIYU Test
        g2 = QGroupBox("🛸 Тест MRIYU API")
        l2 = QVBoxLayout(g2)
        h2 = QHBoxLayout()
        self.diag_mr_in = QLineEdit()
        self.diag_mr_in.setEchoMode(QLineEdit.Password)
        self.diag_mr_in.setPlaceholderText("Токен бота")
        btn_test_mr = QPushButton("Перевірити токен")
        btn_test_mr.clicked.connect(self._diag_test_mr)
        h2.addWidget(self.diag_mr_in)
        h2.addWidget(btn_test_mr)
        l2.addLayout(h2)
        self.diag_mr_out = QTextEdit()
        self.diag_mr_out.setReadOnly(True)
        self.diag_mr_out.setMaximumHeight(150)
        l2.addWidget(self.diag_mr_out)
        layout.addWidget(g2)

        layout.addStretch()
        return widget

    def _load_settings(self):
        cfg = self.cm.config
        self.in_tg_channel.setText(cfg.telegram.channel)

        mode_idx = 0
        if cfg.telegram.mode == "telethon":
            mode_idx = 1
        elif cfg.telegram.mode == "bot_api":
            mode_idx = 2
        self.in_tg_mode.setCurrentIndex(mode_idx)
        self._on_tg_mode_changed(mode_idx)

        self.in_tg_api_id.setText(cfg.telegram.api_id or "")
        self.in_tg_api_hash.setText(cfg.telegram.api_hash or "")
        self.in_tg_phone.setText(cfg.telegram.phone or "")
        self.in_tg_bot_token.setText(cfg.telegram.bot_token or "")
        self.in_tg_interval.setValue(cfg.telegram.poll_interval)
        self.in_tg_sync_count.setValue(cfg.telegram.initial_sync_count)

        self.in_mr_token.setText(cfg.mriyu.token)
        self.in_mr_target_type.setCurrentIndex(0 if cfg.mriyu.target_type == "chat" else 1)
        self.in_mr_target_id.setText(cfg.mriyu.target_id)
        self.chk_mr_silent.setChecked(cfg.mriyu.silent)
        self.chk_mr_button.setChecked(cfg.mriyu.add_button)
        self.in_mr_btn_text.setText(cfg.mriyu.button_text)
        self.in_mr_btn_url.setText(cfg.mriyu.button_url)

        self.in_flt_blacklist.setText(", ".join(cfg.filter.keyword_blacklist))
        self.chk_flt_photos.setChecked(cfg.filter.allow_photos)
        self.chk_flt_text_only.setChecked(cfg.filter.allow_text_only)
        self.chk_flt_forwards.setChecked(cfg.filter.ignore_forwards)
        self.chk_flt_links.setChecked(cfg.filter.skip_links)

        self.in_fmt_prefix.setText(cfg.formatting.header_prefix)
        self.in_fmt_suffix.setText(cfg.formatting.footer_suffix)
        self.chk_fmt_source.setChecked(cfg.formatting.add_source_link)
        self.chk_fmt_md.setChecked(cfg.formatting.convert_markdown)
        self.chk_fmt_rm_urls.setChecked(cfg.formatting.remove_urls)

    def _save_settings(self):
        modes = ["scraper", "telethon", "bot_api"]
        chosen_mode = modes[self.in_tg_mode.currentIndex()]
        upd = {
            "telegram": {
                "channel": self.in_tg_channel.text().strip(),
                "mode": chosen_mode,
                "api_id": self.in_tg_api_id.text().strip(),
                "api_hash": self.in_tg_api_hash.text().strip(),
                "phone": self.in_tg_phone.text().strip(),
                "bot_token": self.in_tg_bot_token.text().strip(),
                "poll_interval": self.in_tg_interval.value(),
                "initial_sync_count": self.in_tg_sync_count.value(),
            },
            "mriyu": {
                "token": self.in_mr_token.text().strip(),
                "target_type": "chat" if self.in_mr_target_type.currentIndex() == 0 else "user",
                "target_id": self.in_mr_target_id.text().strip(),
                "silent": self.chk_mr_silent.isChecked(),
                "add_button": self.chk_mr_button.isChecked(),
                "button_text": self.in_mr_btn_text.text().strip(),
                "button_url": self.in_mr_btn_url.text().strip(),
            },
            "filter": {
                "keyword_blacklist": [w.strip() for w in self.in_flt_blacklist.text().split(",") if w.strip()],
                "allow_photos": self.chk_flt_photos.isChecked(),
                "allow_text_only": self.chk_flt_text_only.isChecked(),
                "ignore_forwards": self.chk_flt_forwards.isChecked(),
                "skip_links": self.chk_flt_links.isChecked(),
            },
            "formatting": {
                "header_prefix": self.in_fmt_prefix.text(),
                "footer_suffix": self.in_fmt_suffix.text(),
                "add_source_link": self.chk_fmt_source.isChecked(),
                "convert_markdown": self.chk_fmt_md.isChecked(),
                "remove_urls": self.chk_fmt_rm_urls.isChecked(),
            }
        }
        self.cm.update(upd)
        QMessageBox.information(self, "Збережено", "Налаштування успішно збережено!")

    def _toggle_engine(self):
        if self.engine.is_running:
            self.engine.stop()
        else:
            self.engine.start()
        self._update_status()

    def _trigger_check(self):
        self.engine.trigger_manual_check()
        QMessageBox.information(self, "Запит", "Позачергову перевірку запущено!")

    def _update_status(self):
        st = self.engine.get_status()
        if st["running"]:
            self.lbl_status.setText("Статус: Працює ▶")
            self.lbl_status.setStyleSheet("font-size: 15px; font-weight: bold; color: #34d399;")
            self.btn_toggle.setText("⏹ Зупинити")
            self.btn_toggle.setObjectName("btnStop")
        else:
            self.lbl_status.setText("Статус: Зупинено ⏹")
            self.lbl_status.setStyleSheet("font-size: 15px; font-weight: bold; color: #f87171;")
            self.btn_toggle.setText("▶ Запустити")
            self.btn_toggle.setObjectName("btnStart")

        self.btn_toggle.setStyle(self.btn_toggle.style())

        stats = st.get("stats", {})
        self.lbl_stat_reposted.setText(f"Репостнуто: {stats.get('reposted', 0)}")
        self.lbl_stat_filtered.setText(f"Відфільтровано: {stats.get('filtered', 0)}")
        self.lbl_stat_errors.setText(f"Помилок: {stats.get('errors', 0)}")
        self.lbl_stat_total.setText(f"Всього: {stats.get('total_processed', 0)}")

    def _load_mriyu_chats(self):
        tok = self.in_mr_token.text().strip()
        if not tok:
            QMessageBox.warning(self, "Увага", "Введіть токен MRIYU")
            return
        client = MriyuClient(tok)
        me = client.get_me()
        if not me.get("ok"):
            QMessageBox.critical(self, "Помилка", f"Недійсний токен: {me.get('description')}")
            return
        chats_res = client.get_chats()
        chats = chats_res.get("result", []) if chats_res.get("ok") else []
        self.in_mr_chats_combo.clear()
        self.in_mr_chats_combo.addItem("-- Оберіть канал бота зі списку --", "")
        for c in chats:
            self.in_mr_chats_combo.addItem(f"{c.get('title')} (ID: {c.get('id')})", str(c.get('id')))
        QMessageBox.information(self, "Успіх", f"Знайдено каналів: {len(chats)}")

    def _on_mriyu_chat_selected(self, idx):
        val = self.in_mr_chats_combo.currentData()
        if val:
            self.in_mr_target_id.setText(str(val))

    def _load_history(self):
        posts = self.db.get_recent_posts(limit=50)
        self.table_history.setRowCount(len(posts))
        for r, p in enumerate(posts):
            self.table_history.setItem(r, 0, QTableWidgetItem(p["post_id"]))
            self.table_history.setItem(r, 1, QTableWidgetItem(p["created_at"]))
            self.table_history.setItem(r, 2, QTableWidgetItem("📷 Фото" if p["has_photo"] else "📝 Текст"))
            self.table_history.setItem(r, 3, QTableWidgetItem(p["status"]))
            self.table_history.setItem(r, 4, QTableWidgetItem((p["text_snippet"] or "")[:100]))
            self.table_history.setItem(r, 5, QTableWidgetItem(p["mriyu_msg_id"] or ""))

    def _clear_history(self):
        if QMessageBox.question(self, "Підтвердження", "Очистити всю історію оброблених постів?") == QMessageBox.Yes:
            self.db.clear_processed_posts()
            self._load_history()

    def _load_logs(self):
        logs = self.db.get_recent_logs(limit=100)
        lines = []
        for l in reversed(logs):
            lines.append(f"[{l['timestamp']}] [{l['level']}] {l['message']} {l['details']}")
        self.text_logs.setPlainText("\n".join(lines))

    def _clear_logs(self):
        self.db.clear_logs()
        self.text_logs.clear()

    def _diag_test_tg(self):
        ch = self.diag_tg_in.text().strip() or self.in_tg_channel.text().strip()
        if not ch:
            return

        if self.in_tg_mode.currentIndex() == 1:
            # Telethon mode
            from core.tg_telethon import TelethonService
            service = TelethonService.get_instance()
            try:
                posts = service.fetch_channel_posts(
                    ch,
                    limit=5,
                    api_id=self.in_tg_api_id.text().strip(),
                    api_hash=self.in_tg_api_hash.text().strip()
                )
                if not posts:
                    self.diag_tg_out.setPlainText("❌ Telethon не повернув постів з цього каналу/чату.")
                    return
                lines = [f"✅ Telethon: успішно отримано {len(posts)} постів:"]
                for p in posts[-3:]:
                    lines.append(f"- ID: {p.post_id} | Фото: {len(p.photos)} | Текст: {p.raw_text[:60]}...")
                self.diag_tg_out.setPlainText("\n".join(lines))
                return
            except Exception as e:
                self.diag_tg_out.setPlainText(f"❌ Помилка Telethon: {e}")
                return

        # Scraper mode
        posts = TelegramScraper.fetch_channel_posts(ch)
        if not posts:
            self.diag_tg_out.setPlainText("❌ Не вдалося отримати пости. Перевірте публічність каналу або увімкніть Telethon.")
            return
        lines = [f"✅ Отримано {len(posts)} постів з каналу:"]
        for p in posts[-3:]:
            lines.append(f"- ID: {p.post_id} | Фото: {len(p.photos)} | Текст: {p.raw_text[:60]}...")
        self.diag_tg_out.setPlainText("\n".join(lines))

    def _diag_test_mr(self):
        tok = self.diag_mr_in.text().strip() or self.in_mr_token.text().strip()
        if not tok:
            return
        client = MriyuClient(tok)
        res = client.get_me()
        if res.get("ok"):
            b = res["result"]
            self.diag_mr_out.setPlainText(f"✅ Успішно! Бот: {b.get('name')} (@{b.get('username')})\nID: {b.get('id')}\nПідписників: {b.get('subscribers')}")
        else:
            self.diag_mr_out.setPlainText(f"❌ Помилка: {res.get('description')} (код {res.get('error_code')})")


def main():
    cm = ConfigManager()
    db = Database()
    engine = ReposterEngine(cm, db)

    app = QApplication(sys.argv)
    window = MainWindow(cm, db, engine)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
