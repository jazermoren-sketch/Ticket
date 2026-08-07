from database.db import connect


def average_resolution_seconds(guild_id: int) -> int:
    conn = connect()
    row = conn.execute(
        """SELECT AVG(closed_at - created_at) AS avg_seconds FROM tickets
           WHERE guild_id = ? AND status = 'closed' AND closed_at IS NOT NULL AND created_at IS NOT NULL""",
        (guild_id,),
    ).fetchone()
    conn.close()
    return int(row["avg_seconds"] or 0)


def daily_ticket_counts(guild_id: int, limit: int = 14) -> list[dict]:
    conn = connect()
    rows = conn.execute(
        """SELECT date(created_at, 'unixepoch') AS day, COUNT(*) AS total
           FROM tickets WHERE guild_id = ?
           GROUP BY day ORDER BY day DESC LIMIT ?""",
        (guild_id, int(limit)),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def most_active_staff(guild_id: int) -> dict | None:
    conn = connect()
    row = conn.execute(
        """SELECT claimed_by AS user_id, COUNT(*) AS total
           FROM tickets
           WHERE guild_id = ? AND claimed_by IS NOT NULL
           GROUP BY claimed_by ORDER BY total DESC LIMIT 1""",
        (guild_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def average_rating(guild_id: int) -> float:
    conn = connect()
    row = conn.execute(
        "SELECT AVG(rating) AS avg_rating FROM tickets WHERE guild_id = ? AND rating IS NOT NULL",
        (guild_id,),
    ).fetchone()
    conn.close()
    return round(float(row["avg_rating"] or 0), 2)


def ticket_analytics(guild_id: int) -> dict:
    return {
        "average_resolution_seconds": average_resolution_seconds(guild_id),
        "daily_ticket_counts": daily_ticket_counts(guild_id),
        "most_active_staff": most_active_staff(guild_id),
        "average_rating": average_rating(guild_id),
    }
