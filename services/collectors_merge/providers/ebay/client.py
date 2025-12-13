from __future__ import annotations

import base64
import os
import time
from typing import Any

import httpx

EBAY_OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
# Example for production; use sandbox endpoints/creds for testing.


class EbayClient:
    def __init__(self):
        self._client_id = os.environ.get("EBAY_CLIENT_ID")
        self._client_secret = os.environ.get("EBAY_CLIENT_SECRET")
        self._scope = "https://api.ebay.com/oauth/api_scope"
        self._access_token: str | None = None
        self._token_expiry = 0

    def _basic_auth(self):
        raw = f"{self._client_id}:{self._client_secret}".encode()
        return base64.b64encode(raw).decode()

    def token(self) -> str:
        now = int(time.time())
        if self._access_token and now < (self._token_expiry - 60):
            return self._access_token
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {self._basic_auth()}",
        }
        data = {"grant_type": "client_credentials", "scope": self._scope}
        with httpx.Client(timeout=15) as c:
            r = c.post(EBAY_OAUTH_URL, headers=headers, data=data)
            r.raise_for_status()
            js = r.json()
            self._access_token = js["access_token"]
            self._token_expiry = int(time.time()) + int(js.get("expires_in", 7200))
            return self._access_token

    def get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self.token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        backoff = 1.0
        for attempt in range(6):
            with httpx.Client(timeout=20) as c:
                resp = c.get(url, headers=headers, params=params)
                if resp.status_code == 429:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                resp.raise_for_status()
                return resp.json()
        raise RuntimeError("eBay GET exhausted retries")
