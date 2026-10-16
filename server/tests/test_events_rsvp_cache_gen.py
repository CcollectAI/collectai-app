"""The cached event lists carry the caller's own RSVP status (2026-10-16).

They were cached 5 min per user with nothing invalidating them, so after
RSVP'ing the Events tab still said you were not going. An RSVP now bumps a
per-user generation that is part of the cache key.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.cache import reset_backend  # noqa: E402
from app.features.events import events_helpers as h  # noqa: E402


def test_rsvp_moves_the_generation_forward():
    reset_backend()
    before = h.user_events_gen("u1")
    h.bump_user_events_gen("u1")
    after = h.user_events_gen("u1")
    assert after > before
    assert h.user_events_gen("someone-else") == 0  # per member


def test_list_keys_carry_the_generation_and_every_rsvp_path_bumps_it():
    core = Path(h.__file__).with_name("events_core.py").read_text()
    assert 'events:list:{uid}:g{user_events_gen(uid)}' in core
    assert 'events:nearby:{uid}:g{user_events_gen(uid)}' in core
    rsvp = Path(h.__file__).with_name("events_rsvp.py").read_text()
    successes = rsvp.count('return {"success": True')
    assert successes >= 3
    assert rsvp.count("bump_user_events_gen(user_id)") == successes
