"""High-level scroller that maps hotkey events to CDP scroll actions."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

from gamerscroll.cdp import CDPError, send_scroll_sync
from gamerscroll.config import Config


@dataclass
class ScrollerStatus:
    ok: bool
    message: str


class Scroller:
    """Connects configuration with CDP scroll actions."""

    def __init__(self, config: Config, on_status: Optional[Callable[[ScrollerStatus], None]] = None):
        self._config = config
        self._on_status = on_status
        self._lock = threading.Lock()

    def update_config(self, config: Config) -> None:
        with self._lock:
            old = self._config
            self._config = config
        logger.debug(
            "Scroller config updated: port={}, amount=({},{}), paused={}",
            config.cdp_port, config.scroll_amount, (config.scroll_x, config.scroll_y),
            config.paused,
        )

    def scroll_down(self) -> None:
        self._scroll(+1)

    def scroll_up(self) -> None:
        self._scroll(-1)

    def _scroll(self, direction: int) -> None:
        with self._lock:
            cfg = self._config
            if cfg.paused:
                logger.info("Scroll {} ignored (paused)", "down" if direction > 0 else "up")
                self._emit(False, "Scrolling is paused.")
                return

        logger.debug("Scroller executing scroll {}", "down" if direction > 0 else "up")
        try:
            exe_name = Path(cfg.browser_exe).name if cfg.browser_exe else None
            send_scroll_sync(
                host=cfg.cdp_host,
                port=cfg.cdp_port,
                direction=direction,
                amount=cfg.scroll_amount,
                x=cfg.scroll_x,
                y=cfg.scroll_y,
                browser_exe_name=exe_name,
            )
            self._emit(True, "Scrolled " + ("down" if direction > 0 else "up"))
        except CDPError as exc:
            logger.error("Scroll failed: {}", exc)
            self._emit(False, str(exc))

    def _emit(self, ok: bool, message: str) -> None:
        if self._on_status:
            self._on_status(ScrollerStatus(ok=ok, message=message))
