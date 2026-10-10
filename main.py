import json
from pathlib import Path


def main():
    data_path = Path("data/festival.json")
    with open(data_path, "r", encoding="utf-8") as f:
        festival = json.load(f)

    name = festival["name"]
    start_date = festival["first_day"]
    end_date = festival["last_day"]
    venues_count = len(festival["venues"])
    artists_count = len(festival["artists"])
    performances_count = len(festival["performances"])

    print(f"{name}")
    print(f"From {start_date} to {end_date}")
    print(f"{venues_count} venues, {artists_count} artists, {performances_count} performances")


if __name__ == "__main__":
    main()