"""Tests for SQL injection guards in pipelines.taxonomy_version_upgrade."""

from __future__ import annotations

import pytest

from pipelines.taxonomy_version_upgrade import (
    _validate_identifier,
    ALLOWED_TABLES,
    ALLOWED_COLUMNS,
    MigrationRule,
    count_affected_rows,
    apply_rule_to_table,
    update_remaining_version,
)


# ---------------------------------------------------------------------------
# _validate_identifier
# ---------------------------------------------------------------------------

class TestValidateIdentifier:
    def test_valid_table(self):
        assert _validate_identifier("items", "table", ALLOWED_TABLES) == "items"

    def test_valid_column(self):
        assert _validate_identifier("category", "column", ALLOWED_COLUMNS) == "category"

    def test_rejects_unknown_table(self):
        with pytest.raises(ValueError, match="Invalid table"):
            _validate_identifier("users; DROP TABLE items;--", "table", ALLOWED_TABLES)

    def test_rejects_unknown_column(self):
        with pytest.raises(ValueError, match="Invalid column"):
            _validate_identifier("1; DELETE FROM items;--", "column", ALLOWED_COLUMNS)

    def test_rejects_sql_injection_in_table(self):
        with pytest.raises(ValueError):
            _validate_identifier("items; DROP TABLE items", "table", ALLOWED_TABLES)

    def test_rejects_sql_injection_in_column(self):
        with pytest.raises(ValueError):
            _validate_identifier("category) = $1; DELETE FROM items; --", "column", ALLOWED_COLUMNS)

    def test_all_migration_targets_are_allowed(self):
        """All tables in MIGRATION_TARGETS should pass validation."""
        for table in ALLOWED_TABLES:
            assert _validate_identifier(table, "table", ALLOWED_TABLES) == table
        for col in ALLOWED_COLUMNS:
            assert _validate_identifier(col, "column", ALLOWED_COLUMNS) == col

    def test_rejects_uppercase_bypass(self):
        with pytest.raises(ValueError):
            _validate_identifier("ITEMS", "table", ALLOWED_TABLES)

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError):
            _validate_identifier("", "table", ALLOWED_TABLES)


# ---------------------------------------------------------------------------
# Async functions with injection attempts
# ---------------------------------------------------------------------------

class TestCountAffectedRowsValidation:
    @pytest.mark.asyncio
    async def test_rejects_injected_table(self):
        from unittest.mock import AsyncMock
        conn = AsyncMock()
        rule = MigrationRule("old_cat", "new_cat")
        with pytest.raises(ValueError, match="Invalid table"):
            await count_affected_rows(conn, "items; DROP TABLE items", "category", "taxonomy_version", "v1.0", rule)

    @pytest.mark.asyncio
    async def test_rejects_injected_column(self):
        from unittest.mock import AsyncMock
        conn = AsyncMock()
        rule = MigrationRule("old_cat", "new_cat")
        with pytest.raises(ValueError, match="Invalid column"):
            await count_affected_rows(conn, "items", "category); --", "taxonomy_version", "v1.0", rule)


class TestApplyRuleValidation:
    @pytest.mark.asyncio
    async def test_rejects_injected_table(self):
        from unittest.mock import AsyncMock
        conn = AsyncMock()
        rule = MigrationRule("old_cat", "new_cat")
        with pytest.raises(ValueError, match="Invalid table"):
            await apply_rule_to_table(conn, "bad_table", "category", "taxonomy_version", "v1.0", "v1.1", rule)


class TestUpdateRemainingVersionValidation:
    @pytest.mark.asyncio
    async def test_rejects_injected_table(self):
        from unittest.mock import AsyncMock
        conn = AsyncMock()
        with pytest.raises(ValueError, match="Invalid table"):
            await update_remaining_version(conn, "evil; DROP TABLE items", "taxonomy_version", "v1.0", "v1.1")

    @pytest.mark.asyncio
    async def test_rejects_injected_column(self):
        from unittest.mock import AsyncMock
        conn = AsyncMock()
        with pytest.raises(ValueError, match="Invalid column"):
            await update_remaining_version(conn, "items", "evil_col", "v1.0", "v1.1")
