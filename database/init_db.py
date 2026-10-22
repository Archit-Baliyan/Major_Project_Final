"""Creates the database, tables and demo data using the credentials in .env

Usage (from the project folder):   python database/init_db.py
This is an alternative to running schema.sql / seed.sql with the mysql command line.
WARNING: it DROPS and re-creates all tables (all existing data is lost).
"""
import sys
from pathlib import Path

import mysql.connector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from config import Config  # noqa: E402


def read_statements(path, db_name):
    text = path.read_text(encoding="utf-8").replace("smart_attendance", db_name)
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def init_db(db_name=None, seed=True, verbose=False):
    db_name = db_name or Config.DB_NAME
    conn = mysql.connector.connect(host=Config.DB_HOST, port=Config.DB_PORT,
                                   user=Config.DB_USER, password=Config.DB_PASSWORD, use_pure=True)
    cur = conn.cursor()
    files = [ROOT / "schema.sql"] + ([ROOT / "seed.sql"] if seed else [])
    for f in files:
        for stmt in read_statements(f, db_name):
            cur.execute(stmt)
        conn.commit()
        if verbose:
            print(f"Executed {f.name}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    try:
        init_db(verbose=True)
        print("Database ready. Now run:  python app.py")
    except mysql.connector.Error as err:
        print("MySQL error:", err)
        print("Check MySQL is running and DB_USER / DB_PASSWORD in your .env file.")
        sys.exit(1)
