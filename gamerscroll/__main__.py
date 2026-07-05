"""Entry point for GamerScroll."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from loguru import logger
from PyQt6.QtWidgets import QApplication, QMessageBox

from gamerscroll.browser import (
    BrowserInfo,
    detect_browsers,
    is_browser_running,
    launch_browser,
    terminate_browser,
    wait_for_cdp,
)
from gamerscroll.config import Config
from gamerscroll.gui import SettingsWindow
from gamerscroll.hotkeys import HotkeyListener
from gamerscroll.logger import set_level, setup_logging
from gamerscroll.scroller import Scroller, ScrollerStatus
from gamerscroll.startup import SingleInstanceGuard, get_auto_start, set_auto_start
from gamerscroll.tray import TrayManager


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="GamerScroll")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override the configured log level for this run.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Shortcut for --log-level DEBUG.",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Force logging to the console (useful for debugging from source).",
    )
    return parser.parse_args(argv[1:])


class GamerScrollApp:
    def __init__(self, log_level_override: Optional[str] = None, force_console: bool = False) -> None:
        self._log_level_override = log_level_override
        self._force_console = force_console
        self.config = Config.load()
        self._setup_logging()

        # Ensure registry reflects saved config.
        if self.config.auto_start_windows != get_auto_start():
            logger.info("Syncing auto-start registry to config value: {}", self.config.auto_start_windows)
            set_auto_start(self.config.auto_start_windows)

        logger.info("Initializing Qt application")
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)

        logger.info("Creating Scroller")
        self.scroller = Scroller(self.config, on_status=self._on_scroller_status)
        logger.info("Creating HotkeyListener (down={}, up={})",
                    self.config.scroll_down_key, self.config.scroll_up_key)
        self.hotkeys = HotkeyListener(
            self.config.scroll_down_key,
            self.config.scroll_up_key,
            on_scroll_down=self._on_scroll_down,
            on_scroll_up=self._on_scroll_up,
        )
        logger.info("Creating TrayManager")
        self.tray = TrayManager(
            on_open_settings=self._open_settings,
            on_toggle_pause=self._toggle_pause,
            on_launch_browser=lambda: self._launch_browser(confirm=True),
            on_exit=self._exit,
        )
        self.settings_window: Optional[SettingsWindow] = None

    def _setup_logging(self) -> None:
        effective_level = self._log_level_override or self.config.log_level
        console = self._force_console or None
        log_path = setup_logging(effective_level, console=console)
        logger.info("GamerScroll starting")
        logger.info("Config path: {}", Config.default_path())
        logger.info("Log file: {}", log_path)

    def _on_scroll_down(self) -> None:
        logger.debug("Scroll-down hotkey dispatched")
        threading.Thread(target=self.scroller.scroll_down, daemon=True).start()

    def _on_scroll_up(self) -> None:
        logger.debug("Scroll-up hotkey dispatched")
        threading.Thread(target=self.scroller.scroll_up, daemon=True).start()

    def _on_scroller_status(self, status: ScrollerStatus) -> None:
        self.tray.set_status(status.message)
        if status.ok:
            logger.info("Scroller status: {}", status.message)
        else:
            logger.warning("Scroller status: {}", status.message)

    def _open_settings(self) -> None:
        logger.info("Opening settings window")
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self.config)
            self.settings_window.config_changed.connect(self._apply_config)
            self.settings_window.launch_browser_requested.connect(self._launch_browser)
            self.settings_window.test_scroll_down_requested.connect(self.scroller.scroll_down)
            self.settings_window.test_scroll_up_requested.connect(self.scroller.scroll_up)
            self.settings_window.destroyed.connect(lambda: setattr(self, "settings_window", None))
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _toggle_pause(self) -> None:
        self.config.paused = not self.config.paused
        logger.info("Pause toggled: {}", self.config.paused)
        self.config.save()
        self.scroller.update_config(self.config)
        self.tray.set_paused(self.config.paused)

    def _apply_config(self, config: Config) -> None:
        logger.info("Applying updated config")
        old_level = self.config.log_level
        self.config = config
        self.scroller.update_config(config)
        self.hotkeys.restart(config.scroll_down_key, config.scroll_up_key)
        if config.auto_start_windows != get_auto_start():
            logger.info("Auto-start changed to {}", config.auto_start_windows)
            set_auto_start(config.auto_start_windows)
        # Update log level at runtime unless overridden by CLI.
        if self._log_level_override is None and config.log_level != old_level:
            logger.info("Log level changed via settings to {}", config.log_level)
            set_level(config.log_level)
        self.tray.set_status("Settings updated")

    def _launch_browser(self, confirm: bool = False) -> None:
        exe = Path(self.config.browser_exe)
        if not exe.is_file():
            logger.warning("Browser executable not set or missing: {}", self.config.browser_exe)
            self.tray.set_status("Browser executable not set")
            self._open_settings()
            return

        exe_name = exe.name
        logger.info("Launching browser: {}", exe)
        if is_browser_running(exe_name):
            logger.info("Browser process {} is already running; checking CDP reachability", exe_name)
            # If already running, check whether CDP is reachable.
            try:
                from gamerscroll.cdp import find_active_tab_ws
                find_active_tab_ws(self.config.cdp_host, self.config.cdp_port, timeout=1.5)
                logger.info("Existing browser already has CDP enabled on port {}", self.config.cdp_port)
                self.tray.set_status("Browser already has CDP enabled")
                return
            except Exception as exc:
                logger.info("CDP not reachable on existing browser ({}); will restart", exc)

            if confirm:
                reply = QMessageBox.question(
                    self.settings_window or None,
                    "Close existing browser?",
                    f"{self.config.browser_name} is already running without CDP enabled.\n\n"
                    "Launching it with CDP will close all existing windows and reopen them.\n"
                    "Unsaved work in the browser may be lost. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    logger.info("User cancelled browser launch")
                    self.tray.set_status("Browser launch cancelled")
                    return

            self.tray.set_status("Closing existing browser...")
            terminate_browser(exe_name)

        self.tray.set_status("Launching browser with CDP...")
        logger.info("Starting browser with profile '{}' on CDP port {}",
                    self.config.profile, self.config.cdp_port)
        proc = launch_browser(exe, self.config.profile, self.config.cdp_port)
        logger.info("Browser process started (PID: {})", proc.pid)
        if wait_for_cdp(self.config.cdp_host, self.config.cdp_port, timeout=30.0):
            logger.info("Browser CDP endpoint is reachable")
            self.tray.set_status("Browser connected via CDP")
        else:
            logger.error("Browser CDP endpoint did not become reachable within 30 seconds")
            self.tray.set_status("Browser did not expose CDP in time")

    def _auto_launch_if_needed(self) -> None:
        if not self.config.auto_launch_browser:
            logger.info("Auto-launch disabled in config")
            return
        if not self.config.browser_exe or not Path(self.config.browser_exe).is_file():
            logger.info("Auto-launch skipped: browser executable not configured")
            return
        logger.info("Auto-launch check: looking for existing CDP endpoint")
        try:
            from gamerscroll.cdp import find_active_tab_ws
            find_active_tab_ws(self.config.cdp_host, self.config.cdp_port, timeout=1.5)
            logger.info("Connected to existing browser via CDP")
            self.tray.set_status("Connected to existing browser")
            return
        except Exception as exc:
            logger.info("No existing CDP endpoint found ({}); launching browser", exc)
        self._launch_browser(confirm=True)

    def _exit(self) -> None:
        logger.info("Shutdown requested")
        self.hotkeys.stop()
        self.tray.stop()
        self.qt_app.quit()
        logger.info("Shutdown complete")

    def run(self) -> int:
        guard = SingleInstanceGuard()
        if not guard.acquire():
            logger.warning("Another instance is already running")
            QMessageBox.information(
                None,
                "GamerScroll already running",
                "GamerScroll is already running. Use the system tray icon to open settings.",
            )
            return 0

        logger.info("Single-instance mutex acquired")
        try:
            self.tray.start()
            self.hotkeys.start()
            self._auto_launch_if_needed()
            if not self.config.browser_exe or not Path(self.config.browser_exe).is_file():
                logger.info("Browser not configured; opening settings window")
                self._open_settings()
            logger.info("Entering Qt event loop")
            return self.qt_app.exec()
        except Exception:
            logger.exception("Fatal error in main loop")
            raise
        finally:
            logger.info("Releasing single-instance mutex")
            guard.release()


if __name__ == "__main__":
    args = _parse_args(sys.argv)
    level = args.log_level or ("DEBUG" if args.verbose else None)
    sys.exit(GamerScrollApp(log_level_override=level, force_console=args.console).run())
