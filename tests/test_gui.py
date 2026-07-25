"""Settings-window integration tests."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from gamerscroll.config import Config
from gamerscroll.gui import SettingsWindow


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
