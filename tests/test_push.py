"""Tests for app.push — Expo push notification helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.push import send_push, send_push_to_user, EXPO_PUSH_URL


# ---------------------------------------------------------------------------
# send_push
# ---------------------------------------------------------------------------

class TestSendPush:
    @pytest.mark.asyncio
    async def test_success_returns_true(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"status": "ok", "id": "ticket-123"}}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.push.httpx.AsyncClient", return_value=mock_client):
            result = await send_push("ExponentPushToken[xxx]", "Title", "Body")

        assert result is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == EXPO_PUSH_URL
        payload = call_args[1]["json"]
        assert payload["to"] == "ExponentPushToken[xxx]"
        assert payload["title"] == "Title"
        assert payload["body"] == "Body"
        assert payload["sound"] == "default"

    @pytest.mark.asyncio
    async def test_with_data_and_badge(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"status": "ok"}}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.push.httpx.AsyncClient", return_value=mock_client):
            result = await send_push(
                "ExponentPushToken[abc]", "Alert", "New price!",
                data={"item_id": "123"}, badge=5,
            )

        assert result is True
        payload = mock_client.post.call_args[1]["json"]
        assert payload["data"] == {"item_id": "123"}
        assert payload["badge"] == 5

    @pytest.mark.asyncio
    async def test_non_200_returns_false(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.push.httpx.AsyncClient", return_value=mock_client):
            result = await send_push("ExponentPushToken[xxx]", "Title", "Body")

        assert result is False

    @pytest.mark.asyncio
    async def test_expo_error_status_returns_false(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "status": "error",
                "message": "Invalid token",
                "details": {"error": "InvalidCredentials"},
            }
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.push.httpx.AsyncClient", return_value=mock_client):
            result = await send_push("ExponentPushToken[bad]", "Title", "Body")

        assert result is False

    @pytest.mark.asyncio
    async def test_device_not_registered_returns_false(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "status": "error",
                "message": "Device not registered",
                "details": {"error": "DeviceNotRegistered"},
            }
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.push.httpx.AsyncClient", return_value=mock_client):
            result = await send_push("ExponentPushToken[old]", "Title", "Body")

        assert result is False

    @pytest.mark.asyncio
    async def test_http_error_returns_false(self):
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.push.httpx.AsyncClient", return_value=mock_client):
            result = await send_push("ExponentPushToken[xxx]", "Title", "Body")

        assert result is False

    @pytest.mark.asyncio
    async def test_os_error_returns_false(self):
        mock_client = AsyncMock()
        mock_client.post.side_effect = OSError("Network unreachable")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.push.httpx.AsyncClient", return_value=mock_client):
            result = await send_push("ExponentPushToken[xxx]", "Title", "Body")

        assert result is False

    @pytest.mark.asyncio
    async def test_no_data_or_badge_keys_omitted(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"status": "ok"}}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.push.httpx.AsyncClient", return_value=mock_client):
            await send_push("ExponentPushToken[xxx]", "T", "B")

        payload = mock_client.post.call_args[1]["json"]
        assert "data" not in payload
        assert "badge" not in payload


# ---------------------------------------------------------------------------
# send_push_to_user
# ---------------------------------------------------------------------------

class TestSendPushToUser:
    @pytest.mark.asyncio
    async def test_no_tokens_returns_zero(self):
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []

        result = await send_push_to_user(mock_conn, "user-1", "Title", "Body")
        assert result == 0

    @pytest.mark.asyncio
    async def test_one_token_success(self):
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [{"push_token": "ExponentPushToken[aaa]"}]

        with patch("app.push.send_push", new_callable=AsyncMock, return_value=True):
            result = await send_push_to_user(mock_conn, "user-1", "Title", "Body")

        assert result == 1

    @pytest.mark.asyncio
    async def test_multiple_tokens_mixed_results(self):
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {"push_token": "ExponentPushToken[aaa]"},
            {"push_token": "ExponentPushToken[bbb]"},
            {"push_token": "ExponentPushToken[ccc]"},
        ]

        call_count = 0

        async def mock_send(token, title, body, data=None):
            nonlocal call_count
            call_count += 1
            return call_count != 2  # second call fails

        with patch("app.push.send_push", side_effect=mock_send):
            result = await send_push_to_user(mock_conn, "user-1", "Title", "Body")

        assert result == 2  # 2 out of 3 succeeded

    @pytest.mark.asyncio
    async def test_passes_data_kwarg(self):
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [{"push_token": "ExponentPushToken[aaa]"}]

        with patch("app.push.send_push", new_callable=AsyncMock, return_value=True) as mock_send:
            await send_push_to_user(
                mock_conn, "user-1", "Title", "Body", data={"item_id": "42"}
            )
            mock_send.assert_called_once_with(
                "ExponentPushToken[aaa]", "Title", "Body", data={"item_id": "42"}
            )

    @pytest.mark.asyncio
    async def test_queries_correct_sql(self):
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []

        await send_push_to_user(mock_conn, "user-42", "T", "B")
        mock_conn.fetch.assert_called_once()
        sql = mock_conn.fetch.call_args[0][0]
        assert "user_push_tokens" in sql
        assert "active = true" in sql
        assert mock_conn.fetch.call_args[0][1] == "user-42"
