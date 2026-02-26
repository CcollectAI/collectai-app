"""Tests for push notification service."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.lib.push_service import (
    send_push,
    send_push_batch,
    notify_chat_message,
    notify_price_alert,
    notify_connection_request,
    notify_event_announcement,
)


@pytest.mark.asyncio
async def test_send_push_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {"status": "ok"}}
    mock_resp.raise_for_status = MagicMock()

    with patch("app.lib.push_service.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.post.return_value = mock_resp
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await send_push("ExponentPushToken[xxx]", "Title", "Body", {"item_id": "123"})
        assert result is True
        client_instance.post.assert_called_once()


@pytest.mark.asyncio
async def test_send_push_error_response():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {"status": "error", "message": "Invalid token"}}
    mock_resp.raise_for_status = MagicMock()

    with patch("app.lib.push_service.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.post.return_value = mock_resp
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await send_push("ExponentPushToken[xxx]", "Title", "Body")
        assert result is False


@pytest.mark.asyncio
async def test_send_push_network_error():
    with patch("app.lib.push_service.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.post.side_effect = Exception("Network error")
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await send_push("ExponentPushToken[xxx]", "Title", "Body")
        assert result is False


@pytest.mark.asyncio
async def test_send_push_batch_empty():
    count = await send_push_batch([], "Title", "Body")
    assert count == 0


@pytest.mark.asyncio
async def test_send_push_batch_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"status": "ok"}, {"status": "ok"}, {"status": "error"}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("app.lib.push_service.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.post.return_value = mock_resp
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        count = await send_push_batch(
            ["token1", "token2", "token3"],
            "Title", "Body", {"key": "val"}
        )
        assert count == 2


@pytest.mark.asyncio
async def test_notify_chat_message():
    with patch("app.lib.push_service.send_push", new_callable=AsyncMock, return_value=True) as mock:
        result = await notify_chat_message("token", "Alice", "Hello!", "thread-1")
        assert result is True
        mock.assert_called_once()
        call_kwargs = mock.call_args
        assert call_kwargs[1]["data"]["thread_id"] == "thread-1"
        assert call_kwargs[1]["channel_id"] == "chat"


@pytest.mark.asyncio
async def test_notify_price_alert():
    with patch("app.lib.push_service.send_push", new_callable=AsyncMock, return_value=True) as mock:
        result = await notify_price_alert("token", "Charizard", "Price dropped 15%", "item-1")
        assert result is True
        mock.assert_called_once()
        assert mock.call_args[1]["channel_id"] == "alerts"


@pytest.mark.asyncio
async def test_notify_connection_request():
    with patch("app.lib.push_service.send_push", new_callable=AsyncMock, return_value=True) as mock:
        result = await notify_connection_request("token", "Bob", "req-1")
        assert result is True
        assert mock.call_args[1]["channel_id"] == "social"


@pytest.mark.asyncio
async def test_notify_event_announcement():
    with patch("app.lib.push_service.send_push", new_callable=AsyncMock, return_value=True) as mock:
        result = await notify_event_announcement("token", "Pokemon TCG Night", "New rules!", "evt-1", "ann-1")
        assert result is True
        assert mock.call_args[1]["channel_id"] == "events"
