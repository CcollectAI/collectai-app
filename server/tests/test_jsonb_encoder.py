"""The jsonb encoder — the guard for a class that corrupted six tables.

WHY THIS FILE EXISTS

`app/db.py` registers a jsonb codec so rows decode to dicts instead of `str`.
Its `encoder` half then silently broke every caller that had ALREADY serialised
its payload, and roughly 25 of them had:

    await conn.execute("... SET attrs = attrs || $3::jsonb", ..., json.dumps(d))

asyncpg calls the encoder on that string, so the value lands as a JSON *string
scalar*. And jsonb `||` merges two OBJECTS but CONCATENATES otherwise, so the
first such write turns an object column into an ARRAY and every write after it
appends. `items.attrs` reached:

    [{"brand": "..."}, "{\\"set_code\\": \\"\\"}", "{\\"value_choice\\": \\"mine\\"}"]

which rendered as raw JSON on the item screen and stopped
`attrs->>'value_choice'` resolving — silently killing a member's saved "keep my
value" choice.

A sweep of every jsonb column in `public` found the class in six tables, all
still being written: mandate_deals.policy_reasons (526 rows),
supply_snapshots.metadata (248), market_hits.features_json (40),
alert_trigger_history.trigger_value, quick_predictions.raw, items.attrs.

Nothing in 3,829 tests could see it, because every one of them asserts the
PARAMETER passed to a mocked connection — never what the parameter becomes once
the codec has run. These tests target the codec itself.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import _jsonb_encoder  # noqa: E402


def _roundtrip(value):
    """What Postgres would parse for this bind."""
    return json.loads(_jsonb_encoder(value))


class TestNoDoubleEncoding:
    """The bug. A pre-serialised payload must not be encoded twice."""

    def test_a_serialised_dict_stays_an_object(self):
        assert _roundtrip(json.dumps({"a": 1})) == {"a": 1}

    def test_a_serialised_list_stays_an_array(self):
        assert _roundtrip(json.dumps([1, 2])) == [1, 2]

    def test_a_dict_is_still_encoded(self):
        assert _roundtrip({"a": 1}) == {"a": 1}

    def test_the_exact_payload_that_corrupted_items_attrs(self):
        """`{"set_code": ""}` is what the attribute editor sent. Encoded twice
        it became the string `'{"set_code": ""}'`, which `||` appended instead
        of merging."""
        out = _jsonb_encoder(json.dumps({"set_code": ""}))
        assert isinstance(json.loads(out), dict), "must stay an object, not become a string"


class TestScalarsAreNotReinterpreted:
    """Found by auditing the FIRST version of this encoder, which passed
    through anything that parsed. Python and Postgres disagree about these."""

    def test_nan_is_stored_as_a_string_not_rejected(self):
        """`json.loads('NaN')` succeeds in Python; `SELECT 'NaN'::jsonb` is a
        hard ERROR in Postgres. Passing it through would 500 on any member who
        typed "NaN" into a field that lands in a jsonb bag."""
        assert _roundtrip("NaN") == "NaN"

    def test_infinity_is_stored_as_a_string(self):
        assert _roundtrip("Infinity") == "Infinity"

    def test_a_numeric_string_stays_a_string(self):
        """A genuine "123" is not the number 123."""
        assert _roundtrip("123") == "123"

    def test_json_keywords_stay_strings(self):
        for kw in ("null", "true", "false"):
            assert _roundtrip(kw) == kw, kw

    def test_a_plain_string_is_encoded(self):
        assert _roundtrip("hello world") == "hello world"

    def test_empty_string(self):
        assert _roundtrip("") == ""


class TestOrdinaryValues:
    def test_none(self):
        assert _roundtrip(None) is None

    def test_number_and_bool(self):
        assert _roundtrip(7) == 7
        assert _roundtrip(True) is True

    def test_nested_structure_survives(self):
        payload = {"a": [1, {"b": None}], "c": "x"}
        assert _roundtrip(payload) == payload
        assert _roundtrip(json.dumps(payload)) == payload
