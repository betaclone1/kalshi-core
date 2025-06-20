import os
import sqlite3
from kalshi_api_util import get_event_json, get_current_event_ticker
from datetime import datetime
import pytz
import time

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

# Connect to (or create) the SQLite DB
conn = sqlite3.connect(os.path.join(BASE_DIR, "data", "kalshi_market_log.db"))
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS kalshi_market_log (
        timestamp TEXT,
        event_ticker TEXT,
        strike_price REAL,
        yes_ask INTEGER,
        yes_bid INTEGER,
        no_ask INTEGER,
        no_bid INTEGER,
        last_price INTEGER,
        volume INTEGER,
        open_interest INTEGER,
        btc_price REAL
    )
''')

try:
    while True:
        try:
            data = get_event_json()
            eastern = pytz.timezone("US/Eastern")
            ts = datetime.now(eastern).isoformat()
            event_ticker = data["event"]["event_ticker"]
            markets = data.get("markets", [])
            print(f"[{ts}] ✅ Market ticker: {event_ticker}, {len(markets)} strikes loaded.")

            # Fetch the most recent BTC price from btc_price_history.db
            btc_conn = sqlite3.connect(os.path.join(BASE_DIR, "../coinbase-api/coinbase-btc/data/btc_price_history.db"))
            btc_cursor = btc_conn.cursor()
            btc_cursor.execute("SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1")
            btc_price_row = btc_cursor.fetchone()
            btc_price = btc_price_row[0] if btc_price_row else None
            btc_conn.close()

            for market in markets:
                cursor.execute('''
                    INSERT INTO kalshi_market_log (
                        timestamp, event_ticker, strike_price,
                        yes_ask, yes_bid, no_ask, no_bid,
                        last_price, volume, open_interest, btc_price
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ts,
                    event_ticker,
                    market.get("floor_strike", 0.0),
                    market.get("yes_ask", 0),
                    market.get("yes_bid", 0),
                    market.get("no_ask", 0),
                    market.get("no_bid", 0),
                    market.get("last_price", 0),
                    market.get("volume", 0),
                    market.get("open_interest", 0),
                    btc_price
                ))

            conn.commit()
            import json
            snapshot_path = os.path.join(BASE_DIR, "data", "latest_market_snapshot.json")
            with open(snapshot_path, "w") as f:
                json.dump({
                    "title": data["event"].get("title", "No title"),
                    "markets": markets
                }, f)
            print(f"[{ts}] ✅ Snapshot saved to {snapshot_path}")
            print(f"[{ts}] ✅ Saved {len(markets)} rows to kalshi_market_log.db")
            with open(os.path.join(BASE_DIR, "data", "kalshi_logger_heartbeat.txt"), "w") as hb:
                hb.write(f"{ts} Kalshi logger alive\n")

        except Exception as e:
            print(f"[{datetime.now().isoformat()}] ❌ Kalshi API error: {e}")

        time.sleep(1)

except KeyboardInterrupt:
    print("🛑 Watchdog terminated by user.")

conn.close()