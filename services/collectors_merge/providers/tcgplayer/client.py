from __future__ import annotations

import os
import time
from typing import Any

import httpx

TCG_AUTH = "https://api.tcgplayer.com/token"
TCG_BASE = "https://api.tcgplayer.com"


class TCGClient:
    def __init__(self):
        self.public = os.getenv("TCGPLAYER_PUBLIC_KEY")
        self.private = os.getenv("TCGPLAYER_PRIVATE_KEY")
        self._token = None
        self._exp = 0

    def token(self) -> str:
        now = time.time()
        if self._token and now < (self._exp - 30):
            return self._token
        with httpx.Client(timeout=15) as c:
            r = c.post(
                TCG_AUTH,
                data={"grant_type": "client_credentials"},
                auth=(self.public, self.private),
            )
            r.raise_for_status()
            js = r.json()
            self._token = js["access_token"]
            self._exp = now + js.get("expires_in", 3600)
            return self._token

    def get(self, path: str, params=None) -> dict[str, Any]:
        tok = self.token()
        with httpx.Client(timeout=20) as c:
            r = c.get(
                TCG_BASE + path,
                headers={"Authorization": f"Bearer {tok}"},
                params=params,
            )
            r.raise_for_status()
            return r.json()
