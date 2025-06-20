import subprocess
import os
import time
from datetime import datetime

# Feed configurations
FEEDS = {
    "btc": {
        "script": "backend/logger/btc_price_watchdog.py",
        "heartbeat": "backend/logger/data/btc_logger_heartbeat.txt",
        "process": None
    },
    "kalshi": {
        "script": "backend/api/kalshi-api/kalshi_api_watchdog.py",
        "heartbeat": "backend/api/kalshi-api/data/kalshi_logger_heartbeat.txt",
        "process": None
    }
}

# Max allowed seconds since last heartbeat
MAX_DELAY = 3

def read_heartbeat(path):
    try:
        with open(path, "r") as f:
            timestamp_str = f.readline().strip().split()[0]
            return datetime.fromisoformat(timestamp_str).replace(tzinfo=None)
    except Exception:
        return None

def launch_process(script_path):
    return subprocess.Popen(["python", script_path])

def main():
    while True:
        for key, feed in FEEDS.items():
            hb_time = read_heartbeat(feed["heartbeat"])
            now = datetime.now().replace(tzinfo=None)

            if not hb_time or (now - hb_time).total_seconds() > MAX_DELAY:
                print(f"[{now}] ⚠️ {key.upper()} heartbeat stale or missing. Restarting...")
                if feed["process"] and feed["process"].poll() is None:
                    feed["process"].terminate()
                    time.sleep(1)
                feed["process"] = launch_process(feed["script"])
            else:
                print(f"[{now}] ✅ {key.upper()} feed alive.")

        time.sleep(2)

if __name__ == "__main__":
    print("🔁 Watchdog Supervisor running...")
    main()
