import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


def slugify(text: str) -> str:
    """Normalize text into a clean URL-friendly slug (e.g. 'Théâtre' -> 'theatre')."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def load_festival(path: str = "data/festival.json") -> dict[str, Any]:
    """Load festival data from JSON file."""
    with open(Path(path), "r", encoding="utf-8") as f:
        return json.load(f)


def get_venues_map(venues: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return a mapping of venue slug -> venue dict."""
    return {slugify(v["name"]): v for v in venues}


def get_artists_map(artists: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return a mapping of artist slug -> artist dict."""
    # Artist objects in data may have a 'slug' or only 'name'
    return {a.get("slug") or slugify(a["name"]): a for a in artists}


def print_summary(festival: dict[str, Any]) -> None:
    """Print the festival overview (Step 00)."""
    name = festival["name"]
    first_day = festival["first_day"]
    last_day = festival["last_day"]
    venues_count = len(festival["venues"])
    artists_count = len(festival["artists"])
    performances_count = len(festival["performances"])

    print(f"{name}")
    print(f"From {first_day} to {last_day}")
    print(f"{venues_count} venues, {artists_count} artists, {performances_count} performances")


def print_venues(festival: dict[str, Any]) -> None:
    """Print venue list with slug and capacity, followed by total seats."""
    total_seats = 0
    for v in festival["venues"]:
        slug = slugify(v["name"])
        seats = v.get("capacity", 0)
        total_seats += seats
        print(f"{slug}: {v['name']}, {seats} seats")
    print(f"Total: {total_seats} seats")


def print_programme(festival: dict[str, Any], day: str) -> None:
    """Print the programme for a given day (naive YYYY-MM-DD filter)."""
    venues_map = get_venues_map(festival["venues"])
    day_perfs = [p for p in festival["performances"] if p["start"][:10] == day]

    if not day_perfs:
        available_days = sorted({p["start"][:10] for p in festival["performances"]})
        print(f"No performance on '{day}'. Days: {', '.join(available_days)}")
        return

    print(f"Programme for {day}:")
    day_perfs.sort(key=lambda p: p["start"])
    for perf in day_perfs:
        time_str = perf["start"][11:16]
        venue_obj = venues_map.get(perf["venue"])
        venue_name = venue_obj["name"] if venue_obj else perf["venue"]
        title = perf["title"]
        kind = perf["kind"]
        print(f"{time_str} | {venue_name} | {title} ({kind})")


def print_artist(festival: dict[str, Any], artist_slug: str) -> None:
    """Print an artist's scheduled performances and their roles."""
    artists_map = get_artists_map(festival["artists"])
    if artist_slug not in artists_map:
        print(f"No artist '{artist_slug}'.")
        return

    artist_name = artists_map[artist_slug]["name"]
    venues_map = get_venues_map(festival["venues"])

    appearances: list[tuple[str, str, str, str]] = []
    for perf in festival["performances"]:
        kind = perf.get("kind")
        role = None

        if kind == "solo" and perf.get("artist") == artist_slug:
            role = "solo"
        elif kind == "lineup":
            if perf.get("host") == artist_slug:
                role = "host"
            elif artist_slug in perf.get("acts", []):
                role = "act"
        elif kind == "workshop" and perf.get("teacher") == artist_slug:
            role = "teacher"

        if role:
            start_str = perf["start"].replace("T", " ")
            venue_obj = venues_map.get(perf["venue"])
            venue_name = venue_obj["name"] if venue_obj else perf["venue"]
            appearances.append((start_str, venue_name, perf["title"], role))

    # Chronological sort
    appearances.sort(key=lambda item: item[0])

    print(artist_name)
    for start_str, venue_name, title, role in appearances:
        print(f"{start_str} | {venue_name} | {title} ({role})")


def print_usage() -> None:
    """Print CLI usage guide."""
    print("Usage:")
    print("  uv run main.py")
    print("  uv run main.py venues")
    print("  uv run main.py programme <YYYY-MM-DD>")
    print("  uv run main.py artist <artist-slug>")


def main() -> None:
    festival = load_festival()
    args = sys.argv[1:]

    if len(args) == 0:
        print_summary(festival)
    elif args[0] == "venues":
        print_venues(festival)
    elif args[0] == "programme":
        if len(args) < 2:
            print("Error: missing day argument.")
            print_usage()
            sys.exit(1)
        print_programme(festival, args[1])
    elif args[0] == "artist":
        if len(args) < 2:
            print("Error: missing artist slug argument.")
            print_usage()
            sys.exit(1)
        print_artist(festival, args[1])
    else:
        print_usage()


if __name__ == "__main__":
    main()