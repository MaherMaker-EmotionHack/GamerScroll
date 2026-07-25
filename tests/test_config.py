"""Tests for configuration loading and schema migration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gamerscroll.config import Config, main_domain_from_url


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


def test_generic_bindings_round_trip_as_optional_chords(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    cfg = Config(
        generic_bindings={
            "short_press": "Ctrl+L",
            "double_press": None,
            "long_hold": "Shift+N",
        }
    )

    cfg.save(path)

    assert json.loads(path.read_text())["generic_bindings"] == {
        "short_press": "Ctrl+L",
        "double_press": None,
        "long_hold": "Shift+N",
    }
    assert Config.load(path).generic_bindings == cfg.generic_bindings


def test_invalid_or_ordered_generic_bindings_are_unassigned(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"generic_bindings": {"short_press": "Ctrl+L, N"}}))

    cfg = Config.load(path)

    assert cfg.generic_bindings["short_press"] is None


def test_main_domain_groups_subdomains_and_keeps_local_hosts_distinct() -> None:
    assert main_domain_from_url("https://music.youtube.com/watch?v=1") == "youtube.com"
    assert main_domain_from_url("https://www.youtube.co.uk/shorts/1") == "youtube.co.uk"
    assert main_domain_from_url("https://a.example.co.za/page") == "example.co.za"
    assert main_domain_from_url("http://localhost:3000") == "localhost"


def test_site_profiles_round_trip_as_optional_chords(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    cfg = Config(site_profiles={
        "youtube.com": {
            "short_press": "K",
            "double_press": None,
            "long_hold": "Shift+P",
        }
    })

    cfg.save(path)

    loaded = Config.load(path)
    assert loaded.site_profiles == cfg.site_profiles
