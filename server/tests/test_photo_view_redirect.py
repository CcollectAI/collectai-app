"""`/photos/view/{key}` — the redirect that makes private uploads visible.

Written 2026-07-27 after finding that every uploaded photo was invisible:
POST /photos/upload returned 200 and stored the object, but the `cdn_url` it
handed back was a direct S3 URL against a PRIVATE bucket, so fetching it
returned 403 AccessDenied. That is why the Add-Manually preview rendered
blank and why no item row has ever held a working S3 image_url.

The route is deliberately UNAUTHENTICATED (React Native's <Image> sends no
Authorization header), so `_PHOTO_KEY_RE` is the entire security boundary:
it is the only thing stopping a caller presigning an arbitrary object in the
bucket. These tests exist for that regex more than for the happy path.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_server_dir = str(Path(__file__).resolve().parent.parent)
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")

from app.features.photo_upload_router import _PHOTO_KEY_RE, _public_url  # noqa: E402

VALID = "user-uploads/b4271bd3-b872-435c-a5f4-44d598f8d479/00000000-0000-0000-0000-0000000000aa/4beb55051db94977b8d004422c4e645d.jpg"


class TestKeyValidation:
    def test_the_real_key_shape_from_production_is_accepted(self):
        """Verbatim key returned by a live POST /photos/upload."""
        assert _PHOTO_KEY_RE.match(VALID)

    @pytest.mark.parametrize("ext", ["jpg", "jpeg", "png", "webp"])
    def test_all_supported_extensions(self, ext):
        key = VALID.rsplit(".", 1)[0] + "." + ext
        assert _PHOTO_KEY_RE.match(key)

    @pytest.mark.parametrize("bad,why", [
        ("../../etc/passwd", "path traversal"),
        ("user-uploads/../../secret.jpg", "traversal inside the prefix"),
        ("artifacts/model.pkl", "different prefix entirely"),
        ("user-uploads/x/y/z.jpg", "filename is not 32 hex"),
        ("user-uploads/b4271bd3-b872-435c-a5f4-44d598f8d479/item/4beb55051db94977b8d004422c4e645d.exe", "extension not an image"),
        ("user-uploads/b4271bd3-b872-435c-a5f4-44d598f8d479/item/4beb55051db94977b8d004422c4e645d.jpg/../../x", "suffix after a valid key"),
        ("", "empty"),
        ("user-uploads/", "prefix only"),
    ])
    def test_rejects_anything_that_is_not_a_photo_key(self, bad, why):
        assert not _PHOTO_KEY_RE.match(bad), f"should reject ({why}): {bad!r}"

    def test_is_anchored_at_both_ends(self):
        """The END anchor is the load-bearing one.

        `re.match` already anchors at the start, so removing `^` changes
        nothing — verified by mutation: dropping it failed no test. Dropping
        `$` fails this and the traversal-suffix case above, because
        `<valid key>/../../x` then matches on its prefix and gets presigned.
        Keep `$`.
        """
        assert not _PHOTO_KEY_RE.match("junk/" + VALID)   # start (via re.match)
        assert not _PHOTO_KEY_RE.match(VALID + "/extra")  # end (via `$`)

    def test_uppercase_hex_filename_is_rejected(self):
        """uuid4().hex is lowercase; accepting uppercase widens the space
        for no reason."""
        head, tail = VALID.rsplit("/", 1)
        assert not _PHOTO_KEY_RE.match(f"{head}/{tail.upper()}")


class TestPublicUrl:
    def test_points_at_this_api_when_no_cdn_is_configured(self):
        url = _public_url(VALID)
        assert "/photos/view/" in url
        assert url.endswith(VALID)
        # The bug: a direct S3 URL against a private bucket -> 403.
        assert ".s3." not in url

    def test_cdn_wins_when_configured(self, monkeypatch):
        """Setting USER_UPLOADS_CDN_URL must override with no code change —
        that is the migration path to CloudFront + OAC."""
        import app.features.photo_upload_router as m

        monkeypatch.setattr(m, "CDN_URL", "https://cdn.example.com/")
        url = m._public_url(VALID)
        assert url == f"https://cdn.example.com/{VALID}"
        assert "/photos/view/" not in url
