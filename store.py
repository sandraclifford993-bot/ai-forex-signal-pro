import sqlite3, os
from datetime import datetime, timedelta, timezone
DB = os.getenv("DATABASE_PATH", "signals.db")

def db():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS signals(
          id INTEGER PRIMARY KEY AUTOINCREMENT, pair TEXT, decision TEXT, score INTEGER,
          entry_price REAL, entry_time TEXT, expiry_time TEXT, result TEXT DEFAULT 'PENDING',
          exit_price REAL, reason TEXT, candle_time TEXT UNIQUE)""")
        c.execute("CREATE TABLE IF NOT EXISTS device_tokens(token TEXT PRIMARY KEY)")
        c.commit()

def add_signal(s, expiry_minutes=5):
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(minutes=expiry_minutes)
    with db() as c:
        cur = c.execute("""INSERT OR IGNORE INTO signals
          (pair,decision,score,entry_price,entry_time,expiry_time,reason,candle_time)
          VALUES(?,?,?,?,?,?,?,?)""",
          (s["pair"],s["decision"],s["score"],s["entry_price"],now.isoformat(),
           expiry.isoformat(),s["reason"],f'{s["pair"]}|{s["candle_time"]}'))
        c.commit()
        return cur.lastrowid if cur.rowcount else None

def list_signals(limit=100):
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?",(limit,)).fetchall()]

def get_stats():
    with db() as c:
        rows=[r["result"] for r in c.execute("SELECT result FROM signals").fetchall()]
    w,l=rows.count("WIN"),rows.count("LOSS")
    return {"total":len(rows),"wins":w,"losses":l,"pending":rows.count("PENDING"),
            "win_rate":round(100*w/(w+l),2) if w+l else None}

def save_token(token):
    with db() as c:
        c.execute("INSERT OR IGNORE INTO device_tokens(token) VALUES(?)",(token,)); c.commit()

def get_tokens():
    with db() as c:
        return [r["token"] for r in c.execute("SELECT token FROM device_tokens").fetchall()]

def update_result(signal_id, result, exit_price):
    with db() as c:
        c.execute("UPDATE signals SET result=?,exit_price=? WHERE id=?",(result,exit_price,signal_id)); c.commit()
