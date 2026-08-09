"""Tests for app.lib.json_safe.

The point of these is the JSON *type* on the wire, not merely that a value is
present. The bug this module exists to prevent (commit fe3b143) shipped a price
of `"642.64"` — present, readable, correct to the eye, and wrong, because the
client tests `typeof priceEur === 'number'`. An assertion of `== 642.64` would
have passed against the broken code in Python, since `"642.64" != 642.64` only
matters once it crosses into JSON. So these assert on `type(...)` and on the
serialised output.
"""

import json
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from app.lib.json_safe import json_safe_row, json_safe_rows, json_safe_value


class TestTheRegression:
    """The exact shape that shipped every search price as a string."""

    def test_float_stays_a_float(self):
        out = json_safe_value(642.64)
        assert out == 642.64
        assert type(out) is float

    def test_float_survives_json_as_a_number(self):
        # The assertion that would have caught the original bug.
        assert json.dumps(json_safe_row({"price_eur": 642.64})) == '{"price_eur": 642.64}'

    def test_float_is_not_hex_stringified(self):
        # (642.64).hex() == '0x1.4147ae147ae14p+9' — the old branch produced this.
        out = json_safe_value(642.64)
        assert not isinstance(out, str)
        assert "0x1." not in repr(out)

    def test_a_whole_row_of_mixed_types(self):
        row = {
            "id": uuid.UUID("20503ad2-c62d-4700-810b-36da247bbf28"),
            "price": 15.0,
            "qty": 3,
            "title": "E2E Upload Test",
            "created_at": datetime(2026, 8, 9, 23, 13, tzinfo=timezone.utc),
            "is_public": True,
            "missing": None,
        }
        out = json_safe_row(row)
        assert out["id"] == "20503ad2-c62d-4700-810b-36da247bbf28"
        assert type(out["price"]) is float
        assert type(out["qty"]) is int
        assert out["created_at"] == "2026-08-09T23:13:00+00:00"
        assert out["is_public"] is True
        assert out["missing"] is None
        json.dumps(out)  # must not raise


class TestConversions:
    def test_uuid_becomes_str(self):
        u = uuid.uuid4()
        assert json_safe_value(u) == str(u)

    def test_decimal_becomes_float_not_str(self):
        out = json_safe_value(Decimal("19.99"))
        assert type(out) is float
        assert out == 19.99

    def test_datetime_date_and_time_all_isoformat(self):
        assert json_safe_value(datetime(2026, 8, 10, 1, 2, 3)) == "2026-08-10T01:02:03"
        assert json_safe_value(date(2026, 8, 10)) == "2026-08-10"
        assert json_safe_value(time(1, 2, 3)) == "01:02:03"

    def test_bool_is_left_alone(self):
        # bool is a subclass of int; a stray numeric branch would corrupt it.
        assert json_safe_value(True) is True
        assert json_safe_value(False) is False

    def test_int_is_left_alone(self):
        out = json_safe_value(7)
        assert out == 7
        assert type(out) is int

    def test_str_is_left_alone(self):
        assert json_safe_value("already fine") == "already fine"


class TestContainers:
    def test_decimal_nested_in_jsonb_dict(self):
        # Previously fell through and 500'd at the response encoder.
        out = json_safe_value({"meta": {"paid": Decimal("5.50")}})
        assert type(out["meta"]["paid"]) is float
        json.dumps(out)

    def test_list_of_values(self):
        out = json_safe_value([Decimal("1.5"), datetime(2026, 1, 1), 2.5])
        assert out[0] == 1.5 and type(out[0]) is float
        assert out[1] == "2026-01-01T00:00:00"
        assert type(out[2]) is float

    def test_floats_inside_containers_stay_floats(self):
        out = json_safe_value({"prices": [1.5, 2.5]})
        assert all(type(p) is float for p in out["prices"])


class TestRows:
    def test_json_safe_rows_accepts_dicts(self):
        out = json_safe_rows([{"a": Decimal("1")}, {"a": 2.0}])
        assert [type(r["a"]) for r in out] == [float, float]

    def test_json_safe_rows_handles_empty(self):
        assert json_safe_rows([]) == []

    def test_json_safe_row_does_not_mutate_input(self):
        row = {"d": Decimal("1.25")}
        json_safe_row(row)
        assert isinstance(row["d"], Decimal)
