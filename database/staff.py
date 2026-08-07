import sqlite3
import time

from database.db import apply_staff_xp_multiplier, connect

STAFF_STATS = {"tickets_claimed", "tickets_closed", "ratings_received"}


def _row_to_dict(row):
    return dict(row) if row is not None else None


def create_staff_table():
    conn = connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS staff_profiles (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 0,
            rank TEXT NOT NULL DEFAULT 'Trainee',
            tickets_claimed INTEGER NOT NULL DEFAULT 0,
            tickets_closed INTEGER NOT NULL DEFAULT 0,
            ratings_received INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def get_staff(user_id):
    create_staff_table()
    conn = connect()
    row = conn.execute("SELECT * FROM staff_profiles WHERE user_id = ?", (int(user_id),)).fetchone()
    conn.close()
    return _row_to_dict(row)


def create_staff(user_id):
    create_staff_table()
    now = int(time.time())
    conn = connect()
    conn.execute(
        """
        INSERT INTO staff_profiles (user_id, xp, level, rank, tickets_claimed, tickets_closed, ratings_received, created_at, updated_at)
        VALUES (?, 0, 0, 'Trainee', 0, 0, 0, ?, ?)
        ON CONFLICT(user_id) DO NOTHING
        """,
        (int(user_id), now, now),
    )
    row = conn.execute("SELECT * FROM staff_profiles WHERE user_id = ?", (int(user_id),)).fetchone()
    conn.commit()
    conn.close()
    return _row_to_dict(row)


def add_staff_xp(user_id, amount, guild_id=None, apply_multiplier=True):
    amount = int(amount)
    if guild_id is not None and apply_multiplier:
        amount = apply_staff_xp_multiplier(guild_id, amount)
    profile = create_staff(user_id)
    if amount <= 0:
        return profile
    from utils.ranks import calculate_level, rank_for_xp
    now = int(time.time())
    new_xp = int(profile["xp"]) + amount
    new_level = calculate_level(new_xp)
    new_rank = rank_for_xp(new_xp)["name"]
    conn = connect()
    conn.execute(
        """UPDATE staff_profiles
           SET xp = ?, level = ?, rank = ?, updated_at = ?
           WHERE user_id = ?""",
        (new_xp, new_level, new_rank, now, int(user_id)),
    )
    row = conn.execute("SELECT * FROM staff_profiles WHERE user_id = ?", (int(user_id),)).fetchone()
    conn.commit()
    conn.close()
    return _row_to_dict(row)


def update_staff_stat(user_id, stat, amount=1):
    if stat not in STAFF_STATS:
        raise ValueError(f"Unsupported staff stat: {stat}")
    create_staff(user_id)
    now = int(time.time())
    conn = connect()
    conn.execute(
        f"UPDATE staff_profiles SET {stat} = {stat} + ?, updated_at = ? WHERE user_id = ?",
        (int(amount), now, int(user_id)),
    )
    row = conn.execute("SELECT * FROM staff_profiles WHERE user_id = ?", (int(user_id),)).fetchone()
    conn.commit()
    conn.close()
    return _row_to_dict(row)


def get_staff_leaderboard(limit=10):
    create_staff_table()
    conn = connect()
    rows = conn.execute(
        """SELECT * FROM staff_profiles
           ORDER BY xp DESC, tickets_closed DESC, tickets_claimed DESC, ratings_received DESC
           LIMIT ?""",
        (int(limit),),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_staff_totals():
    create_staff_table()
    conn = connect()
    row = conn.execute(
        """SELECT COUNT(*) AS members, COALESCE(SUM(xp), 0) AS xp,
                  COALESCE(SUM(tickets_claimed), 0) AS tickets_claimed,
                  COALESCE(SUM(tickets_closed), 0) AS tickets_closed,
                  COALESCE(SUM(ratings_received), 0) AS ratings_received
           FROM staff_profiles"""
    ).fetchone()
    conn.close()
    return dict(row)
