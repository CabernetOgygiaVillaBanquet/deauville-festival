from datetime import date, datetime
import sys
from typing import Any

from festival import (
    check_performance_rules,
    end_of,
    festival_day_of,
    get_artists_map,
    get_venues_list,
    get_venues_map,
    load_festival,
    performance_id,
    save_festival,
    start_of,
)


def print_summary(festival: dict[str, Any]) -> None:
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
    venues = get_venues_list(festival)
    total_seats = sum(v["capacity"] for v in venues)
    for v in venues:
        print(f"{v['slug']}: {v['name']}, {v['capacity']} seats")
    print(f"Total: {total_seats} seats")


def print_programme(festival: dict[str, Any], day_str: str) -> None:
    try:
        target_date = date.fromisoformat(day_str)
    except ValueError as e:
        raise ValueError(f"'{day_str}' is not a day, use YYYY-MM-DD.") from e

    venues_map = get_venues_map(festival)
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
        print(f"{time_slot} | {venue_name} | {perf['title']} ({perf['kind']})")


def print_artist(festival: dict[str, Any], artist_slug: str) -> None:
    artists_map = get_artists_map(festival)
    if artist_slug not in artists_map:
        raise ValueError(f"No artist '{artist_slug}'.")

    artist_name = artists_map[artist_slug]["name"]
    venues_map = get_venues_map(festival)

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
    try:
        target_moment = datetime.fromisoformat(moment_str)
    except ValueError as e:
        raise ValueError(f"'{moment_str}' is not a valid ISO datetime (use YYYY-MM-DDTHH:MM).") from e

    venues_map = get_venues_map(festival)
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