"""Persistent JSON configuration for GamerScroll."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List

from loguru import logger


DEFAULT_CONFIG: dict[str, Any] = {
    "browser_name": "Comet",
    "browser_exe": "",
    "user_data_dir": "",
    "profile": "Default",
    "cdp_port": 9222,
    "cdp_host": "127.0.0.1",
    "media_key": "f13",
    "hold_threshold_ms": 500,
    "double_click_window_ms": 300,
    "debounce_ms": 150,
    "auto_launch_browser": True,
    "auto_start_windows": False,
    "disabled": False,
    "log_level": "INFO",
}


@dataclass
class Config:
    browser_name: str = "Comet"
    browser_exe: str = ""
    user_data_dir: str = ""
    profile: str = "Default"
    cdp_port: int = 9222
    cdp_host: str = "127.0.0.1"
    media_key: str = "f13"
    hold_threshold_ms: int = 500
    double_click_window_ms: int = 300
    debounce_ms: int = 150
    auto_launch_browser: bool = True
    auto_start_windows: bool = False
    disabled: bool = False
    log_level: str = "INFO"

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        if path is None:
            path = cls.default_path()
        if not path.exists():
            logger.info("No config file found at {}, using defaults", path)
            return cls()
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            logger.warning("Config file at {} is invalid JSON: {}", path, exc)
            return cls()
        except OSError as exc:
            logger.warning("Cannot read config file at {}: {}", path, exc)
            return cls()
        merged = {**DEFAULT_CONFIG, **data}
        # Migrate legacy `paused` field to `disabled`.
        if "paused" in data and "disabled" not in data:
            merged["disabled"] = bool(data["paused"])

        fields = {k: merged[k] for k in DEFAULT_CONFIG if k in merged}
        # Drop legacy scroll fields so they don't break dataclass construction.
        fields = {k: v for k, v in fields.items() if k in cls.__dataclass_fields__}
        cfg = cls(**fields)
        cfg._sanitize_to_defaults()
        logger.info("Loaded config from {}", path)
        logger.debug(
            "Effective config: browser_name={}, cdp_port={}, profile={}, log_level={}",
            cfg.browser_name, cfg.cdp_port, cfg.profile, cfg.log_level,
        )
        return cfg

    def _sanitize_to_defaults(self) -> None:
        """Reset invalid numeric/boolean fields to their defaults on load."""
        if not isinstance(self.cdp_port, int) or not (1024 <= self.cdp_port <= 65535):
            self.cdp_port = DEFAULT_CONFIG["cdp_port"]
        if not isinstance(self.hold_threshold_ms, int) or self.hold_threshold_ms <= 0:
            self.hold_threshold_ms = DEFAULT_CONFIG["hold_threshold_ms"]
        if (
            not isinstance(self.double_click_window_ms, int)
            or self.double_click_window_ms <= 0
        ):
            self.double_click_window_ms = DEFAULT_CONFIG["double_click_window_ms"]
        if not isinstance(self.debounce_ms, int) or self.debounce_ms < 0:
            self.debounce_ms = DEFAULT_CONFIG["debounce_ms"]
        if not isinstance(self.log_level, str) or self.log_level not in {
            "DEBUG", "INFO", "WARNING", "ERROR"
        }:
            self.log_level = DEFAULT_CONFIG["log_level"]
        for field_name in ("auto_launch_browser", "auto_start_windows", "disabled"):
            current = getattr(self, field_name)
            if not isinstance(current, bool):
                setattr(self, field_name, bool(current))

    def save(self, path: Path | None = None) -> None:
        if path is None:
            path = self.default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
            logger.info("Saved config to {}", path)
        except OSError as exc:
            logger.error("Failed to save config to {}: {}", path, exc)
            raise

    @staticmethod
    def default_path() -> Path:
        app_data = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if app_data:
            return Path(app_data) / "GamerScroll" / "config.json"
        return Path.home() / ".gamerscroll" / "config.json"

    def validate(self) -> List[str]:
        """Return a list of human-readable validation errors."""
        errors: List[str] = []
        if not self.browser_exe or not Path(self.browser_exe).is_file():
            errors.append(f"Browser executable not found: {self.browser_exe or '(none)'}")
        if not self.user_data_dir or not Path(self.user_data_dir).is_dir():
            errors.append(f"User data directory not found: {self.user_data_dir or '(none)'}")
        if not (1024 <= self.cdp_port <= 65535):
            errors.append(f"CDP port must be between 1024 and 65535, got {self.cdp_port}")
        if not self.media_key:
            errors.append("Media key is not set.")
        if self.hold_threshold_ms <= 0:
            errors.append(f"Hold threshold must be positive, got {self.hold_threshold_ms}")
        if self.double_click_window_ms <= 0:
            errors.append(
                f"Double-click window must be positive, got {self.double_click_window_ms}"
            )
        if self.debounce_ms < 0:
            errors.append(f"Debounce must be non-negative, got {self.debounce_ms}")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            errors.append(f"Invalid log level: {self.log_level}")
        return errors
