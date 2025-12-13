import os
import time
import httpx
from typing import Optional, List, Dict, Any


class TwitchClient:
    """
    Lightweight Twitch API client for Helix + OAuth.
    """

    def __init__(self):
        self.client_id = os.getenv("TWITCH_CLIENT_ID")
        self.client_secret = os.getenv("TWITCH_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise RuntimeError("Missing TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET env variables")

        self._token: Optional[str] = None
        self._token_expiry: float = 0  # epoch seconds

    # ============================================================
    # OAuth Token Handling
    # ============================================================

    async def _ensure_token(self):
        now = time.time()

        if self._token and now < self._token_expiry - 60:
            return self._token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://id.twitch.tv/oauth2/token",
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=15,
            )
            data = resp.json()
            self._token = data["access_token"]
            self._token_expiry = now + data.get("expires_in", 3600)

        return self._token

    # ============================================================
    # Internal Helix request helper
    # ============================================================

    async def _helix_get(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        token = await self._ensure_token()

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {token}",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()

    # ============================================================
    # Public API: Get creator(s)
    # ============================================================

    async def get_users(self, logins: List[str] = None, ids: List[str] = None) -> List[Dict[str, Any]]:
        url = "https://api.twitch.tv/helix/users"
        params = {}
        if logins:
            params.update({ "login": logins })
        if ids:
            params.update({ "id": ids })

        data = await self._helix_get(url, params)
        return data.get("data", [])

    # ============================================================
    # Public API: Get live streams (Helix /streams)
    # ============================================================

    async def get_live_streams(self, user_ids: List[str]) -> List[Dict[str, Any]]:
        url = "https://api.twitch.tv/helix/streams"
        params = { "user_id": user_ids }

        data = await self._helix_get(url, params)
        return data.get("data", [])


# Singleton pattern (import anywhere)
twitch_client = TwitchClient()

