"""PyQt6 settings window for GamerScroll."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List, Optional

from loguru import logger
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gamerscroll.browser import BrowserInfo, detect_browsers, list_profiles
from gamerscroll.config import Config
from gamerscroll.logger import _log_dir


class KeyCaptureDialog(QDialog):
    """Modal dialog that captures the next global-ish key press."""

    key_captured = pyqtSignal(str)

    def __init__(self, label: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Capture key")
        self.setFixedSize(360, 140)
        self.setModal(True)
        layout = QVBoxLayout(self)
        self._label = QLabel(f"Press the key for: <b>{label}</b><br>Press Esc to cancel.")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)
        self._captured: Optional[str] = None

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:  # noqa: N802
        if event is None:
            return
        key = event.key()

        if key == Qt.Key.Key_Escape:
            self.reject()
            return

        # Prefer named keys for function/special keys; otherwise char.
        key_name = QKeySequence(key).toString()
        if not key_name:
            key_name = event.text().lower()

        # Normalize common names to pynput-compatible lower-case.
        self._captured = self._normalize(key_name)
        self.key_captured.emit(self._captured)
        self.accept()

    @staticmethod
    def _normalize(name: str) -> str:
        name = name.strip().lower()
        mapping = {
            "esc": "esc",
            "return": "enter",
            "\r": "enter",
            "\t": "tab",
            " ": "space",
        }
        return mapping.get(name, name)


class SettingsWindow(QWidget):
    """Main settings window."""

    config_changed = pyqtSignal(Config)
    launch_browser_requested = pyqtSignal()
    test_pause_play_requested = pyqtSignal()
    test_next_requested = pyqtSignal()
    test_prev_requested = pyqtSignal()

    def __init__(self, config: Config, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("GamerScroll Settings")
        self.setMinimumWidth(500)
        self._config = config
        self._browsers: List[BrowserInfo] = []
        self._build_ui()
        self._refresh_browser_list()
        self._load_config_into_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Browser group
        browser_group = QGroupBox("Browser")
        browser_layout = QFormLayout(browser_group)

        self._browser_combo = QComboBox()
        self._browser_combo.currentIndexChanged.connect(self._on_browser_changed)
        browser_layout.addRow("Detected browser:", self._browser_combo)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_browser)
        browser_layout.addRow("", browse_btn)

        self._exe_edit = QLineEdit()
        self._exe_edit.setReadOnly(True)
        browser_layout.addRow("Executable:", self._exe_edit)

        self._profile_combo = QComboBox()
        self._profile_combo.setEditable(True)
        browser_layout.addRow("Profile:", self._profile_combo)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(9222)
        self._port_spin.valueChanged.connect(self._update_manual_label)
        browser_layout.addRow("CDP port:", self._port_spin)

        self._auto_launch_check = QCheckBox("Launch browser automatically if CDP is not available")
        self._auto_launch_check.stateChanged.connect(self._update_warning_visibility)
        browser_layout.addRow("", self._auto_launch_check)

        self._auto_launch_warning = QLabel(
            "Warning: auto-launch will close existing browser windows and reopen them."
        )
        self._auto_launch_warning.setWordWrap(True)
        self._auto_launch_warning.setStyleSheet("color: #c06000; font-size: 11px;")
        browser_layout.addRow("", self._auto_launch_warning)

        launch_btn = QPushButton("Launch Browser Now")
        launch_btn.setToolTip("Closes existing browser windows and restarts with CDP enabled")
        launch_btn.clicked.connect(self.launch_browser_requested.emit)
        browser_layout.addRow("", launch_btn)

        self._manual_label = QLabel("")
        self._manual_label.setTextFormat(Qt.TextFormat.RichText)
        self._manual_label.setWordWrap(True)
        browser_layout.addRow("", self._manual_label)

        layout.addWidget(browser_group)

        # Media key group
        media_key_group = QGroupBox("Media Key")
        media_key_layout = QFormLayout(media_key_group)

        self._media_key_edit = QLineEdit()
        self._media_key_edit.setReadOnly(True)
        media_key_capture = QPushButton("Capture")
        media_key_capture.clicked.connect(lambda: self._capture_key("media key", self._media_key_edit))
        media_key_row = QHBoxLayout()
        media_key_row.addWidget(self._media_key_edit)
        media_key_row.addWidget(media_key_capture)
        media_key_layout.addRow("Media key:", media_key_row)

        layout.addWidget(media_key_group)

        # Gesture timing group
        timing_group = QGroupBox("Gesture Timing")
        timing_layout = QFormLayout(timing_group)

        self._hold_threshold_spin = QSpinBox()
        self._hold_threshold_spin.setRange(50, 5000)
        self._hold_threshold_spin.setSingleStep(50)
        self._hold_threshold_spin.setValue(500)
        self._hold_threshold_spin.setSuffix(" ms")
        timing_layout.addRow("Hold threshold:", self._hold_threshold_spin)

        self._double_click_window_spin = QSpinBox()
        self._double_click_window_spin.setRange(50, 2000)
        self._double_click_window_spin.setSingleStep(50)
        self._double_click_window_spin.setValue(300)
        self._double_click_window_spin.setSuffix(" ms")
        timing_layout.addRow("Double-click window:", self._double_click_window_spin)

        self._debounce_spin = QSpinBox()
        self._debounce_spin.setRange(0, 1000)
        self._debounce_spin.setSingleStep(10)
        self._debounce_spin.setValue(150)
        self._debounce_spin.setSuffix(" ms")
        timing_layout.addRow("Debounce:", self._debounce_spin)

        test_layout = QHBoxLayout()
        test_pause_btn = QPushButton("Test Pause/Play")
        test_pause_btn.clicked.connect(self.test_pause_play_requested.emit)
        test_next_btn = QPushButton("Test Next")
        test_next_btn.clicked.connect(self.test_next_requested.emit)
        test_prev_btn = QPushButton("Test Prev")
        test_prev_btn.clicked.connect(self.test_prev_requested.emit)
        test_layout.addWidget(test_pause_btn)
        test_layout.addWidget(test_next_btn)
        test_layout.addWidget(test_prev_btn)
        timing_layout.addRow("", test_layout)

        layout.addWidget(timing_group)

        # Logging group
        logging_group = QGroupBox("Logging")
        logging_layout = QFormLayout(logging_group)

        self._log_level_combo = QComboBox()
        self._log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        logging_layout.addRow("Log level:", self._log_level_combo)

        self._log_path_label = QLabel("")
        self._log_path_label.setWordWrap(True)
        self._log_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        logging_layout.addRow("Log file:", self._log_path_label)

        open_log_btn = QPushButton("Open log folder")
        open_log_btn.clicked.connect(self._open_log_folder)
        logging_layout.addRow("", open_log_btn)

        layout.addWidget(logging_group)

        # Startup group
        startup_group = QGroupBox("Startup")
        startup_layout = QFormLayout(startup_group)
        self._auto_start_check = QCheckBox("Start GamerScroll with Windows")
        startup_layout.addRow("", self._auto_start_check)
        layout.addWidget(startup_group)

        # Action buttons
        action_layout = QHBoxLayout()
        self._save_btn = QPushButton("Save")
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._save)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._load_config_into_ui)
        action_layout.addStretch()
        action_layout.addWidget(self._save_btn)
        action_layout.addWidget(self._cancel_btn)
        layout.addLayout(action_layout)

        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

    def _refresh_browser_list(self) -> None:
        self._browsers = detect_browsers()
        self._browser_combo.blockSignals(True)
        self._browser_combo.clear()
        self._browser_combo.addItem("Custom...", None)
        selected_index = 0
        for idx, browser in enumerate(self._browsers, start=1):
            self._browser_combo.addItem(browser.name, browser)
            if browser.name == self._config.browser_name:
                selected_index = idx
        self._browser_combo.setCurrentIndex(selected_index)
        self._browser_combo.blockSignals(False)
        self._on_browser_changed(selected_index)

    def _on_browser_changed(self, index: int) -> None:
        browser: Optional[BrowserInfo] = self._browser_combo.itemData(index)
        if browser:
            self._exe_edit.setText(str(browser.exe))
            self._populate_profiles(browser.user_data_dir)
        else:
            self._exe_edit.setText(self._config.browser_exe)
            self._populate_profiles_from_config()
        self._update_manual_label()

    def _populate_profiles(self, user_data_dir: Path) -> None:
        profiles = list_profiles(user_data_dir)
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        for p in profiles:
            self._profile_combo.addItem(p)
        if self._config.profile in profiles:
            self._profile_combo.setCurrentText(self._config.profile)
        elif not profiles:
            self._profile_combo.setEditText(self._config.profile)
        self._profile_combo.blockSignals(False)

    def _populate_profiles_from_config(self) -> None:
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        self._profile_combo.setEditable(True)
        self._profile_combo.setEditText(self._config.profile)
        self._profile_combo.blockSignals(False)

    def _browse_browser(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select browser executable",
            str(Path.home()),
            "Executables (*.exe)",
        )
        if path:
            self._exe_edit.setText(path)
            self._browser_combo.setCurrentIndex(0)
            self._update_manual_label()

    def _capture_key(self, label: str, target: QLineEdit) -> None:
        dlg = KeyCaptureDialog(label, self)
        dlg.key_captured.connect(target.setText)
        dlg.exec()

    def _load_config_into_ui(self) -> None:
        self._exe_edit.setText(self._config.browser_exe)
        self._port_spin.setValue(self._config.cdp_port)
        self._media_key_edit.setText(self._config.media_key)
        self._hold_threshold_spin.setValue(self._config.hold_threshold_ms)
        self._double_click_window_spin.setValue(self._config.double_click_window_ms)
        self._debounce_spin.setValue(self._config.debounce_ms)
        self._auto_launch_check.setChecked(self._config.auto_launch_browser)
        self._auto_start_check.setChecked(self._config.auto_start_windows)
        self._log_level_combo.setCurrentText(self._config.log_level.upper())
        self._log_path_label.setText(str(_log_dir() / "gamerscroll.log"))
        self._refresh_browser_list()
        self._update_warning_visibility()
        self._update_manual_label()

    def _update_warning_visibility(self) -> None:
        self._auto_launch_warning.setVisible(self._auto_launch_check.isChecked())

    def _update_manual_label(self) -> None:
        port = self._port_spin.value()
        exe = self._exe_edit.text() or "C:\\Path\\To\\browser.exe"
        text = (
            "Or launch the browser manually with CDP enabled:<br>"
            f"<code>\"{exe}\" --profile-directory=Default --remote-debugging-port={port}</code>"
        )
        self._manual_label.setText(text)

    def _save(self) -> None:
        new_config = Config(
            browser_name=self._browser_combo.currentText(),
            browser_exe=self._exe_edit.text(),
            user_data_dir=str(self._selected_user_data_dir()),
            profile=self._profile_combo.currentText(),
            cdp_port=self._port_spin.value(),
            cdp_host=self._config.cdp_host,
            media_key=self._media_key_edit.text().lower(),
            hold_threshold_ms=self._hold_threshold_spin.value(),
            double_click_window_ms=self._double_click_window_spin.value(),
            debounce_ms=self._debounce_spin.value(),
            auto_launch_browser=self._auto_launch_check.isChecked(),
            auto_start_windows=self._auto_start_check.isChecked(),
            disabled=self._config.disabled,
            log_level=self._log_level_combo.currentText(),
        )
        errors = new_config.validate()
        if errors:
            logger.warning("Settings validation failed: {}", errors)
            QMessageBox.warning(self, "Invalid settings", "\n".join(errors))
            return
        self._config = new_config
        self._config.save()
        logger.info("Settings saved from GUI")
        self.config_changed.emit(self._config)
        self._status_label.setText("Settings saved.")

    def _selected_user_data_dir(self) -> Optional[Path]:
        browser: Optional[BrowserInfo] = self._browser_combo.currentData()
        if browser:
            return browser.user_data_dir
        # Try to derive from exe parent as a fallback.
        exe = Path(self._exe_edit.text())
        candidate = exe.parent.parent / "User Data"
        if candidate.is_dir():
            return candidate
        return Path(self._config.user_data_dir) if self._config.user_data_dir else None

    @staticmethod
    def _open_log_folder() -> None:
        log_dir = _log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(log_dir)

    def set_status(self, message: str) -> None:
        self._status_label.setText(message)
