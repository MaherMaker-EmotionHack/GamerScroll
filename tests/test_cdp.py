"""Tests for CDP transport helpers."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gamerscroll.cdp import CDPError, send_key_event


@pytest.mark.asyncio
async def test_send_key_event_dispatches_keydown_and_keyup() -> None:
    mock_ws = AsyncMock()

    with patch("gamerscroll.cdp.find_active_tab_ws", return_value="ws://tab"):
        with patch("websockets.connect", return_value=async_context_manager(mock_ws)):
            await send_key_event("127.0.0.1", 9222, "Space")

    assert mock_ws.send.call_count == 2
    sent = [json.loads(call.args[0]) for call in mock_ws.send.call_args_list]

    assert sent[0]["method"] == "Input.dispatchKeyEvent"
    assert sent[0]["params"]["type"] == "keyDown"
    assert sent[0]["params"]["key"] == "Space"
    assert sent[0]["params"]["text"] == " "

    assert sent[1]["method"] == "Input.dispatchKeyEvent"
    assert sent[1]["params"]["type"] == "keyUp"
    assert sent[1]["params"]["key"] == "Space"


@pytest.mark.asyncio
async def test_send_key_event_uses_arrow_down_for_next() -> None:
    mock_ws = AsyncMock()

    with patch("gamerscroll.cdp.find_active_tab_ws", return_value="ws://tab"):
        with patch("websockets.connect", return_value=async_context_manager(mock_ws)):
            await send_key_event("127.0.0.1", 9222, "ArrowDown")

    sent = [json.loads(call.args[0]) for call in mock_ws.send.call_args_list]
    assert sent[0]["params"]["windowsVirtualKeyCode"] == 40
    assert sent[0]["params"]["nativeVirtualKeyCode"] == 40


@pytest.mark.asyncio
async def test_send_key_event_uses_arrow_up_for_prev() -> None:
    mock_ws = AsyncMock()

    with patch("gamerscroll.cdp.find_active_tab_ws", return_value="ws://tab"):
        with patch("websockets.connect", return_value=async_context_manager(mock_ws)):
            await send_key_event("127.0.0.1", 9222, "ArrowUp")

    sent = [json.loads(call.args[0]) for call in mock_ws.send.call_args_list]
    assert sent[0]["params"]["windowsVirtualKeyCode"] == 38
    assert sent[0]["params"]["nativeVirtualKeyCode"] == 38


@pytest.mark.asyncio
async def test_send_key_event_raises_cdp_error_when_no_tab() -> None:
    with patch("gamerscroll.cdp.find_active_tab_ws", return_value=None):
        with pytest.raises(CDPError, match="No target tab available"):
            await send_key_event("127.0.0.1", 9222, "Space")


@pytest.mark.asyncio
async def test_send_key_event_wraps_websocket_errors() -> None:
    with patch("gamerscroll.cdp.find_active_tab_ws", return_value="ws://tab"):
        with patch("websockets.connect", side_effect=ConnectionRefusedError("nope")):
            with pytest.raises(CDPError, match="Connection error"):
                await send_key_event("127.0.0.1", 9222, "Space")


def async_context_manager(mock: AsyncMock) -> MagicMock:
    """Turn an AsyncMock into an async context manager."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx
