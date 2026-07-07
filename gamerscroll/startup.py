"""Windows startup helpers (single-instance guard + Run registry)."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


_MUTEX_NAME = "Global\\GamerScrollSingleInstanceMutex"


class SingleInstanceGuard:
    """Ensure only one instance of the application runs at a time."""

    def __init__(self) -> None:
        self._handle: Optional[int] = None

    def acquire(self) -> bool:
        # CREATE_MUTEX_EX with initial ownership, fail on existing.
        self._handle = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        if not self._handle:
            logger.error("Failed to create single-instance mutex")
            return False
        err = ctypes.windll.kernel32.GetLastError()
        if err == 183:  # ERROR_ALREADY_EXISTS
            logger.info("Single-instance mutex already exists")
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
            return False
        logger.debug("Single-instance mutex acquired")
        return True

    def release(self) -> None:
        if self._handle:
            logger.debug("Releasing single-instance mutex")
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None


def _own_executable_path() -> str:
    """Return the path to use for the auto-start registry entry."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return str(Path(sys.argv[0]).resolve())


def set_auto_start(enabled: bool) -> None:
    """Add or remove the GamerScroll entry from the Windows Run registry."""
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            exe_path = _own_executable_path()
            winreg.SetValueEx(key, "GamerScroll", 0, winreg.REG_SZ, exe_path)
            logger.info("Added auto-start registry entry: {}", exe_path)
        else:
            try:
                winreg.DeleteValue(key, "GamerScroll")
                logger.info("Removed auto-start registry entry")
            except FileNotFoundError:
                logger.debug("Auto-start registry entry already absent")


def get_auto_start() -> bool:
    """Return whether the GamerScroll Run registry entry exists."""
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_QUERY_VALUE) as key:
            winreg.QueryValueEx(key, "GamerScroll")
            return True
    except FileNotFoundError:
        return False


def play_beep() -> None:
    """Play the Windows default beep sound for failure feedback."""
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception as exc:
        logger.debug("Could not play beep: {}", exc)
