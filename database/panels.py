import json
import time
from database.db import connect


def create_panels_table():
    conn = connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ticket_panels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '🎫',
            description TEXT DEFAULT '',
            embed_title TEXT DEFAULT '',
            embed_description TEXT DEFAULT '',
            embed_color INTEGER DEFAULT 5793266,
            button_label TEXT DEFAULT 'فتح تذكرة',
            button_style INTEGER DEFAULT 1,
            ticket_type TEXT DEFAULT 'دعم',
            ticket_name TEXT DEFAULT 'ticket-{username}',
            category_id INTEGER,
            support_role_id INTEGER,
            created_by INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ticket_panels_guild ON ticket_panels (guild_id, id)")
    conn.commit()
    conn.close()


def create_panel(guild_id, name, created_by, **fields):
    create_panels_table()
    allowed = {
        'emoji', 'description', 'embed_title', 'embed_description', 'embed_color',
        'button_label', 'button_style', 'ticket_type', 'ticket_name',
        'category_id', 'support_role_id'
    }
    fields = {k: v for k, v in fields.items() if k in allowed}
    now = int(time.time())
    keys = ['guild_id', 'name', 'created_by', 'created_at', 'updated_at', *fields.keys()]
    values = [guild_id, name, created_by, now, now, *fields.values()]
    placeholders = ', '.join('?' for _ in keys)
    conn = connect()
    cur = conn.execute(
        f"INSERT INTO ticket_panels ({', '.join(keys)}) VALUES ({placeholders})",
        values,
    )
    panel_id = cur.lastrowid
    conn.commit()
    conn.close()
    return get_panel(panel_id)


def get_panel(panel_id):
    create_panels_table()
    conn = connect()
    row = conn.execute('SELECT * FROM ticket_panels WHERE id = ?', (panel_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_panels(guild_id):
    create_panels_table()
    conn = connect()
    rows = conn.execute(
        'SELECT * FROM ticket_panels WHERE guild_id = ? ORDER BY id ASC',
        (guild_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_panel(panel_id, guild_id, **fields):
    create_panels_table()
    allowed = {
        'name', 'emoji', 'description', 'embed_title', 'embed_description', 'embed_color',
        'button_label', 'button_style', 'ticket_type', 'ticket_name',
        'category_id', 'support_role_id'
    }
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return get_panel(panel_id)
    fields['updated_at'] = int(time.time())
    query = ', '.join(f'{key} = ?' for key in fields)
    conn = connect()
    conn.execute(
        f'UPDATE ticket_panels SET {query} WHERE id = ? AND guild_id = ?',
        [*fields.values(), panel_id, guild_id],
    )
    conn.commit()
    conn.close()
    return get_panel(panel_id)


def delete_panel(panel_id, guild_id):
    create_panels_table()
    conn = connect()
    cur = conn.execute(
        'DELETE FROM ticket_panels WHERE id = ? AND guild_id = ?',
        (panel_id, guild_id),
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def serialize_panel(panel):
    return json.dumps(panel, ensure_ascii=False)
