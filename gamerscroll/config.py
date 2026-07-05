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
    "scroll_down_key": "f13",
    "scroll_up_key": "f14",
    "scroll_amount": 400,
    "scroll_x": 640,
    "scroll_y": 360,
    "auto_launch_browser": True,
    "auto_start_windows": False,
    "paused": False,
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
    scroll_down_key: str = "f13"
    scroll_up_key: str = "f14"
    scroll_amount: int = 400
    scroll_x: int = 640
    scroll_y: int = 360
    auto_launch_browser: bool = True
    auto_start_windows: bool = False
    paused: bool = False
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
        cfg = cls(**{k: merged[k] for k in DEFAULT_CONFIG if k in merged})
        logger.info("Loaded config from {}", path)
        logger.debug("Effective config: browser_name={}, cdp_port={}, profile={}, log_level={}",
                     cfg.browser_name, cfg.cdp_port, cfg.profile, cfg.log_level)
        return cfg

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
        if not self.scroll_down_key:
            errors.append("Scroll-down key is not set.")
        if not self.scroll_up_key:
            errors.append("Scroll-up key is not set.")
        if self.scroll_amount <= 0:
            errors.append(f"Scroll amount must be positive, got {self.scroll_amount}")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            errors.append(f"Invalid log level: {self.log_level}")
        return errors
