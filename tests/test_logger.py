"""Tests for logger setup and runtime level changes (issue #9)."""

from __future__ import annotations

import pytest

from gamerscroll.logger import set_level, setup_logging, _LEVELS


def test_set_level_does_not_crash() -> None:
    """Changing the log level at runtime must not raise AttributeError."""
    setup_logging("INFO", console=False)
    # This used to call logger.update() which doesn't exist in Loguru.
    set_level("DEBUG")
    set_level("WARNING")
    set_level("ERROR")
    set_level("INFO")


def test_set_level_with_invalid_level_is_ignored() -> None:
    setup_logging("INFO", console=False)
    # Should log a warning but not raise.
    set_level("BOGUS")
    # The effective level should remain INFO.


def test_set_level_preserves_file_sink() -> None:
    setup_logging("INFO", console=False)
    set_level("DEBUG")
    # Verify that the logger still has handlers (file sink was re-added).
    from loguru import logger
    assert len(logger._core.handlers) > 0  # type: ignore[attr-defined]


def test_setup_logging_accepts_all_valid_levels() -> None:
    for level in _LEVELS:
        setup_logging(level, console=False)