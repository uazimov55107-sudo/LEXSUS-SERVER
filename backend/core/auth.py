import sqlite3
import secrets
import hashlib
import hmac
import time
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "lexsus.db"

hasher = PasswordHasher()
SESSION_LIFETIME = 12 * 60 * 60


def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def init_db():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                success INTEGER NOT NULL,
                attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                csrf_hash TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_expiry
            ON sessions(expires_at)
        """)


def create_user(username, password, role="admin"):
    password_hash = hasher.hash(password)
    with connect() as db:
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role)
        )


def verify_user(username, password):
    with connect() as db:
        user = db.execute(
            "SELECT * FROM users WHERE username = ? AND active = 1",
            (username,)
        ).fetchone()

    if not user:
        return None

    try:
        if hasher.verify(user["password_hash"], password):
            if hasher.check_needs_rehash(user["password_hash"]):
                with connect() as db:
                    db.execute(
                        "UPDATE users SET password_hash = ? WHERE id = ?",
                        (hasher.hash(password), user["id"])
                    )
            return dict(user)
    except VerifyMismatchError:
        pass

    return None


def create_session(user_id):
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)

    with connect() as db:
        db.execute(
            """
            INSERT INTO sessions
            (token_hash, user_id, csrf_hash, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                token_hash(session_token),
                user_id,
                token_hash(csrf_token),
                int(time.time()) + SESSION_LIFETIME
            )
        )

    return session_token, csrf_token


def get_session(session_token):
    if not session_token:
        return None

    with connect() as db:
        row = db.execute(
            """
            SELECT users.id, users.username, users.role,
                   sessions.csrf_hash, sessions.expires_at
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
              AND sessions.expires_at > ?
              AND users.active = 1
            """,
            (token_hash(session_token), int(time.time()))
        ).fetchone()

    return dict(row) if row else None


def verify_csrf(session, csrf_token):
    if not session or not csrf_token:
        return False

    return hmac.compare_digest(
        session["csrf_hash"],
        token_hash(csrf_token)
    )


def delete_session(session_token):
    if not session_token:
        return

    with connect() as db:
        db.execute(
            "DELETE FROM sessions WHERE token_hash = ?",
            (token_hash(session_token),)
        )


def cleanup_sessions():
    with connect() as db:
        db.execute(
            "DELETE FROM sessions WHERE expires_at <= ?",
            (int(time.time()),)
        )
