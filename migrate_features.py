import os
import secrets
import sqlite3

from app import app, db
from db import basedir


def table_exists(conn, table_name):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def column_exists(conn, table_name, column_name):
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def add_column(conn, table_name, column_sql):
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def migrate():
    db_path = os.path.join(basedir, "db.db")
    conn = sqlite3.connect(db_path)
    try:
        if table_exists(conn, "admin_user") and not column_exists(conn, "admin_user", "role"):
            add_column(conn, "admin_user", "role TEXT NOT NULL DEFAULT 'admin'")
            conn.execute("UPDATE admin_user SET role='admin' WHERE role IS NULL")

        if table_exists(conn, "equipment") and not column_exists(conn, "equipment", "qr_token"):
            add_column(conn, "equipment", "qr_token TEXT")
            conn.execute("UPDATE equipment SET qr_token=NULL")

        if table_exists(conn, "equipment"):
            cursor = conn.execute("SELECT id FROM equipment WHERE qr_token IS NULL")
            rows = cursor.fetchall()
            for (equipment_id,) in rows:
                token = secrets.token_urlsafe(16)
                conn.execute("UPDATE equipment SET qr_token=? WHERE id=?", (token, equipment_id))

        conn.commit()
    finally:
        conn.close()

    with app.app_context():
        db.create_all()

    print("Migration completed.")


if __name__ == "__main__":
    migrate()
