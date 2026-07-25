"""Persistent JSON configuration for GamerScroll."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List

from loguru import logger
import tldextract


GESTURE_BINDING_NAMES = ("short_press", "double_press", "long_hold")
_NAMED_KEYBOARD_KEYS = {
    "Space", "Enter", "Tab", "Escape", "Backspace", "Delete", "Insert",
    "Home", "End", "PageUp", "PageDown", "ArrowDown", "ArrowUp",
    "ArrowLeft", "ArrowRight",
}
DEFAULT_GENERIC_BINDINGS: dict[str, str | None] = {
    "short_press": "Space",
    "double_press": "ArrowDown",
    "long_hold": "ArrowUp",
}


_PUBLIC_SUFFIX_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())


def main_domain_from_url(url: str) -> str:
    """Return the registrable domain used to select a Site Profile.

    The browser targets local development pages as well as public sites, so
    localhost and IP addresses deliberately remain their own keys.  The
    bundled Public Suffix List is used offline, avoiding a network lookup while
    correctly grouping country-code domains and their subdomains.
    """
    from urllib.parse import urlparse

    hostname = (urlparse(url).hostname or "").lower().rstrip(".")
    if not hostname:
        return ""
    extracted = _PUBLIC_SUFFIX_EXTRACTOR(hostname)
    if not extracted.domain or not extracted.suffix:
        return hostname
    return f"{extracted.domain}.{extracted.suffix}"


def normalize_keyboard_chord(value: object) -> str | None:
    """Return a canonical simultaneous-key chord, or ``None`` if invalid.

    Bindings intentionally use a compact string representation (``Ctrl+L``),
    which is stable in JSON and accepted directly by the CDP transport.  A
    chord has exactly one non-modifier key; comma-separated or space-separated
    input would be an ordered sequence or text entry and is rejected.
    """
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or "," in value or ";" in value or " " in value:
        return None

    aliases = {
        "ctrl": "Ctrl",
        "control": "Ctrl",
        "alt": "Alt",
        "shift": "Shift",
        "meta": "Meta",
        "cmd": "Meta",
        "command": "Meta",
        "esc": "Escape",
        "return": "Enter",
        "up": "ArrowUp",
        "down": "ArrowDown",
        "left": "ArrowLeft",
        "right": "ArrowRight",
    }
    parts = value.split("+")
    if not parts or any(not part for part in parts):
        return None

    normalized = [aliases.get(part.lower(), part.upper() if len(part) == 1 else part) for part in parts]
    modifiers = {"Ctrl", "Alt", "Shift", "Meta"}
    keys = [part for part in normalized if part not in modifiers]
    if len(keys) != 1 or normalized[-1] in modifiers:
        return None
    modifier_parts = normalized[:-1]
    if any(part not in modifiers for part in modifier_parts) or len(set(modifier_parts)) != len(modifier_parts):
        return None
    key = keys[0]
    if not (
        key in _NAMED_KEYBOARD_KEYS
        or re.fullmatch(r"[A-Z0-9]|F(?:[1-9]|1[0-9]|2[0-4])", key)
    ):
        return None
    return "+".join([*modifier_parts, key])


def sanitize_generic_bindings(value: object) -> dict[str, str | None]:
    """Merge saved generic bindings with defaults without accepting sequences."""
    raw = value if isinstance(value, dict) else {}
    bindings: dict[str, str | None] = {}
    for name in GESTURE_BINDING_NAMES:
        if name not in raw:
            bindings[name] = DEFAULT_GENERIC_BINDINGS[name]
            continue
        saved = raw[name]
        bindings[name] = None if saved is None else normalize_keyboard_chord(saved)
    return bindings


def sanitize_site_profiles(value: object) -> dict[str, dict[str, str | None]]:
    """Accept only domain-keyed, complete Site Profile binding maps."""
    if not isinstance(value, dict):
        return {}
    profiles: dict[str, dict[str, str | None]] = {}
    for raw_domain, raw_bindings in value.items():
        if not isinstance(raw_domain, str):
            continue
        domain = raw_domain.lower().strip().rstrip(".")
        if not domain or any(char.isspace() for char in domain):
            continue
        raw = raw_bindings if isinstance(raw_bindings, dict) else {}
        profiles[domain] = {
            name: (
                None
                if raw.get(name) is None
                else normalize_keyboard_chord(raw.get(name))
            )
            for name in GESTURE_BINDING_NAMES
        }
    return profiles


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
    "generic_bindings": DEFAULT_GENERIC_BINDINGS,
    "site_profiles": {},
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
    generic_bindings: dict[str, str | None] = field(
        default_factory=lambda: dict(DEFAULT_GENERIC_BINDINGS)
    )
    site_profiles: dict[str, dict[str, str | None]] = field(default_factory=dict)

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
        self.generic_bindings = sanitize_generic_bindings(self.generic_bindings)
        self.site_profiles = sanitize_site_profiles(self.site_profiles)

    def set_site_profile(self, domain: str, bindings: object) -> None:
        """Store a validated Site Profile under its main-domain key."""
        profiles = sanitize_site_profiles({domain: bindings})
        if not profiles:
            raise ValueError("A Site Profile needs a valid main domain.")
        self.site_profiles[domain.lower().strip().rstrip(".")] = next(iter(profiles.values()))

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
        for name, binding in self.generic_bindings.items():
            if name not in GESTURE_BINDING_NAMES:
                errors.append(f"Unknown generic gesture binding: {name}")
            elif binding is not None and normalize_keyboard_chord(binding) is None:
                errors.append(f"Invalid keyboard chord for {name}: {binding}")
        for domain, bindings in self.site_profiles.items():
            if not domain:
                errors.append("Site Profile has an empty domain.")
            for name, binding in bindings.items():
                if binding is not None and normalize_keyboard_chord(binding) is None:
                    errors.append(f"Invalid Site Profile chord for {domain}/{name}: {binding}")
        return errors
