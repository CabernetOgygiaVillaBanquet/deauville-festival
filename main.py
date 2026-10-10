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
    """Load festival data from JSON file with specific error handling."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Festival file '{path}' not found.")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupted festival data file: {e}") from e


def save_festival(festival: dict[str, Any], path: str = "data/festival.json") -> None:
    """Save festival data to JSON file with UTF-8 and formatting."""
    with open(Path(path), "w", encoding="utf-8") as f:
        json.dump(festival, f, ensure_ascii=False, indent=2)


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


def performance_id(perf: dict[str, Any]) -> str:
    """Construct unique id: <venue-slug>-YYYY-MM-DD-HHMM."""
    s = start_of(perf)
    time_compact = f"{s:%H%M}"
    return f"{perf['venue']}-{s:%Y-%m-%d}-{time_compact}"


def get_involved_artists(perf: dict[str, Any]) -> list[str]:
    """Return list of all artist slugs involved in a performance."""
    kind = perf.get("kind")
    if kind == "solo":
        artist = perf.get("artist")
        return [artist] if artist else []
    if kind == "lineup":
        artists = []
        if perf.get("host"):
            artists.append(perf["host"])
        artists.extend(perf.get("acts", []))
        return artists
    if kind == "workshop":
        teacher = perf.get("teacher")
        return [teacher] if teacher else []
    return []


def overlaps_with_gap(s1: datetime, e1: datetime, s2: datetime, e2: datetime, gap_minutes: int = 30) -> bool:
    """Check if two time intervals conflict considering a minimum 30 min gap."""
    gap = timedelta(minutes=gap_minutes)
    return s1 < e2 + gap and s2 < e1 + gap


def check_performance_rules(festival: dict[str, Any], new_perf: dict[str, Any]) -> None:
    """Validate all festival rules before scheduling a performance."""
    venues_map = get_venues_map(festival["venues"])
    artists_map = get_artists_map(festival["artists"])

    venue_slug = new_perf["venue"]
    if venue_slug not in venues_map:
        raise ValueError(f"Unknown venue '{venue_slug}'.")

    involved = get_involved_artists(new_perf)
    for a_slug in involved:
        if a_slug not in artists_map:
            raise ValueError(f"Unknown artist '{a_slug}'.")

    duration = new_perf["duration_minutes"]
    if not (1 <= duration <= 360):
        raise ValueError(f"Duration must be between 1 and 360 minutes (got {duration}).")

    perf_day = festival_day_of(new_perf)
    first_day = date.fromisoformat(festival["first_day"])
    last_day = date.fromisoformat(festival["last_day"])
    if not (first_day <= perf_day <= last_day):
        raise ValueError(f"{perf_day} is not a day of the festival.")

    new_s = start_of(new_perf)
    new_e = end_of(new_perf)
    venue_name = venues_map[venue_slug]["name"]

    for existing in festival["performances"]:
        ex_s = start_of(existing)
        ex_e = end_of(existing)

        # 30-minute venue turnaround gap rule
        if existing["venue"] == venue_slug:
            if overlaps_with_gap(new_s, new_e, ex_s, ex_e, gap_minutes=30):
                raise ValueError(
                    f"{venue_name} is busy with {existing['title']} ({ex_s:%Y-%m-%d %H:%M}-{ex_e:%H:%M})."
                )

        # 30-minute artist turnaround gap rule
        ex_involved = get_involved_artists(existing)
        for a_slug in involved:
            if a_slug in ex_involved:
                if overlaps_with_gap(new_s, new_e, ex_s, ex_e, gap_minutes=30):
                    a_name = artists_map[a_slug]["name"]
                    raise ValueError(f"{a_name} is on stage in {existing['title']}.")


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
    """Print the programme for a festival day."""
    try:
        target_date = date.fromisoformat(day_str)
    except ValueError as e:
        raise ValueError(f"'{day_str}' is not a day, use YYYY-MM-DD.") from e

    venues_map = get_venues_map(festival["venues"])
    day_perfs = [p for p in festival["performances"] if festival_day_of(p) == target_date]

    if not day_perfs:
        available_days = sorted({str(festival_day_of(p)) for p in festival["performances"]})
        print(f"No performance on '{day_str}'. Days: {', '.join(available_days)}")
        return

    day_perfs.sort(key=start_of)
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
    """Print an artist's scheduled performances."""
    artists_map = get_artists_map(festival["artists"])
    if artist_slug not in artists_map:
        raise ValueError(f"No artist '{artist_slug}'.")

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
    """Print shows currently on stage and upcoming ones."""
    try:
        target_moment = datetime.fromisoformat(moment_str)
    except ValueError as e:
        raise ValueError(f"'{moment_str}' is not a valid ISO datetime (use YYYY-MM-DDTHH:MM).") from e

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


def add_solo_interactive(festival: dict[str, Any]) -> None:
    """Interactively collect and schedule a new solo show."""
    title = input("Title: ").strip()
    if not title:
        raise ValueError("Title cannot be empty.")

    artist = input("Artist (slug): ").strip()
    venue = input("Venue (slug): ").strip()

    start_raw = input("Start (YYYY-MM-DDTHH:MM): ").strip()
    try:
        _ = datetime.fromisoformat(start_raw)
    except ValueError as e:
        raise ValueError(f"'{start_raw}' is not a valid datetime format (YYYY-MM-DDTHH:MM).") from e

    duration_raw = input("Duration (minutes): ").strip()
    if not duration_raw.isdigit():
        raise ValueError(f"'{duration_raw}' is not a number of minutes.")
    duration = int(duration_raw)

    new_perf = {
        "kind": "solo",
        "title": title,
        "artist": artist,
        "venue": venue,
        "start": start_raw,
        "duration_minutes": duration,
        "description": "",
    }

    check_performance_rules(festival, new_perf)
    festival["performances"].append(new_perf)
    save_festival(festival)

    new_id = performance_id(new_perf)
    print(f"Added: {new_id}")


def cancel_performance(festival: dict[str, Any], perf_id: str) -> None:
    """Cancel a performance by its calculated ID."""
    matching_idx = None
    cancelled_title = None

    for i, p in enumerate(festival["performances"]):
        if performance_id(p) == perf_id:
            matching_idx = i
            cancelled_title = p["title"]
            break

    if matching_idx is None:
        raise ValueError(f"No performance with ID '{perf_id}'.")

    festival["performances"].pop(matching_idx)
    save_festival(festival)
    print(f"Cancelled: {cancelled_title}")


def print_usage() -> None:
    """Print CLI usage guide."""
    print("Usage:")
    print("  uv run main.py")
    print("  uv run main.py venues")
    print("  uv run main.py programme <YYYY-MM-DD>")
    print("  uv run main.py artist <artist-slug>")
    print("  uv run main.py now <YYYY-MM-DDTHH:MM>")
    print("  uv run main.py add")
    print("  uv run main.py cancel <performance-id>")


def main() -> None:
    try:
        festival = load_festival()
        args = sys.argv[1:]

        if len(args) == 0:
            print_summary(festival)
        elif args[0] == "venues":
            print_venues(festival)
        elif args[0] == "programme":
            if len(args) < 2:
                raise ValueError("Missing day argument.")
            print_programme(festival, args[1])
        elif args[0] == "artist":
            if len(args) < 2:
                raise ValueError("Missing artist slug argument.")
            print_artist(festival, args[1])
        elif args[0] == "now":
            if len(args) < 2:
                raise ValueError("Missing moment argument.")
            print_now(festival, args[1])
        elif args[0] == "add":
            add_solo_interactive(festival)
        elif args[0] == "cancel":
            if len(args) < 2:
                raise ValueError("Missing performance ID argument.")
            cancel_performance(festival, args[1])
        else:
            print_usage()

    except (ValueError, FileNotFoundError) as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()