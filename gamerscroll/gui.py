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
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gamerscroll.browser import BrowserInfo, detect_browsers, list_profiles
from gamerscroll.config import Config, GESTURE_BINDING_NAMES, normalize_keyboard_chord
from gamerscroll.controller import SiteProfileSetup, TabTarget
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


class ChordCaptureDialog(QDialog):
    """Capture a single key or simultaneous modifier chord, never a sequence."""

    chord_captured = pyqtSignal(str)

    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Capture shortcut")
        self.setFixedSize(400, 150)
        self.setModal(True)
        layout = QVBoxLayout(self)
        message = (
            f"Press one key or a shortcut for: <b>{label}</b><br>"
            "Use keys pressed together, such as Ctrl+L. Press Esc to cancel."
        )
        self._label = QLabel(message)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:  # noqa: N802
        if event is None:
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        if key in {
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Meta,
        }:
            self._label.setText("Hold your modifier, then press its key.")
            return

        key_name = QKeySequence(key).toString()
        if not key_name:
            self._label.setText("That key is not supported. Try another key.")
            return
        modifiers: list[str] = []
        held = event.modifiers()
        if held & Qt.KeyboardModifier.ControlModifier:
            modifiers.append("Ctrl")
        if held & Qt.KeyboardModifier.AltModifier:
            modifiers.append("Alt")
        if held & Qt.KeyboardModifier.ShiftModifier:
            modifiers.append("Shift")
        if held & Qt.KeyboardModifier.MetaModifier:
            modifiers.append("Meta")
        chord = normalize_keyboard_chord("+".join([*modifiers, key_name]))
        if chord is None:
            self._label.setText("Use one key or a modifier chord, not text or a sequence.")
            return
        self.chord_captured.emit(chord)
        self.accept()


def capture_chord(label: str, target: QLineEdit, parent: QWidget) -> None:
    """Capture a Keyboard Chord into a read-only binding field."""
    dialog = ChordCaptureDialog(label, parent)
    dialog.chord_captured.connect(target.setText)
    dialog.exec()


class SiteProfileDialog(QDialog):
    """Edit a Site Profile from Quick Setup or Profile Management."""

    binding_test_requested = pyqtSignal(str)
    profile_saved = pyqtSignal(str, object)

    def __init__(self, setup: SiteProfileSetup, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup = setup
        self._binding_edits: dict[str, QLineEdit] = {}
        self.setWindowTitle(f"Site Profile: {setup.domain}")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        target_label = QLabel(
            (
                f"Profile Setup Target: <b>{setup.target.title or setup.domain}</b><br>"
                f"Main domain: <b>{setup.domain}</b>"
            )
            if setup.target is not None
            else f"Saved Site Profile<br>Main domain: <b>{setup.domain}</b>"
        )
        target_label.setWordWrap(True)
        layout.addWidget(target_label)

        help_label = QLabel(
            "Capture one page-level key or a simultaneous shortcut for each gesture. "
            + (
                "Test sends the captured binding to this Profile Setup Target before saving."
                if setup.target is not None
                else "This saved profile can be maintained without opening its website."
            )
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        bindings_layout = QFormLayout()
        labels = {
            "short_press": "Short press:",
            "double_press": "Double press:",
            "long_hold": "Long hold:",
        }
        for binding_name in GESTURE_BINDING_NAMES:
            edit = QLineEdit(setup.bindings.get(binding_name) or "")
            edit.setReadOnly(True)
            capture_btn = QPushButton("Capture")
            capture_btn.clicked.connect(
                lambda _checked=False, name=binding_name, field=edit: self._capture_chord(name, field)
            )
            clear_btn = QPushButton("Clear")
            clear_btn.clicked.connect(edit.clear)
            row = QHBoxLayout()
            row.addWidget(edit)
            row.addWidget(capture_btn)
            row.addWidget(clear_btn)
            if setup.target is not None:
                test_btn = QPushButton("Test")
                test_btn.clicked.connect(
                    lambda _checked=False, field=edit: self.binding_test_requested.emit(field.text().strip())
                )
                row.addWidget(test_btn)
            bindings_layout.addRow(labels[binding_name], row)
            self._binding_edits[binding_name] = edit
        layout.addLayout(bindings_layout)

        actions = QHBoxLayout()
        save_btn = QPushButton("Save Site Profile")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        actions.addStretch()
        actions.addWidget(save_btn)
        actions.addWidget(cancel_btn)
        layout.addLayout(actions)

    def _capture_chord(self, binding_name: str, target: QLineEdit) -> None:
        capture_chord(binding_name.replace("_", " ").title(), target, self)

    def _save(self) -> None:
        self.profile_saved.emit(
            self._setup.domain,
            {name: edit.text().strip() or None for name, edit in self._binding_edits.items()},
        )
        self.accept()


class ProfileManagementDialog(QDialog):
    """List saved Site Profiles and expose their lifecycle actions."""

    profile_edit_requested = pyqtSignal(str)
    profile_reset_requested = pyqtSignal(str)
    profile_delete_requested = pyqtSignal(str)

    def __init__(
        self,
        profiles: dict[str, dict[str, str | None]],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Profile Management")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        help_label = QLabel(
            "Saved Site Profiles apply automatically by main domain. Select one to edit, "
            "reset it to Generic Profile bindings, or delete it."
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self._profiles = QListWidget()
        self._profiles.currentItemChanged.connect(self._update_actions)
        layout.addWidget(self._profiles)

        actions = QHBoxLayout()
        self._open_btn = QPushButton("Open")
        self._open_btn.clicked.connect(self._open_selected)
        self._reset_btn = QPushButton("Reset to Generic")
        self._reset_btn.clicked.connect(self._reset_selected)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._delete_selected)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        actions.addWidget(self._open_btn)
        actions.addWidget(self._reset_btn)
        actions.addWidget(self._delete_btn)
        actions.addStretch()
        actions.addWidget(close_btn)
        layout.addLayout(actions)
        self.set_profiles(profiles)

    def set_profiles(
        self,
        profiles: dict[str, dict[str, str | None]],
        selected_domain: str | None = None,
    ) -> None:
        """Refresh the visible saved domains after a lifecycle action."""
        self._profiles.clear()
        for domain in sorted(profiles):
            self._profiles.addItem(domain)
        if selected_domain:
            matches = self._profiles.findItems(selected_domain, Qt.MatchFlag.MatchExactly)
            if matches:
                self._profiles.setCurrentItem(matches[0])
        if self._profiles.currentItem() is None and self._profiles.count():
            self._profiles.setCurrentRow(0)
        self._update_actions()

    def _selected_domain(self) -> str | None:
        item = self._profiles.currentItem()
        return item.text() if item is not None else None

    def _update_actions(self) -> None:
        enabled = self._selected_domain() is not None
        self._open_btn.setEnabled(enabled)
        self._reset_btn.setEnabled(enabled)
        self._delete_btn.setEnabled(enabled)

    def _open_selected(self) -> None:
        domain = self._selected_domain()
        if domain is not None:
            self.profile_edit_requested.emit(domain)

    def _reset_selected(self) -> None:
        domain = self._selected_domain()
        if domain is not None:
            self.profile_reset_requested.emit(domain)

    def _delete_selected(self) -> None:
        domain = self._selected_domain()
        if domain is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Site Profile?",
            f"Delete the Site Profile for {domain}? Future controls for this domain will use Generic Profile.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.profile_delete_requested.emit(domain)


class SettingsWindow(QWidget):
    """Main settings window."""

    config_changed = pyqtSignal(Config)
    launch_browser_requested = pyqtSignal()
    generic_binding_test_requested = pyqtSignal(str)
    quick_profile_setup_requested = pyqtSignal()
    site_profile_binding_test_requested = pyqtSignal(str)
    site_profile_save_requested = pyqtSignal(str, object)
    site_profile_reset_requested = pyqtSignal(str)
    site_profile_delete_requested = pyqtSignal(str)
    pin_current_tab_requested = pyqtSignal()
    unpin_current_tab_requested = pyqtSignal()
    pin_status_changed = pyqtSignal(object)

    def __init__(self, config: Config, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("GamerScroll Settings")
        self.setMinimumWidth(500)
        self._config = config
        self._browsers: List[BrowserInfo] = []
        self._generic_binding_edits: dict[str, QLineEdit] = {}
        self.pin_status_changed.connect(self.set_pin_status)
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

        # Pinned tab group
        pinned_tab_group = QGroupBox("Pinned Tab")
        pinned_tab_layout = QFormLayout(pinned_tab_group)
        self._pin_status_label = QLabel("No tab pinned. Gestures control the active browser tab.")
        self._pin_status_label.setWordWrap(True)
        pinned_tab_layout.addRow("Status:", self._pin_status_label)

        pin_current_btn = QPushButton("Pin Current Tab")
        pin_current_btn.clicked.connect(self.pin_current_tab_requested.emit)
        pinned_tab_layout.addRow("", pin_current_btn)

        self._unpin_btn = QPushButton("Unpin")
        self._unpin_btn.setEnabled(False)
        self._unpin_btn.clicked.connect(self.unpin_current_tab_requested.emit)
        pinned_tab_layout.addRow("", self._unpin_btn)
        layout.addWidget(pinned_tab_group)

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

        # Generic Profile group
        generic_profile_group = QGroupBox("Generic Profile")
        generic_profile_layout = QFormLayout(generic_profile_group)
        generic_help = QLabel(
            "Used for every website without a Site Profile. Each gesture can use one key, "
            "a simultaneous shortcut, or be left unassigned."
        )
        generic_help.setWordWrap(True)
        generic_profile_layout.addRow(generic_help)
        labels = {
            "short_press": "Short press:",
            "double_press": "Double press:",
            "long_hold": "Long hold:",
        }
        for binding_name in GESTURE_BINDING_NAMES:
            edit = QLineEdit()
            edit.setReadOnly(True)
            capture_btn = QPushButton("Capture")
            capture_btn.clicked.connect(
                lambda _checked=False, name=binding_name, field=edit: self._capture_chord(name, field)
            )
            clear_btn = QPushButton("Clear")
            clear_btn.clicked.connect(edit.clear)
            test_btn = QPushButton("Test")
            test_btn.setToolTip("Sends the saved binding to the active setup tab")
            test_btn.clicked.connect(
                lambda _checked=False, name=binding_name: self.generic_binding_test_requested.emit(name)
            )
            row = QHBoxLayout()
            row.addWidget(edit)
            row.addWidget(capture_btn)
            row.addWidget(clear_btn)
            row.addWidget(test_btn)
            generic_profile_layout.addRow(labels[binding_name], row)
            self._generic_binding_edits[binding_name] = edit
        layout.addWidget(generic_profile_group)

        # Site Profile setup group
        site_profile_group = QGroupBox("Site Profiles")
        site_profile_layout = QFormLayout(site_profile_group)
        site_profile_help = QLabel(
            "Focus a browser tab, then open Quick Profile Setup to create or edit "
            "the profile shared by that site's subdomains."
        )
        site_profile_help.setWordWrap(True)
        site_profile_layout.addRow(site_profile_help)
        quick_setup_btn = QPushButton("Quick Profile Setup")
        quick_setup_btn.setToolTip("Configure the profile for the focused browser tab")
        quick_setup_btn.clicked.connect(self.quick_profile_setup_requested.emit)
        site_profile_layout.addRow("", quick_setup_btn)
        manage_profiles_btn = QPushButton("Manage Saved Profiles")
        manage_profiles_btn.setToolTip("Edit, reset, or delete saved Site Profiles")
        manage_profiles_btn.clicked.connect(self.show_profile_management)
        site_profile_layout.addRow("", manage_profiles_btn)
        layout.addWidget(site_profile_group)

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

    def _capture_chord(self, binding_name: str, target: QLineEdit) -> None:
        label = binding_name.replace("_", " ").title()
        capture_chord(label, target, self)

    def _load_config_into_ui(self) -> None:
        self._exe_edit.setText(self._config.browser_exe)
        self._port_spin.setValue(self._config.cdp_port)
        self._media_key_edit.setText(self._config.media_key)
        for binding_name, edit in self._generic_binding_edits.items():
            edit.setText(self._config.generic_bindings.get(binding_name) or "")
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

    def set_pin_status(self, pinned_tab: Optional[TabTarget]) -> None:
        """Display the current session-only pin state in Settings."""
        if pinned_tab is None:
            self._pin_status_label.setText(
                "No tab pinned. Gestures control the active browser tab."
            )
            self._unpin_btn.setEnabled(False)
            return
        self._pin_status_label.setText(
            f"Pinned: {pinned_tab.title}\nDomain: {pinned_tab.main_domain or 'unknown'}"
        )
        self._unpin_btn.setEnabled(True)

    def show_pin_error(self, message: str) -> None:
        """Explain why the focused browser tab could not be pinned."""
        QMessageBox.warning(self, "Could not pin current tab", message)

    def show_site_profile_error(self, title: str, message: str) -> None:
        """Explain why a Quick Profile Setup action could not complete."""
        QMessageBox.warning(self, title, message)

    def show_site_profile_setup(self, setup: SiteProfileSetup) -> None:
        """Open the editable Site Profile form selected by the focused tab."""
        dialog = SiteProfileDialog(setup, self)
        dialog.binding_test_requested.connect(self.site_profile_binding_test_requested.emit)
        dialog.profile_saved.connect(self.site_profile_save_requested.emit)
        dialog.exec()

    def show_profile_management(self) -> None:
        """Open the lifecycle controls for all saved Site Profiles."""
        dialog = ProfileManagementDialog(self._config.site_profiles, self)
        dialog.profile_edit_requested.connect(self._open_managed_site_profile)
        dialog.profile_reset_requested.connect(
            lambda domain: self._reset_managed_site_profile(domain, dialog)
        )
        dialog.profile_delete_requested.connect(
            lambda domain: self._delete_managed_site_profile(domain, dialog)
        )
        dialog.exec()

    def _open_managed_site_profile(self, domain: str) -> None:
        bindings = self._config.site_profiles.get(domain)
        if bindings is None:
            return
        self.show_site_profile_setup(SiteProfileSetup(None, domain, dict(bindings)))

    def _reset_managed_site_profile(self, domain: str, dialog: ProfileManagementDialog) -> None:
        self.site_profile_reset_requested.emit(domain)
        dialog.set_profiles(self._config.site_profiles, domain)

    def _delete_managed_site_profile(self, domain: str, dialog: ProfileManagementDialog) -> None:
        self.site_profile_delete_requested.emit(domain)
        dialog.set_profiles(self._config.site_profiles)

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
            generic_bindings={
                name: edit.text().strip() or None
                for name, edit in self._generic_binding_edits.items()
            },
            site_profiles={
                domain: dict(bindings)
                for domain, bindings in self._config.site_profiles.items()
            },
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
