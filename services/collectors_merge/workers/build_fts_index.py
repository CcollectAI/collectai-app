from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv(".env")
except Exception:
    pass
import pathlib
import sqlite3
from typing import Any

import psycopg2
import psycopg2.extras

DBPATH = pathlib.Path("data/search.db")


def pg():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def ensure_schema(conn: sqlite3.Connection):
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute(
        """
      CREATE TABLE IF NOT EXISTS hits (
        provider TEXT, listing_id TEXT PRIMARY KEY, title TEXT, normalized_key TEXT, ended_at TEXT
      );
    """
    )
    c.execute(
        """
      CREATE VIRTUAL TABLE IF NOT EXISTS hits_fts USING fts5(
        title, listing_id UNINDEXED, content='hits', content_rowid='rowid'
      );
    """
    )
    conn.commit()


def load_recent_hits(days=365, limit=200000) -> list[dict[str, Any]]:
    q = """
      SELECT provider, listing_id, title, normalized_key, ended_at
      FROM public.market_hits
      WHERE ended_at >= now() - (%s || ' days')::interval
      ORDER BY ended_at DESC
      LIMIT %s
    """
    conn = pg()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(q, (days, limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def rebuild(days=365):
    DBPATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DBPATH)
    ensure_schema(conn)
    c = conn.cursor()
    c.execute("DELETE FROM hits;")
    c.execute("DELETE FROM hits_fts;")
    rows = load_recent_hits(days=days)
    for r in rows:
        c.execute(
            "INSERT OR REPLACE INTO hits(provider,listing_id,title,normalized_key,ended_at) VALUES(?,?,?,?,?)",
            (
                r["provider"],
                r["listing_id"],
                r["title"],
                r["normalized_key"],
                r["ended_at"].isoformat() if r["ended_at"] else None,
            ),
        )
    # rebuild FTS from content table
    c.execute("INSERT INTO hits_fts(rowid, title) SELECT rowid, title FROM hits;")
    conn.commit()
    conn.close()
    print(f"fts indexed {len(rows)} rows")


if __name__ == "__main__":
    rebuild()
