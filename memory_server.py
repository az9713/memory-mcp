#!/usr/bin/env python3
"""
Lightweight semantic memory MCP server.

Three tiers:
  core      — permanent, never fades
  warm      — 30-day half-life (active projects, recent learnings)
  ephemeral — 2-day half-life  (session facts, transient notes)

Tools: remember · recall · forget · memories
DB:    ~/.claude/memory.db  (auto-created)
"""

import math
import os
import sqlite3
import struct
import time
import uuid
from typing import Callable, Optional

import sqlite_vec
from mcp.server.fastmcp import FastMCP
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_PATH = os.path.expanduser("~/.claude/memory.db")
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
HALF_LIFE = {"core": float("inf"), "warm": 30.0, "ephemeral": 2.0}
VALID_TIERS = {"core", "warm", "ephemeral"}
PRUNE_AFTER_DAYS = 7  # delete ephemeral not accessed in this many days
CURRENT_SCHEMA_VERSION = 2

# ---------------------------------------------------------------------------
# Embedding model (lazy — first call downloads ~80 MB to ~/.cache/)
# ---------------------------------------------------------------------------

_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed(text: str) -> list[float]:
    # normalize_embeddings=True gives unit vectors → L2 distance maps to cosine
    return get_model().encode(text, normalize_embeddings=True).tolist()


def serialize(v: list[float]) -> bytes:
    return struct.pack(f"{len(v)}f", *v)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_db: Optional[sqlite3.Connection] = None


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    INTEGER PRIMARY KEY,
            applied_at REAL NOT NULL
        )
        """
    )


def _get_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
    return int(row["version"] or 0)


def _migration_001_initial(conn: sqlite3.Connection) -> None:
    conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS memories (
            id            TEXT PRIMARY KEY,
            content       TEXT NOT NULL,
            tier          TEXT NOT NULL,
            importance    REAL NOT NULL DEFAULT 0.5,
            created_at    REAL NOT NULL,
            last_accessed REAL NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS mem_vss USING vec0(
            embedding float[{EMBEDDING_DIM}]
        );
    """)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def _migration_002_add_scope(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "memories", "scope"):
        conn.execute("ALTER TABLE memories ADD COLUMN scope TEXT NOT NULL DEFAULT 'global'")
    conn.execute("UPDATE memories SET scope = 'global' WHERE scope IS NULL")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_scope_tier_last_accessed"
        " ON memories(scope, tier, last_accessed)"
    )


MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _migration_001_initial,
    2: _migration_002_add_scope,
}


def _apply_migrations(conn: sqlite3.Connection) -> None:
    _ensure_migrations_table(conn)
    current = _get_schema_version(conn)
    for version in range(current + 1, CURRENT_SCHEMA_VERSION + 1):
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise RuntimeError(f"missing migration for schema version {version}")
        migration(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, time.time()),
        )
    conn.commit()


def db() -> sqlite3.Connection:
    global _db
    if _db is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        _apply_migrations(conn)
        _prune(conn)
        _db = conn
    return _db


def _prune(conn: sqlite3.Connection) -> None:
    """Delete ephemeral memories not accessed within PRUNE_AFTER_DAYS."""
    cutoff = time.time() - PRUNE_AFTER_DAYS * 86400
    stale = conn.execute(
        "SELECT rowid FROM memories WHERE tier='ephemeral' AND last_accessed < ?", (cutoff,)
    ).fetchall()
    for row in stale:
        conn.execute("DELETE FROM mem_vss WHERE rowid = ?", (row["rowid"],))
    conn.execute("DELETE FROM memories WHERE tier='ephemeral' AND last_accessed < ?", (cutoff,))
    conn.commit()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _decay_score(
    similarity: float, importance: float, tier: str, last_accessed: float
) -> float:
    age_days = (time.time() - last_accessed) / 86400
    hl = HALF_LIFE[tier]
    decay = 1.0 if hl == float("inf") else math.exp(-age_days / hl)
    return similarity * importance * decay


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP("memory")


@mcp.tool()
def remember(content: str, tier: str = "warm", importance: float = 0.5, scope: str = "global") -> dict:
    """
    Store a memory.

    tier:
      'core'      — permanent, never fades (identity, strong preferences, rules)
      'warm'      — 30-day half-life (active projects, learnings, context)
      'ephemeral' — 2-day half-life  (session facts, transient notes)

    importance: 0.0 – 1.0 (default 0.5). Higher importance resists decay.
    """
    if tier not in VALID_TIERS:
        return {"stored": False, "error": f"tier must be one of {sorted(VALID_TIERS)}"}
    if not content or not content.strip():
        return {"stored": False, "error": "content cannot be empty"}
    if not scope or not scope.strip():
        return {"stored": False, "error": "scope cannot be empty"}
    importance = max(0.0, min(1.0, float(importance)))

    mem_id = str(uuid.uuid4())
    now = time.time()
    vec = embed(content.strip())

    conn = db()
    cur = conn.execute(
        "INSERT INTO memories (id, content, tier, scope, importance, created_at, last_accessed)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (mem_id, content.strip(), tier, scope.strip(), importance, now, now),
    )
    conn.execute(
        "INSERT INTO mem_vss (rowid, embedding) VALUES (?, ?)",
        (cur.lastrowid, serialize(vec)),
    )
    conn.commit()

    return {"id": mem_id, "tier": tier, "scope": scope.strip(), "importance": importance, "stored": True}


@mcp.tool()
def recall(query: str, limit: int = 5, scope: str = "global") -> list:
    """
    Semantic search across all memories, ranked by relevance × importance × decay.
    Recalling a memory resets its last_accessed clock, keeping it alive.
    Returns up to `limit` results (max 20).
    """
    if not query or not query.strip():
        return []
    if not scope or not scope.strip():
        return []
    limit = max(1, min(20, int(limit)))
    fetch = limit * 3  # over-fetch for decay re-ranking

    q_vec = embed(query.strip())
    conn = db()

    rows = conn.execute(
        """
        SELECT m.id, m.content, m.tier, m.scope, m.importance, m.last_accessed, m.rowid,
               v.distance
        FROM mem_vss v
        JOIN memories m ON m.rowid = v.rowid
        WHERE v.embedding MATCH ? AND k = ? AND m.scope = ?
        ORDER BY v.distance
        """,
        (serialize(q_vec), fetch, scope.strip()),
    ).fetchall()

    # unit vectors: cosine_similarity = 1 - L2_distance² / 2
    scored = []
    for r in rows:
        cosine = max(0.0, 1.0 - (r["distance"] ** 2) / 2.0)
        score = _decay_score(cosine, r["importance"], r["tier"], r["last_accessed"])
        scored.append((score, r))

    scored.sort(key=lambda x: -x[0])
    top = scored[:limit]

    # bump last_accessed on returned memories
    now = time.time()
    for _, r in top:
        conn.execute("UPDATE memories SET last_accessed = ? WHERE id = ?", (now, r["id"]))
    conn.commit()

    return [
        {
            "id": r["id"],
            "content": r["content"],
            "tier": r["tier"],
            "scope": r["scope"],
            "score": round(s, 4),
        }
        for s, r in top
    ]


@mcp.tool()
def forget(memory_id: str) -> dict:
    """Delete a memory permanently by its ID."""
    conn = db()
    row = conn.execute("SELECT rowid FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if not row:
        return {"deleted": False, "error": "memory not found"}
    conn.execute("DELETE FROM mem_vss WHERE rowid = ?", (row["rowid"],))
    conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    return {"deleted": True}


@mcp.tool()
def memories(tier: Optional[str] = None, scope: str = "global") -> list:
    """
    List all stored memories, optionally filtered by tier ('core', 'warm', 'ephemeral').
    Sorted by vitality (importance × decay) so the most alive memories appear first.
    """
    if tier is not None and tier not in VALID_TIERS:
        return []
    if not scope or not scope.strip():
        return []

    conn = db()
    scope = scope.strip()
    if tier:
        rows = conn.execute(
            "SELECT id, content, tier, scope, importance, last_accessed"
            " FROM memories WHERE tier = ? AND scope = ?",
            (tier, scope),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, content, tier, scope, importance, last_accessed"
            " FROM memories WHERE scope = ?",
            (scope,),
        ).fetchall()

    now = time.time()
    result = []
    for r in rows:
        age_days = (now - r["last_accessed"]) / 86400
        hl = HALF_LIFE[r["tier"]]
        decay = 1.0 if hl == float("inf") else math.exp(-age_days / hl)
        vitality = round(r["importance"] * decay, 4)
        result.append(
            {
                "id": r["id"],
                "content": r["content"],
                "tier": r["tier"],
                "scope": r["scope"],
                "importance": r["importance"],
                "age_days": round(age_days, 1),
                "vitality": vitality,
            }
        )

    result.sort(key=lambda x: -x["vitality"])
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
