from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
import sys
from typing import Any
import unicodedata


def slugify(text: str) -> str:
    """Normalize text into a clean URL-friendly slug."""
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
    return {a.get("slug") or slugify(a["name"]): a for a in artists}


def start_of(perf: dict[str, Any]) -> datetime:
    """Return the start datetime of a performance."""
    return datetime.fromisoformat(perf["start"])


def end_of(perf: dict[str, Any]) -> datetime:
    """Return the end datetime of a performance."""
    return start_of(perf) + timedelta(minutes=perf["duration_minutes"])


def festival_day_of(perf: dict[str, Any]) -> date:
    """A festival day ends at 06:00: subtract 6 hours from start."""
    return (start_of(perf) - timedelta(hours=6)).date()


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


def print_programme(festival: dict[str, Any], day_str: str) -> None:
    """Print the programme for a festival day using the 06:00 cutoff."""
    target_date = date.fromisoformat(day_str)
    venues_map = get_venues_map(festival["venues"])

    day_perfs = [p for p in festival["performances"] if festival_day_of(p) == target_date]
    day_perfs.sort(key=start_of)

    # Format heading: "Programme for Friday 11 June:"
    formatted_date = f"{target_date:%A %d %B}".replace(" 0", " ")
    print(f"Programme for {formatted_date}:")

    for perf in day_perfs:
        s = start_of(perf)
        e = end_of(perf)
        time_slot = f"{s:%H:%M}-{e:%H:%M}"
        venue_obj = venues_map.get(perf["venue"])
        venue_name = venue_obj["name"] if venue_obj else perf["venue"]
        title = perf["title"]
        kind = perf["kind"]
        print(f"{time_slot} | {venue_name} | {title} ({kind})")


def print_artist(festival: dict[str, Any], artist_slug: str) -> None:
    """Print an artist's performances with festival day prefix."""
    artists_map = get_artists_map(festival["artists"])
    if artist_slug not in artists_map:
        print(f"No artist '{artist_slug}'.")
        return

    artist_name = artists_map[artist_slug]["name"]
    venues_map = get_venues_map(festival["venues"])

    appearances: list[tuple[datetime, dict[str, Any], str]] = []
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
            appearances.append((start_of(perf), perf, role))

    appearances.sort(key=lambda item: item[0])

    print(artist_name)
    for _, perf, role in appearances:
        f_day = festival_day_of(perf)
        day_prefix = f"{f_day:%a %d}".replace(" 0", " ")
        s = start_of(perf)
        e = end_of(perf)
        time_slot = f"{s:%H:%M}-{e:%H:%M}"
        venue_obj = venues_map.get(perf["venue"])
        venue_name = venue_obj["name"] if venue_obj else perf["venue"]
        print(f"{day_prefix} {time_slot} | {venue_name} | {perf['title']} ({role})")


def print_now(festival: dict[str, Any], moment_str: str) -> None:
    """Print shows currently on stage and the next 3 upcoming shows."""
    target_moment = datetime.fromisoformat(moment_str)
    venues_map = get_venues_map(festival["venues"])
    perfs = festival["performances"]

    on_stage = [p for p in perfs if start_of(p) <= target_moment < end_of(p)]
    up_next = [p for p in perfs if start_of(p) > target_moment]
    up_next.sort(key=start_of)

    time_display = target_moment.strftime("%Y-%m-%d %H:%M")
    print(f"On stage at {time_display}:")
    for p in on_stage:
        v_obj = venues_map.get(p["venue"])
        v_name = v_obj["name"] if v_obj else p["venue"]
        print(f"- {p['title']} at {v_name}, until {end_of(p):%H:%M}")

    print("Up next:")
    for p in up_next[:3]:
        s = start_of(p)
        e = end_of(p)
        v_obj = venues_map.get(p["venue"])
        v_name = v_obj["name"] if v_obj else p["venue"]
        print(f"- {s:%H:%M}-{e:%H:%M} | {v_name} | {p['title']} ({p['kind']})")


def print_usage() -> None:
    """Print CLI usage guide."""
    print("Usage:")
    print("  uv run main.py")
    print("  uv run main.py venues")
    print("  uv run main.py programme <YYYY-MM-DD>")
    print("  uv run main.py artist <artist-slug>")
    print("  uv run main.py now <YYYY-MM-DDTHH:MM>")


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
    elif args[0] == "now":
        if len(args) < 2:
            print("Error: missing moment argument.")
            print_usage()
            sys.exit(1)
        print_now(festival, args[1])
    else:
        print_usage()


if __name__ == "__main__":
    main()