import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "todo")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")  # require / disable


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode=DB_SSLMODE,
    )


def init_db():
    """
    Creates tables if they don't exist.
    Also ensures last_seen column exists (needed for active users).
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            last_seen TIMESTAMP NULL
        );
        """
    )

    # in case table existed before without last_seen
    cur.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP NULL;
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS todos (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            done BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """
    )

    conn.commit()
    cur.close()
    conn.close()


def db_healthcheck() -> bool:
    """
    Used by /healthz readiness endpoint.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        _ = cur.fetchone()
        cur.close()
        conn.close()
        return True
    except Exception:
        return False


def get_user(username: str):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, username, password_hash FROM users WHERE username = %s;", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def create_user(username: str, pw_hash: str) -> bool:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash, last_seen) VALUES (%s, %s, NOW());",
            (username, pw_hash),
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except psycopg2.errors.UniqueViolation:
        return False
    except Exception:
        return False


def touch_user_last_seen(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET last_seen = NOW() WHERE id = %s;", (user_id,))
    conn.commit()
    cur.close()
    conn.close()


def users_total_count() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users;")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return int(count)


def active_users_count(minutes: int = 5) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM users WHERE last_seen >= NOW() - (%s || ' minutes')::interval;",
        (str(minutes),),
    )
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return int(count)


def list_todos(user_id: int):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT id, title, done FROM todos WHERE user_id = %s ORDER BY id DESC;",
        (user_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def add_todo(user_id: int, title: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO todos (user_id, title, done) VALUES (%s, %s, FALSE);",
        (user_id, title),
    )
    conn.commit()
    cur.close()
    conn.close()


def delete_todo(user_id: int, todo_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM todos WHERE id = %s AND user_id = %s;",
        (todo_id, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def todos_count(user_id: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM todos WHERE user_id = %s;", (user_id,))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return int(count)


def todos_total_count() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM todos;")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return int(count)
