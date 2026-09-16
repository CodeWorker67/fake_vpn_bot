import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from config import DB_PATH


@dataclass(frozen=True)
class BotUserRow:
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    is_premium: bool
    joined_at: datetime


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_premium INTEGER NOT NULL DEFAULT 0,
                joined_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _row_to_bot_user(row: sqlite3.Row) -> BotUserRow:
    joined_raw = row["joined_at"]
    if isinstance(joined_raw, str):
        joined_at = datetime.strptime(joined_raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    else:
        joined_at = datetime.now(timezone.utc)
    return BotUserRow(
        user_id=int(row["user_id"]),
        username=row["username"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        is_premium=bool(row["is_premium"]),
        joined_at=joined_at,
    )


def record_start_user(
    *,
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    is_premium: bool,
) -> None:
    init_db()
    premium_flag = 1 if is_premium else 0
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO bot_users (
                user_id, username, first_name, last_name, is_premium, joined_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                is_premium = excluded.is_premium,
                joined_at = bot_users.joined_at
            """,
            (user_id, username, first_name, last_name, premium_flag, _now_iso()),
        )
        conn.commit()


def list_all_users() -> List[BotUserRow]:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT user_id, username, first_name, last_name, is_premium, joined_at
            FROM bot_users
            ORDER BY joined_at ASC, user_id ASC
            """
        )
        return [_row_to_bot_user(row) for row in cur.fetchall()]


def count_users() -> int:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM bot_users").fetchone()
        return int(row["cnt"]) if row else 0
