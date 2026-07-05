"""Rewrite tray.py with a Qt-based implementation."""
from pathlib import Path

content = '''"""System tray icon and menu for GamerScroll using Qt."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QBrush, QPolygonF
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


class TrayManager:
    """Manages the system tray icon, menu, and status tooltip."""

    def __init__(
        self,
        on_open_settings: Callable[[], None],
        on_toggle_pause: Callable[[], None],
        on_launch_browser: Callable[[], None],
        on_exit: Callable[[], None],
        icon: Optional[QIcon] = None,
    ):
        self.on_open_settings = on_open_settings
        self.on_toggle_pause = on_toggle_pause
        self.on_launch_browser = on_launch_browser
        self.on_exit = on_exit
        self._icon = icon or self._default_icon()
        self._tray: Optional[QSystemTrayIcon] = None
        self._menu: Optional[QMenu] = None
        self._pause_action: Optional[QAction] = None
        self._paused = False
        self._status = "GamerScroll — waiting"

    def _create_menu(self) -> QMenu:
        menu = QMenu()
        self._pause_action = QAction("Pause", menu)
        self._pause_action.triggered.connect(self._on_toggle_pause)
        menu.addAction(self._pause_action)

        launch_action = QAction("Launch Browser", menu)
        launch_action.triggered.connect(self._on_launch_browser)
        menu.addAction(launch_action)

        settings_action = QAction("Settings", menu)
        settings_action.triggered.connect(self._on_open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(self._on_exit)
        menu.addAction(exit_action)
        return menu

    def _on_open_settings(self) -> None:
        try:
            self.on_open_settings()
        except Exception as exc:
            print(f"[Tray] Settings callback failed: {exc}")

    def _on_toggle_pause(self) -> None:
        try:
            self.on_toggle_pause()
        except Exception as exc:
            print(f"[Tray] Pause callback failed: {exc}")

    def _on_launch_browser(self) -> None:
        try:
            self.on_launch_browser()
        except Exception as exc:
            print(f"[Tray] Launch browser callback failed: {exc}")

    def _on_exit(self) -> None:
        try:
            self.on_exit()
        except Exception as exc:
            print(f"[Tray] Exit callback failed: {exc}")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_open_settings()

    def start(self) -> None:
        if self._tray is not None:
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("[Tray] System tray is not available")
            return

        self._menu = self._create_menu()
        self._tray = QSystemTrayIcon(self._icon)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)
        self._update_tooltip()
        self._tray.show()

    def stop(self) -> None:
        if self._tray:
            self._tray.hide()
            self._tray.deleteLater()
            self._tray = None
        self._menu = None

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        if self._pause_action:
            self._pause_action.setText("Resume" if paused else "Pause")
        self._update_tooltip()

    def set_status(self, message: str) -> None:
        self._status = message
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        if self._tray is None:
            return
        state = "paused" if self._paused else "running"
        self._tray.setToolTip(f"GamerScroll — {state}\\n{self._status}")

    @staticmethod
    def _default_icon() -> QIcon:
        """Return the application icon, generating a fallback if needed."""
        icon_path = _asset_path("icon.ico")
        if icon_path.is_file():
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                return icon
        return TrayManager._generate_fallback_icon()

    @staticmethod
    def _generate_fallback_icon() -> QIcon:
        """Draw a simple 64x64 blue rounded-square icon with a white caret."""
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(50, 120, 220)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(4, 4, size - 8, size - 8, 12, 12)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        polygon = QPolygonF([
            QPointF(size / 2, 18),
            QPointF(18, 42),
            QPointF(46, 42),
        ])
        painter.drawPolygon(polygon)
        painter.end()
        return QIcon(pixmap)


def _asset_path(name: str) -> Path:
    """Resolve a bundled asset path in both source and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets" / name
'''

Path('gamerscroll/tray.py').write_text(content, encoding='utf-8')
print('tray.py rewritten')
