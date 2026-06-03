# db.py
import os
import pymysql
from dotenv import load_dotenv
from flask import g

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASS", ""),
    "db": os.getenv("DB_NAME", "perwira_curfew_system"),
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
    "charset": "utf8mb4",
    "connect_timeout": 5
}

def get_db():
    """Get one DB connection per request"""
    if "db_conn" not in g:
        try:
            g.db_conn = pymysql.connect(**DB_CONFIG)
        except Exception as e:
            print(f"[DB ERROR] {e}")
            g.db_conn = None
    return g.db_conn

def init_db(app):
    """Register DB teardown with Flask"""
    @app.teardown_appcontext
    def close_db(exception=None):
        conn = g.pop("db_conn", None)
        if conn:
            conn.close()

def close_db(e=None):
    conn = g.pop("db", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass