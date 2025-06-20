import sys
from get_current_market_info import get_event_json

def parse_market_info(field):
    event_json = get_event_json()
    print("Searching for market containing:", event_json["event"]["event_ticker"])

    # Flatten event data for easy access
    if 'event' in event_json:
        event_json.update(event_json.pop('event'))

    # First check top-level fields
    if field in event_json:
        return event_json[field]

    # Check first market entry if field wasn't found at the top level
    if "markets" in event_json and isinstance(event_json["markets"], list):
        first_market = event_json["markets"][0]
        if field in first_market:
            return first_market[field]

    print(f"Field '{field}' not found in event data. Available keys: {event_json.keys()}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python parse_market_info.py <field_name>")
        sys.exit(1)

    field_name = sys.argv[1]
    value = parse_market_info(field_name)
    print(value)