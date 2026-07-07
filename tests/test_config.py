"""Tests for configuration loading and schema migration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gamerscroll.config import Config


def test_default_config_has_media_control_values() -> None:
    cfg = Config()

    assert cfg.media_key == "f13"
    assert cfg.hold_threshold_ms == 500
    assert cfg.double_click_window_ms == 300
    assert cfg.debounce_ms == 150
    assert cfg.disabled is False


def test_load_merges_missing_defaults_for_new_fields(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    legacy = {
        "browser_name": "Chrome",
        "paused": True,
        "scroll_amount": 400,
    }
    path.write_text(json.dumps(legacy))

    cfg = Config.load(path)

    assert cfg.browser_name == "Chrome"
    assert cfg.disabled is True  # migrated from paused
    assert cfg.media_key == "f13"
    assert cfg.hold_threshold_ms == 500
    # legacy scroll fields are ignored
    assert not hasattr(cfg, "scroll_amount")


def test_load_rejects_invalid_hold_threshold(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"hold_threshold_ms": 0}))

    cfg = Config.load(path)
    assert cfg.hold_threshold_ms == 500  # falls back to default


def test_validate_requires_media_key() -> None:
    cfg = Config(media_key="")
    errors = cfg.validate()

    assert any("media key" in e.lower() for e in errors)


def test_validate_rejects_negative_thresholds() -> None:
    cfg = Config(hold_threshold_ms=-1, double_click_window_ms=-1, debounce_ms=-1)
    errors = cfg.validate()

    assert any("hold threshold" in e.lower() for e in errors)
    assert any("double-click" in e.lower() for e in errors)
    assert any("debounce" in e.lower() for e in errors)


def test_save_and_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    cfg = Config(media_key="f14", hold_threshold_ms=700, disabled=True)
    cfg.save(path)

    loaded = Config.load(path)
    assert loaded.media_key == "f14"
    assert loaded.hold_threshold_ms == 700
    assert loaded.disabled is True
