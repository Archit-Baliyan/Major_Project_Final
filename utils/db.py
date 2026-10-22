"""Small MySQL helper layer.

Every query uses %s placeholders with a separate parameter list, so user
input never gets concatenated into SQL (this is what stops SQL injection).
One connection is opened per request and closed automatically at the end.
"""
from contextlib import contextmanager

import mysql.connector
from flask import current_app, g


def get_db():
    if "db" not in g:
        cfg = current_app.config
        g.db = mysql.connector.connect(
            host=cfg["DB_HOST"], port=cfg["DB_PORT"], user=cfg["DB_USER"],
            password=cfg["DB_PASSWORD"], database=cfg["DB_NAME"],
            charset="utf8mb4", use_pure=True,
        )
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def query(sql, params=None, one=False):
    """Run a SELECT. Returns a list of dicts (or one dict / None if one=True)."""
    cur = get_db().cursor(dictionary=True)
    try:
        cur.execute(sql, tuple(params or ()))
        rows = cur.fetchall()
    finally:
        cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, params=None):
    """Run one INSERT/UPDATE/DELETE and commit. Returns last inserted id."""
    with transaction() as cur:
        cur.execute(sql, tuple(params or ()))
        return cur.lastrowid


@contextmanager
def transaction():
    """Use for multi-step writes: everything is committed together or rolled back."""
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        yield cur
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()
