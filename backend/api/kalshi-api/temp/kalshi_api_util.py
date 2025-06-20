from get_current_market_info import get_event_json

def get_current_market_json(event_ticker):
    return get_event_json(event_ticker)

from datetime import datetime, timedelta
import pytz

def get_current_event_ticker():
    eastern = pytz.timezone("US/Eastern")
    now = datetime.now(eastern)
    next_hour = now + timedelta(hours=1)
    hour_str = f"{next_hour.hour:02d}"
    ticker = f"KXBTCD-{next_hour.strftime('%d%b').upper()}{hour_str}"
    return ticker