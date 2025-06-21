from fastapi import APIRouter, HTTPException, status, Request
import sqlite3
import threading
import time
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re

def is_trade_expired(trade):
    contract = trade.get('contract', '')
    if not contract:
        return False
    match = re.search(r'BTC\s+(\d{1,2})(am|pm)', contract, re.IGNORECASE)
    if not match:
        return False
    hour = int(match.group(1))
    ampm = match.group(2).lower()
    if ampm == 'pm' and hour != 12:
        hour += 12
    elif ampm == 'am' and hour == 12:
        hour = 0
    now = datetime.now(ZoneInfo('America/New_York'))
    expiration = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    # If expiration hour is earlier than now but time is before expiration, handle day wrap:
    if expiration < now and (now - expiration).total_seconds() > 3600:
        expiration = expiration + timedelta(days=1)
    return now >= expiration

router = APIRouter()

# Define path for the trades database file
DB_TRADES_PATH = os.path.join(os.path.dirname(__file__), "trade_history/trades.db")

# Initialize trades DB and table
def init_trades_db():
    conn = sqlite3.connect(DB_TRADES_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        strike TEXT NOT NULL,
        side TEXT NOT NULL,
        price REAL NOT NULL,
        position INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        closed_at TEXT DEFAULT NULL,
        contract TEXT DEFAULT NULL
    )
    """)
    conn.commit()
    conn.close()

init_trades_db()

# Database helper functions
def get_db_connection():
    return sqlite3.connect(DB_TRADES_PATH)

def fetch_open_trades():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, time, strike, side, price, position, status, contract FROM trades WHERE status = 'open'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(["id","date","time","strike","side","price","position","status","contract"], row)) for row in rows]

def fetch_all_trades():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, time, strike, side, price, position, status, closed_at, contract FROM trades ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(["id","date","time","strike","side","price","position","status","closed_at","contract"], row)) for row in rows]

def insert_trade(trade):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO trades (date, time, strike, side, price, position, status, contract) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (trade['date'], trade['time'], trade['strike'], trade['side'], trade['price'] / 100, trade['position'], trade.get('status', 'open'), trade.get('contract'))
    )
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

def update_trade_status(trade_id, status, closed_at=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status == 'closed':
        if closed_at is None:
            utc_now = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
            est_now = utc_now.astimezone(ZoneInfo("America/New_York"))
            closed_at = est_now.isoformat()
        cursor.execute("UPDATE trades SET status = ?, closed_at = ? WHERE id = ?", (status, closed_at, trade_id))
    else:
        cursor.execute("UPDATE trades SET status = ? WHERE id = ?", (status, trade_id))
    conn.commit()
    conn.close()

def delete_trade(trade_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()

def fetch_recent_closed_trades(hours=24):
    conn = get_db_connection()
    cursor = conn.cursor()
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()
    cursor.execute("""
        SELECT id, date, time, strike, side, price, position, status, closed_at, contract
        FROM trades
        WHERE status = 'closed' AND closed_at >= ?
        ORDER BY closed_at DESC
    """, (cutoff_iso,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(["id","date","time","strike","side","price","position","status","closed_at","contract"], row)) for row in rows]

# API routes for trade management

@router.get("/trades")
def get_trades(status: str = None, recent_hours: int = None):
    if status == "open":
        return fetch_open_trades()
    elif status == "closed" and recent_hours:
        return fetch_recent_closed_trades(recent_hours)
    elif status == "closed":
        return [t for t in fetch_all_trades() if t["status"] == "closed"]
    return fetch_all_trades()

@router.post("/trades", status_code=status.HTTP_201_CREATED)
async def add_trade(request: Request):
    data = await request.json()
    required_fields = {"date", "time", "strike", "side", "price", "position"}
    if not required_fields.issubset(data.keys()):
        raise HTTPException(status_code=400, detail="Missing required trade fields")
    trade_id = insert_trade(data)
    return {"id": trade_id}

@router.put("/trades/{trade_id}")
async def update_trade(trade_id: int, request: Request):
    data = await request.json()
    if "status" not in data:
        raise HTTPException(status_code=400, detail="Missing 'status' field for update")
    closed_at = data.get("closed_at")
    update_trade_status(trade_id, data["status"], closed_at)
    return {"id": trade_id, "status": data["status"]}

@router.delete("/trades/{trade_id}")
def remove_trade(trade_id: int):
    delete_trade(trade_id)
    return {"id": trade_id, "deleted": True}

# Background trade monitoring thread

def check_stop_trigger(trade):
    # TODO: Implement your stop trigger logic here
    # For now, never triggers
    return False

def trade_monitor_loop():
    while True:
        try:
            open_trades = fetch_open_trades()
            for trade in open_trades:
                if check_stop_trigger(trade):
                    print(f"[Trade Monitor] Closing trade id={trade['id']} due to stop trigger")
                    update_trade_status(trade['id'], 'closed')
                elif is_trade_expired(trade):
                    print(f"[Trade Monitor] Auto-closing trade id={trade['id']} due to expiration")
                    update_trade_status(trade['id'], 'closed')
        except Exception as e:
            print(f"[Trade Monitor] Error: {e}")
        time.sleep(5)  # Check every 5 seconds

_monitor_thread = None

def start_trade_monitor():
    global _monitor_thread
    if _monitor_thread is None or not _monitor_thread.is_alive():
        _monitor_thread = threading.Thread(target=trade_monitor_loop, daemon=True)
        _monitor_thread.start()