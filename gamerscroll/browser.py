"""Browser detection, profile enumeration, and Chromium launch helpers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import requests
from loguru import logger


KNOWN_BROWSERS = {
    "Google Chrome": {
        "exe_hints": [
            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
        ],
        "data_dir_hints": [r"%LOCALAPPDATA%\Google\Chrome\User Data"],
        "registry_path": r"SOFTWARE\Google\Chrome\BLBeacon",
    },
    "Microsoft Edge": {
        "exe_hints": [
            r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe",
            r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe",
            r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe",
        ],
        "data_dir_hints": [r"%LOCALAPPDATA%\Microsoft\Edge\User Data"],
        "registry_path": r"SOFTWARE\Microsoft\Edge\BLBeacon",
    },
    "Brave": {
        "exe_hints": [
            r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
        "data_dir_hints": [r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data"],
        "registry_path": r"SOFTWARE\BraveSoftware\Brave-Browser\BLBeacon",
    },
    "Comet": {
        "exe_hints": [
            r"%LOCALAPPDATA%\Perplexity\Comet\Application\comet.exe",
        ],
        "data_dir_hints": [r"%LOCALAPPDATA%\Perplexity\Comet\User Data"],
        "registry_path": None,
    },
}


@dataclass
class BrowserInfo:
    name: str
    exe: Path
    user_data_dir: Path


def _expand(path_template: str) -> Path:
    return Path(os.path.expandvars(path_template))


def _read_registry_str(key_path: str, value_name: str) -> Optional[str]:
    try:
        import winreg
    except ImportError:
        return None
    for hkey in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for sam in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY, 0):
            try:
                with winreg.OpenKey(hkey, key_path, 0, winreg.KEY_READ | sam) as key:
                    value, _ = winreg.QueryValueEx(key, value_name)
                    if value:
                        return str(value)
            except OSError:
                continue
    return None


def _find_first_existing(paths: List[str]) -> Optional[Path]:
    for p in paths:
        expanded = _expand(p)
        if expanded.is_file() or expanded.is_dir():
            return expanded
    return None


def detect_browsers() -> List[BrowserInfo]:
    """Return a list of Chromium-based browsers installed on this system."""
    found: List[BrowserInfo] = []
    seen: set[Path] = set()

    logger.info("Detecting installed Chromium-based browsers")
    for name, meta in KNOWN_BROWSERS.items():
        # Try registry to derive the install directory.
        exe = _find_first_existing(meta["exe_hints"])
        if not exe and meta.get("registry_path"):
            version = _read_registry_str(meta["registry_path"], "version")
            if version:
                logger.debug("{} registry version: {}", name, version)
                # Registry doesn't give the path directly; fall back to the standard paths.
                exe = _find_first_existing(meta["exe_hints"])
        if not exe:
            logger.debug("{} executable not found", name)
            continue

        data_dir = _find_first_existing(meta["data_dir_hints"])
        if not data_dir:
            # Derive from exe location as a fallback.
            candidate = exe.parent.parent / "User Data"
            if candidate.is_dir():
                data_dir = candidate
            else:
                logger.debug("{} user data dir not found", name)
                continue

        # Normalize to absolute resolved paths.
        exe = exe.resolve()
        data_dir = data_dir.resolve()
        if exe in seen:
            continue
        seen.add(exe)
        found.append(BrowserInfo(name=name, exe=exe, user_data_dir=data_dir))
        logger.info("Detected {} at {} (data: {})", name, exe, data_dir)

    logger.info("Browser detection complete: {} found", len(found))
    return found


def list_profiles(user_data_dir: Path) -> List[str]:
    """Return profile directory names (e.g. ['Default', 'Profile 1'])."""
    profiles: List[str] = []
    if not user_data_dir.is_dir():
        logger.debug("Cannot list profiles: {} is not a directory", user_data_dir)
        return profiles

    logger.debug("Listing profiles in {}", user_data_dir)
    local_state = user_data_dir / "Local State"
    if local_state.is_file():
        try:
            with local_state.open("r", encoding="utf-8") as f:
                data = json.load(f)
            info_cache = data.get("profile", {}).get("info_cache", {})
            for profile_dir in info_cache:
                full = user_data_dir / profile_dir
                if full.is_dir():
                    profiles.append(profile_dir)
            if profiles:
                logger.debug("Found {} profile(s) from Local State", len(profiles))
                return sorted(set(profiles), key=lambda p: (p != "Default", p.lower()))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read Local State for profiles: {}", exc)

    # Fallback: scan directory names.
    for entry in user_data_dir.iterdir():
        if entry.is_dir() and (entry / "Preferences").is_file():
            profiles.append(entry.name)
    logger.debug("Found {} profile(s) by directory scan", len(profiles))
    return sorted(set(profiles), key=lambda p: (p != "Default", p.lower()))


def is_browser_running(exe_name: str) -> bool:
    """Check whether any process matching the browser executable name is running."""
    try:
        import psutil
    except ImportError:
        # Fallback using tasklist.
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe_name}"],
                capture_output=True,
                text=True,
                check=False,
            )
            running = exe_name.lower() in result.stdout.lower()
            logger.debug("Browser running check (tasklist): {} -> {}", exe_name, running)
            return running
        except Exception as exc:
            logger.warning("psutil unavailable and tasklist failed: {}", exc)
            return False
    running = any(p.name().lower() == exe_name.lower() for p in psutil.process_iter(["name"]))
    logger.debug("Browser running check (psutil): {} -> {}", exe_name, running)
    return running


def terminate_browser(exe_name: str, timeout: int = 15) -> None:
    """Gracefully close then force-kill all matching processes."""
    logger.warning("Terminating browser processes: {}", exe_name)
    result = subprocess.run(
        ["taskkill", "/IM", exe_name, "/T"],
        capture_output=True,
        check=False,
    )
    logger.debug("taskkill graceful exit code: {}", result.returncode)
    deadline = time.time() + timeout
    while is_browser_running(exe_name) and time.time() < deadline:
        time.sleep(0.3)
    if is_browser_running(exe_name):
        logger.warning("Browser still running; forcing termination")
        result = subprocess.run(
            ["taskkill", "/F", "/IM", exe_name, "/T"],
            capture_output=True,
            check=False,
        )
        logger.debug("taskkill force exit code: {}", result.returncode)


def launch_browser(exe: Path, profile: str, port: int) -> subprocess.Popen:
    """Launch the browser with remote debugging enabled."""
    cmd = [
        str(exe),
        f"--remote-debugging-port={port}",
        f"--profile-directory={profile}",
    ]
    logger.info("Browser launch command: {}", " ".join(cmd))
    # Detach from the current console so closing the app doesn't kill the browser.
    proc = subprocess.Popen(
        cmd,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info("Browser launched with PID {}", proc.pid)
    return proc


def wait_for_cdp(host: str, port: int, timeout: float = 30.0) -> bool:
    """Poll the browser CDP endpoint until it responds or timeout."""
    url = f"http://{host}:{port}/json"
    deadline = time.time() + timeout
    attempts = 0
    while time.time() < deadline:
        attempts += 1
        try:
            resp = requests.get(url, timeout=1.5)
            if resp.status_code == 200:
                logger.info("CDP endpoint reachable after {} attempt(s)", attempts)
                return True
        except requests.RequestException:
            pass
        time.sleep(0.25)
    logger.error("CDP endpoint not reachable after {:.1f}s ({} attempts)", timeout, attempts)
    return False
