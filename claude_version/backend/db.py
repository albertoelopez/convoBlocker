import json
import time
from pathlib import Path

import aiosqlite

_DB_PATH = Path(__file__).resolve().parent / "chat_blocker.db"

# Re-usable connection kept open for the lifetime of the server.
_conn: aiosqlite.Connection | None = None


async def _get_conn() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        _conn = await aiosqlite.connect(str(_DB_PATH))
        _conn.row_factory = aiosqlite.Row
    return _conn


async def init_db() -> None:
    """Create tables if they do not exist."""
    conn = await _get_conn()
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS user_messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT    NOT NULL,
            message   TEXT    NOT NULL,
            timestamp REAL    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL,
            decision   TEXT    NOT NULL,
            reason     TEXT    NOT NULL,
            categories TEXT    NOT NULL DEFAULT '[]',
            timestamp  REAL    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS stats (
            id                 INTEGER PRIMARY KEY CHECK (id = 1),
            messages_analyzed  INTEGER NOT NULL DEFAULT 0,
            users_blocked      INTEGER NOT NULL DEFAULT 0,
            cache_hits         INTEGER NOT NULL DEFAULT 0
        );

        INSERT OR IGNORE INTO stats (id, messages_analyzed, users_blocked, cache_hits)
        VALUES (1, 0, 0, 0);
        """
    )
    await conn.commit()


# ------------------------------------------------------------------
# Messages
# ------------------------------------------------------------------

async def store_message(username: str, message: str) -> None:
    conn = await _get_conn()
    await conn.execute(
        "INSERT INTO user_messages (username, message, timestamp) VALUES (?, ?, ?)",
        (username, message, time.time()),
    )
    await conn.commit()


async def get_user_history(username: str, limit: int = 50) -> list[dict]:
    conn = await _get_conn()
    cursor = await conn.execute(
        "SELECT username, message, timestamp FROM user_messages "
        "WHERE username = ? ORDER BY timestamp DESC LIMIT ?",
        (username, limit),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# ------------------------------------------------------------------
# Decisions
# ------------------------------------------------------------------

async def store_decision(
    username: str,
    decision: str,
    reason: str,
    categories: list[str] | None = None,
) -> None:
    conn = await _get_conn()
    await conn.execute(
        "INSERT INTO decisions (username, decision, reason, categories, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        (username, decision, reason, json.dumps(categories or []), time.time()),
    )
    await conn.commit()


async def get_block_log(limit: int = 100) -> list[dict]:
    conn = await _get_conn()
    cursor = await conn.execute(
        "SELECT username, decision, reason, categories, timestamp "
        "FROM decisions ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    results = []
    for row in rows:
        entry = dict(row)
        entry["categories"] = json.loads(entry["categories"])
        results.append(entry)
    return results


async def delete_decision(decision_id: int) -> bool:
    conn = await _get_conn()
    cursor = await conn.execute(
        "DELETE FROM decisions WHERE id = ?", (decision_id,)
    )
    await conn.commit()
    return cursor.rowcount > 0


# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------

async def get_stats() -> dict:
    conn = await _get_conn()
    cursor = await conn.execute(
        "SELECT messages_analyzed, users_blocked, cache_hits FROM stats WHERE id = 1"
    )
    row = await cursor.fetchone()
    return dict(row) if row else {"messages_analyzed": 0, "users_blocked": 0, "cache_hits": 0}


async def update_stats(
    messages_analyzed: int = 0,
    users_blocked: int = 0,
    cache_hits: int = 0,
) -> None:
    """Increment stat counters by the given amounts."""
    conn = await _get_conn()
    await conn.execute(
        "UPDATE stats SET "
        "messages_analyzed = messages_analyzed + ?, "
        "users_blocked = users_blocked + ?, "
        "cache_hits = cache_hits + ? "
        "WHERE id = 1",
        (messages_analyzed, users_blocked, cache_hits),
    )
    await conn.commit()


# ------------------------------------------------------------------
# Maintenance
# ------------------------------------------------------------------

async def cleanup_old_messages(max_age_hours: int = 24) -> int:
    """Delete messages older than *max_age_hours*. Returns rows removed."""
    conn = await _get_conn()
    cutoff = time.time() - max_age_hours * 3600
    cursor = await conn.execute(
        "DELETE FROM user_messages WHERE timestamp < ?", (cutoff,)
    )
    await conn.commit()
    return cursor.rowcount


async def close() -> None:
    """Shut down the database connection cleanly."""
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None
