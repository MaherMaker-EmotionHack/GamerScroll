"""Settings-window integration tests."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox

from gamerscroll.config import Config
from gamerscroll.gui import ProfileManagementDialog, SettingsWindow


def test_settings_save_preserves_site_profiles(tmp_path: Path, monkeypatch: object) -> None:
    app = QApplication.instance() or QApplication([])
    browser_exe = tmp_path / "browser.exe"
    browser_exe.touch()
    config = Config(
        browser_exe=str(browser_exe),
        user_data_dir=str(tmp_path),
        site_profiles={
            "youtube.com": {
                "short_press": "K",
                "double_press": None,
                "long_hold": "Shift+P",
            }
        },
    )
    saved_configs: list[Config] = []
    monkeypatch.setattr(Config, "save", lambda self: None)  # type: ignore[attr-defined]
    window = SettingsWindow(config)
    window.config_changed.connect(saved_configs.append)

    window._save()

    assert app is not None
    assert saved_configs[0].site_profiles == config.site_profiles
    window.close()


def test_profile_management_lists_saved_domains_and_opens_the_selected_profile() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = ProfileManagementDialog({
        "youtube.com": {
            "short_press": "K",
            "double_press": None,
            "long_hold": "Shift+P",
        },
        "vimeo.com": {
            "short_press": "Space",
            "double_press": "ArrowDown",
            "long_hold": "ArrowUp",
        },
    })

    assert app is not None
    domains = []
    for index in range(dialog._profiles.count()):
        item = dialog._profiles.item(index)
        assert item is not None
        domains.append(item.text())
    assert domains == [
        "vimeo.com",
        "youtube.com",
    ]
    opened_domains: list[str] = []
    dialog.profile_edit_requested.connect(opened_domains.append)
    dialog._open_btn.click()

    assert opened_domains == ["vimeo.com"]
    dialog.close()


def test_profile_management_requires_delete_confirmation(monkeypatch: object) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = ProfileManagementDialog({
        "youtube.com": {
            "short_press": "K",
            "double_press": None,
            "long_hold": "Shift+P",
        }
    })
    deleted_domains: list[str] = []
    dialog.profile_delete_requested.connect(deleted_domains.append)
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Cancel,
    )

    dialog._delete_btn.click()

    assert app is not None
    assert deleted_domains == []

    monkeypatch.setattr(  # type: ignore[attr-defined]
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )
    dialog._delete_btn.click()

    assert deleted_domains == ["youtube.com"]
    dialog.close()
