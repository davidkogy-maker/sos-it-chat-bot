import sqlite3
import time
import re

DB_PATH = "cache.sqlite3"

conn = sqlite3.connect(DB_PATH, check_same_thread=False)

conn.execute("""
CREATE TABLE IF NOT EXISTS cache (
question TEXT PRIMARY KEY,
answer TEXT,
timestamp INTEGER
)
""")

conn.commit()


def normalize_question(q):
    q = q.lower().strip()
    q = re.sub(r"\s+", " ", q)
    q = q.replace("?", "")
    return q


def get_cached_answer(question):

    key = normalize_question(question)

    row = conn.execute(
        "SELECT answer FROM cache WHERE question=?",
        (key,)
    ).fetchone()

    if row:
        return row[0]

    return None


def save_answer(question, answer):

    key = normalize_question(question)

    conn.execute(
        "INSERT OR REPLACE INTO cache(question,answer,timestamp) VALUES(?,?,?)",
        (key, answer, int(time.time()))
    )

    conn.commit()
