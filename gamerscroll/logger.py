"""Centralized logging setup for GamerScroll."""

from __future__ import annotations

import os
import re
import sys
import threading
from pathlib import Path
from typing import Optional

from loguru import logger

from gamerscroll.config import Config


_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
_DEFAULT_LEVEL = "INFO"
_LOG_FILE_NAME = "gamerscroll.log"
_MAX_BYTES = 1_000_000  # 1 MB
_BACKUP_COUNT = 3


def _user_profile_pattern() -> Optional[re.Pattern[str]]:
    """Build a regex that matches the user's profile directory prefix."""
    # Common root paths that may contain the Windows username.
    candidates = [
        os.environ.get("USERPROFILE"),
        os.environ.get("HOME"),
    ]
    patterns: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        # Normalize backslashes and escape for regex.
        normalized = os.path.normpath(candidate).replace("\\", "/")
        escaped = re.escape(normalized)
        # Match the prefix with either forward or backward slashes.
        patterns.append(escaped)

    if not patterns:
        return None
    return re.compile(
        "(?:" + "|".join(patterns) + r")([/\\].*)?",
        re.IGNORECASE,
    )


_PROFILE_RE = _user_profile_pattern()


def _redact(message: str) -> str:
    """Redact Windows user-profile paths from log messages."""
    if _PROFILE_RE is None:
        return message
    return _PROFILE_RE.sub(r"<USERPROFILE>\1", message)


def _patcher(record: dict) -> None:
    """Loguru record patcher that redacts user paths from the message."""
    record["message"] = _redact(record["message"])


def _log_dir() -> Path:
    """Return the directory used for log files."""
    return Config.default_path().parent / "logs"


def _console_enabled() -> bool:
    """Return True when running from source with a real console."""
    if getattr(sys, "frozen", False):
        return False
    return sys.stdout is not None and sys.stderr is not None


def _global_exception_hook(exc_type, exc_value, exc_traceback) -> None:  # type: ignore[no-untyped-def]
    """Log uncaught exceptions from the main thread."""
    if issubclass(exc_type, KeyboardInterrupt):
        # Respect Ctrl+C.
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.opt(exception=(exc_type, exc_value, exc_traceback)).error(
        "Uncaught exception in main thread"
    )


def _thread_exception_hook(args: threading.ExceptHookArgs) -> None:
    """Log uncaught exceptions from daemon threads."""
    if args.exc_type is None:
        return
    if issubclass(args.exc_type, SystemExit):
        return
    logger.opt(exception=(args.exc_type, args.exc_value, args.exc_traceback)).error(
        "Uncaught exception in thread '{}'", args.thread.name if args.thread else "?"
    )


def setup_logging(
    level: Optional[str] = None,
    *,
    console: Optional[bool] = None,
    file: bool = True,
) -> Path:
    """Configure Loguru sinks for GamerScroll."""
    effective_level = (level or _DEFAULT_LEVEL).upper()
    if effective_level not in _LEVELS:
        effective_level = _DEFAULT_LEVEL

    logger.remove()
    logger.configure(patcher=_patcher)

    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / _LOG_FILE_NAME

    common_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    if file:
        logger.add(
            str(log_path),
            level=effective_level,
            format=common_format,
            rotation=_MAX_BYTES,
            retention=_BACKUP_COUNT,
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=True,
        )

    if console if console is not None else _console_enabled():
        logger.add(
            sys.stderr,
            level=effective_level,
            format=common_format,
            colorize=True,
            enqueue=True,
            backtrace=True,
            diagnose=True,
        )

    sys.excepthook = _global_exception_hook
    threading.excepthook = _thread_exception_hook

    logger.info("Logging initialized at {} level", effective_level)
    logger.debug("Log file: {}", log_path)
    return log_path


def set_level(level: str) -> None:
    """Dynamically change the log level of all registered handlers.

    Loguru does not support updating an existing handler in place, so we
    remove every handler and re-run :func:`setup_logging` with the new level.
    This preserves the file/console sink configuration while changing the
    severity threshold.
    """
    effective = level.upper()
    if effective not in _LEVELS:
        logger.warning("Ignoring invalid log level: {}", level)
        return
    # Determine whether console output was enabled before reconfiguring.
    had_console = any(
        getattr(h, "_sink", None) and hasattr(h._sink, "_stream") and h._sink._stream is sys.stderr  # type: ignore[attr-defined]
        for h in logger._core.handlers.values()  # type: ignore[attr-defined]
    )
    setup_logging(effective, console=had_console if had_console else None)
    logger.info("Log level changed to {}", effective)
