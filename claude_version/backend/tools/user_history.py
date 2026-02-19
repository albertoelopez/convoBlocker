"""User history tool for querying and storing message data in SQLite."""

import json
import logging
import os
import sqlite3
import time

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'chat_blocker.db')


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Create the user_messages table if it does not exist."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp REAL NOT NULL,
            flagged INTEGER DEFAULT 0
        )
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_user_messages_username
        ON user_messages (username)
    ''')
    conn.commit()


@tool
def get_user_history(username: str, message: str) -> str:
    """Query a user's chat history and store their current message.

    Retrieves historical stats for the given username from the local SQLite
    database and records the current message. Returns total messages,
    recent message count (last 10 minutes), flag count, and first-seen time.

    Args:
        username: The YouTube username to look up.
        message: The current message to store.

    Returns:
        JSON string with user history stats.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        _ensure_table(conn)

        now = time.time()
        ten_minutes_ago = now - 600

        # Store current message
        conn.execute(
            'INSERT INTO user_messages (username, message, timestamp) VALUES (?, ?, ?)',
            (username, message, now),
        )
        conn.commit()

        # Total messages from this user
        row = conn.execute(
            'SELECT COUNT(*) FROM user_messages WHERE username = ?',
            (username,),
        ).fetchone()
        total_messages = row[0] if row else 0

        # Messages in last 10 minutes
        row = conn.execute(
            'SELECT COUNT(*) FROM user_messages WHERE username = ? AND timestamp > ?',
            (username, ten_minutes_ago),
        ).fetchone()
        recent_messages = row[0] if row else 0

        # Flagged message count
        row = conn.execute(
            'SELECT COUNT(*) FROM user_messages WHERE username = ? AND flagged = 1',
            (username,),
        ).fetchone()
        flag_count = row[0] if row else 0

        # First seen
        row = conn.execute(
            'SELECT MIN(timestamp) FROM user_messages WHERE username = ?',
            (username,),
        ).fetchone()
        first_seen = row[0] if row and row[0] else now

        result = {
            "username": username,
            "total_messages": total_messages,
            "recent_messages": recent_messages,
            "flag_count": flag_count,
            "first_seen": first_seen,
        }
        return json.dumps(result)
    except sqlite3.Error as e:
        logger.error("SQLite error querying history for '%s': %s", username, e)
        return json.dumps({
            "username": username,
            "total_messages": 0,
            "recent_messages": 0,
            "flag_count": 0,
            "first_seen": time.time(),
            "error": str(e),
        })
    finally:
        conn.close()
