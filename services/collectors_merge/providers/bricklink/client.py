from __future__ import annotations

import os

import requests
from requests_oauthlib import OAuth1

BL_BASE = "https://api.bricklink.com/api/store/v1"


class BrickLinkClient:
    def __init__(self):
        self.key = os.getenv("BRICKLINK_CONSUMER_KEY")
        self.secret = os.getenv("BRICKLINK_CONSUMER_SECRET")
        self.token = os.getenv("BRICKLINK_TOKEN")
        self.token_secret = os.getenv("BRICKLINK_TOKEN_SECRET")
        self.auth = OAuth1(self.key, self.secret, self.token, self.token_secret)

    def get(self, path: str, params=None):
        url = f"{BL_BASE}{path}"
        r = requests.get(url, auth=self.auth, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
