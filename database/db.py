import sqlite3
import time
from pathlib import Path

DB_PATH = Path("data/tickets.db")
DB_PATH.parent.mkdir(exist_ok=True)

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = connect()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS guild_config (
        guild_id INTEGER PRIMARY KEY,
        category_id INTEGER,
        support_role_id INTEGER,
        archive_category_id INTEGER,
        transcript_channel_id INTEGER,
        log_channel_id INTEGER,
        auto_close_minutes INTEGER DEFAULT 0,
        sla_minutes INTEGER DEFAULT 0,
        promotion_channel_id INTEGER,
        staff_points_channel_id INTEGER,
        staff_xp_messages_per_point INTEGER NOT NULL DEFAULT 30,
        staff_xp_cooldown_seconds INTEGER NOT NULL DEFAULT 60,
        staff_xp_log_channel_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS staff_points (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        points INTEGER NOT NULL DEFAULT 0,
        tickets_claimed INTEGER NOT NULL DEFAULT 0,
        rating_points INTEGER NOT NULL DEFAULT 0,
        message_points INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS staff_xp_roles (
        guild_id INTEGER NOT NULL,
        role_id INTEGER NOT NULL,
        PRIMARY KEY (guild_id, role_id)
    );

    CREATE TABLE IF NOT EXISTS staff_messages (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        counted_messages INTEGER NOT NULL DEFAULT 0,
        pending_messages INTEGER NOT NULL DEFAULT 0,
        last_message_at INTEGER,
        updated_at INTEGER NOT NULL,
        PRIMARY KEY (guild_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS staff_promotions (
        guild_id INTEGER NOT NULL,
        role_id INTEGER NOT NULL,
        required_points INTEGER NOT NULL CHECK(required_points >= 0),
        PRIMARY KEY (guild_id, role_id)
    );

    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        ticket_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        claimed_by INTEGER,
        team TEXT,
        priority TEXT DEFAULT 'normal',
        tags TEXT DEFAULT '',
        created_at INTEGER NOT NULL,
        last_activity_at INTEGER NOT NULL,
        first_response_at INTEGER,
        closed_at INTEGER,
        close_reason TEXT,
        rating INTEGER,
        rating_comment TEXT
    );
    """)
    # Safe migration
    cfg_cols = {r["name"] for r in conn.execute("PRAGMA table_info(guild_config)")}
    for name, definition in {
        "sla_minutes": "INTEGER DEFAULT 0",
        "promotion_channel_id": "INTEGER",
        "staff_points_channel_id": "INTEGER",
        "staff_xp_messages_per_point": "INTEGER NOT NULL DEFAULT 30",
        "staff_xp_cooldown_seconds": "INTEGER NOT NULL DEFAULT 60",
        "staff_xp_log_channel_id": "INTEGER",
    }.items():
        if name not in cfg_cols:
            conn.execute(f"ALTER TABLE guild_config ADD COLUMN {name} {definition}")

    staff_points_cols = {r["name"] for r in conn.execute("PRAGMA table_info(staff_points)")}
    if "message_points" not in staff_points_cols:
        conn.execute("ALTER TABLE staff_points ADD COLUMN message_points INTEGER NOT NULL DEFAULT 0")

    ticket_cols = {r["name"] for r in conn.execute("PRAGMA table_info(tickets)")}
    for name, definition in {
        "team": "TEXT",
        "priority": "TEXT DEFAULT 'normal'",
        "tags": "TEXT DEFAULT ''",
        "last_activity_at": "INTEGER",
        "first_response_at": "INTEGER",
    }.items():
        if name not in ticket_cols:
            conn.execute(f"ALTER TABLE tickets ADD COLUMN {name} {definition}")

    now = int(time.time())
    conn.execute("UPDATE tickets SET last_activity_at = COALESCE(last_activity_at, created_at, ?)", (now,))
    conn.commit()
    conn.close()

def get_guild_config(guild_id):
    conn = connect()
    row = conn.execute("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)).fetchone()
    conn.close()
    return row

def set_guild_config(guild_id, **fields):
    allowed = {
        "category_id", "support_role_id", "archive_category_id",
        "transcript_channel_id", "log_channel_id", "auto_close_minutes",
        "sla_minutes", "promotion_channel_id", "staff_points_channel_id",
        "staff_xp_messages_per_point", "staff_xp_cooldown_seconds",
        "staff_xp_log_channel_id"
    }
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    conn = connect()
    existing = conn.execute("SELECT guild_id FROM guild_config WHERE guild_id = ?", (guild_id,)).fetchone()
    if existing:
        query = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE guild_config SET {query} WHERE guild_id = ?", [*fields.values(), guild_id])
    else:
        keys = ["guild_id", *fields.keys()]
        placeholders = ", ".join("?" for _ in keys)
        conn.execute(
            f"INSERT INTO guild_config ({', '.join(keys)}) VALUES ({placeholders})",
            [guild_id, *fields.values()],
        )
    conn.commit()
    conn.close()

def create_ticket(guild_id, channel_id, user_id, ticket_type):
    now = int(time.time())
    conn = connect()
    cur = conn.execute(
        """INSERT INTO tickets
        (guild_id, channel_id, user_id, ticket_type, created_at, last_activity_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (guild_id, channel_id, user_id, ticket_type, now, now),
    )
    conn.commit()
    ticket_id = cur.lastrowid
    conn.close()
    return ticket_id

def get_ticket_by_channel(channel_id, include_closed=False):
    conn = connect()
    query = "SELECT * FROM tickets WHERE channel_id = ?"
    if not include_closed:
        query += " AND status = 'open'"
    row = conn.execute(query, (channel_id,)).fetchone()
    conn.close()
    return row

def get_open_ticket_for_user(guild_id, user_id):
    conn = connect()
    row = conn.execute(
        "SELECT * FROM tickets WHERE guild_id = ? AND user_id = ? AND status = 'open'",
        (guild_id, user_id),
    ).fetchone()
    conn.close()
    return row

def update_ticket(channel_id, **fields):
    allowed = {
        "status", "claimed_by", "team", "priority", "tags",
        "last_activity_at", "first_response_at", "closed_at",
        "close_reason", "rating", "rating_comment"
    }
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    query = ", ".join(f"{key} = ?" for key in fields)
    conn = connect()
    conn.execute(f"UPDATE tickets SET {query} WHERE channel_id = ?", [*fields.values(), channel_id])
    conn.commit()
    conn.close()

def get_open_tickets_for_autoclose(guild_id, minutes):
    cutoff = int(time.time()) - (minutes * 60)
    conn = connect()
    rows = conn.execute(
        """SELECT * FROM tickets
        WHERE guild_id = ? AND status = 'open' AND last_activity_at <= ?""",
        (guild_id, cutoff),
    ).fetchall()
    conn.close()
    return rows


# =========================
# نظام نقاط الإدارة
# =========================

def add_staff_points(guild_id, user_id, amount, source="ticket"):
    """إضافة نقاط للإداري مع حفظ إحصائيات المصدر."""
    amount = int(amount)
    if amount <= 0:
        return get_staff_points(guild_id, user_id)

    conn = connect()
    conn.execute(
        """INSERT INTO staff_points
           (guild_id, user_id, points, tickets_claimed, rating_points, message_points)
           VALUES (?, ?, 0, 0, 0, 0)
           ON CONFLICT(guild_id, user_id) DO NOTHING""",
        (guild_id, user_id),
    )

    if source == "claim":
        conn.execute(
            """UPDATE staff_points
               SET points = points + ?,
                   tickets_claimed = tickets_claimed + 1
               WHERE guild_id = ? AND user_id = ?""",
            (amount, guild_id, user_id),
        )
    elif source == "rating":
        conn.execute(
            """UPDATE staff_points
               SET points = points + ?,
                   rating_points = rating_points + ?
               WHERE guild_id = ? AND user_id = ?""",
            (amount, amount, guild_id, user_id),
        )
    elif source == "message":
        conn.execute(
            """UPDATE staff_points
               SET points = points + ?,
                   message_points = message_points + ?
               WHERE guild_id = ? AND user_id = ?""",
            (amount, amount, guild_id, user_id),
        )
    else:
        conn.execute(
            "UPDATE staff_points SET points = points + ? WHERE guild_id = ? AND user_id = ?",
            (amount, guild_id, user_id),
        )

    row = conn.execute(
        "SELECT * FROM staff_points WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    conn.commit()
    conn.close()
    return row


def get_staff_points(guild_id, user_id):
    conn = connect()
    row = conn.execute(
        "SELECT * FROM staff_points WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    conn.close()

    if row is None:
        return {
            "guild_id": guild_id,
            "user_id": user_id,
            "points": 0,
            "tickets_claimed": 0,
            "rating_points": 0,
            "message_points": 0,
        }

    return dict(row)


def get_staff_leaderboard(guild_id, limit=10):
    conn = connect()
    rows = conn.execute(
        """SELECT * FROM staff_points
           WHERE guild_id = ?
           ORDER BY points DESC, tickets_claimed DESC
           LIMIT ?""",
        (guild_id, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# =========================
# نظام الترقيات
# =========================

def add_promotion(guild_id, role_id, required_points):
    conn = connect()
    conn.execute(
        """INSERT INTO staff_promotions (guild_id, role_id, required_points)
           VALUES (?, ?, ?)
           ON CONFLICT(guild_id, role_id)
           DO UPDATE SET required_points = excluded.required_points""",
        (guild_id, role_id, int(required_points)),
    )
    conn.commit()
    conn.close()


def remove_promotion(guild_id, role_id):
    conn = connect()
    cur = conn.execute(
        "DELETE FROM staff_promotions WHERE guild_id = ? AND role_id = ?",
        (guild_id, role_id),
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def get_promotions(guild_id):
    conn = connect()
    rows = conn.execute(
        """SELECT guild_id, role_id, required_points
           FROM staff_promotions
           WHERE guild_id = ?
           ORDER BY required_points ASC, role_id ASC""",
        (guild_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_promotion_for_role(guild_id, role_id):
    conn = connect()
    row = conn.execute(
        """SELECT guild_id, role_id, required_points
           FROM staff_promotions
           WHERE guild_id = ? AND role_id = ?""",
        (guild_id, role_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# =========================
# نقاط الرتبة الأساسية
# =========================

def get_member_base_points(guild_id, role_ids):
    role_ids = [int(role_id) for role_id in role_ids]
    if not role_ids:
        return 0
    placeholders = ",".join("?" for _ in role_ids)
    conn = connect()
    row = conn.execute(
        f"""SELECT COALESCE(MAX(required_points), 0) AS base_points
            FROM staff_promotions
            WHERE guild_id = ? AND role_id IN ({placeholders})""",
        [guild_id, *role_ids],
    ).fetchone()
    conn.close()
    return int(row["base_points"] if row else 0)


def get_member_effective_points(guild_id, user_id, role_ids):
    stats = get_staff_points(guild_id, user_id)
    base_points = get_member_base_points(guild_id, role_ids)
    earned_points = int(stats["points"])
    return {
        "earned_points": earned_points,
        "base_points": base_points,
        "effective_points": base_points + earned_points,
    }


# =========================
# Staff XP حسب الرسائل
# =========================

def upsert_staff_xp_role(guild_id, role_id):
    conn = connect()
    conn.execute(
        "INSERT OR IGNORE INTO staff_xp_roles (guild_id, role_id) VALUES (?, ?)",
        (guild_id, role_id),
    )
    conn.commit()
    conn.close()


def remove_staff_xp_role(guild_id, role_id):
    conn = connect()
    cur = conn.execute(
        "DELETE FROM staff_xp_roles WHERE guild_id = ? AND role_id = ?",
        (guild_id, role_id),
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def get_staff_xp_roles(guild_id):
    conn = connect()
    rows = conn.execute(
        "SELECT role_id FROM staff_xp_roles WHERE guild_id = ? ORDER BY role_id ASC",
        (guild_id,),
    ).fetchall()
    conn.close()
    return [int(row["role_id"]) for row in rows]


def add_staff_message(guild_id, user_id, messages_per_xp=30):
    messages_per_xp = max(1, int(messages_per_xp))
    now = int(time.time())
    conn = connect()
    conn.execute(
        """INSERT INTO staff_messages
           (guild_id, user_id, counted_messages, pending_messages, last_message_at, updated_at)
           VALUES (?, ?, 0, 0, NULL, ?)
           ON CONFLICT(guild_id, user_id) DO NOTHING""",
        (guild_id, user_id, now),
    )
    conn.execute(
        """UPDATE staff_messages
           SET counted_messages = counted_messages + 1,
               pending_messages = pending_messages + 1,
               last_message_at = ?,
               updated_at = ?
           WHERE guild_id = ? AND user_id = ?""",
        (now, now, guild_id, user_id),
    )
    row = conn.execute(
        "SELECT * FROM staff_messages WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    awarded = int(row["pending_messages"]) // messages_per_xp
    if awarded:
        remaining = int(row["pending_messages"]) % messages_per_xp
        conn.execute(
            """UPDATE staff_messages
               SET pending_messages = ?, updated_at = ?
               WHERE guild_id = ? AND user_id = ?""",
            (remaining, now, guild_id, user_id),
        )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM staff_messages WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    conn.close()
    data = dict(row)
    data["awarded_points"] = awarded
    return data


def get_staff_message_stats(guild_id, user_id):
    conn = connect()
    row = conn.execute(
        "SELECT * FROM staff_messages WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    conn.close()
    if row is None:
        return {
            "guild_id": guild_id,
            "user_id": user_id,
            "counted_messages": 0,
            "pending_messages": 0,
            "last_message_at": None,
            "updated_at": 0,
        }
    return dict(row)
