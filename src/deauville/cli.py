import argparse
import sys
from datetime import date, datetime

import uvicorn

from deauville.api import create_app
from deauville.errors import FestivalError
from deauville.models import SoloShow
from deauville.storage import JSONStorage, Storage


def print_summary(festival) -> None:
    print(f"{festival.name}")
    print(f"From {festival.first_day} to {festival.last_day}")
    v_count = len(festival.venues)
    a_count = len(festival.artists)
    p_count = len(festival.performances)
    print(f"{v_count} venues, {a_count} artists, {p_count} performances")


def print_venues(festival) -> None:
    total_seats = sum(v.capacity for v in festival.venues)
    for v in festival.venues:
        print(f"{v.slug}: {v.name}, {v.capacity} seats")
    print(f"Total: {total_seats} seats")


def print_programme(festival, day_str: str) -> None:
    try:
        target_date = date.fromisoformat(day_str)
    except ValueError as e:
        raise ValueError(f"'{day_str}' is not a day, use YYYY-MM-DD.") from e

    day_perfs = [p for p in festival.performances if p.festival_day == day_str]
    if not day_perfs:
        available_days = sorted({p.festival_day for p in festival.performances})
        print(f"No performance on '{day_str}'. Days: {', '.join(available_days)}")
        return

    day_perfs.sort(key=lambda p: p.start_datetime)
    formatted_date = f"{target_date:%A %d %B}".replace(" 0", " ")
    print(f"Programme for {formatted_date}:")

    for perf in day_perfs:
        s = perf.start_datetime
        e = perf.end_datetime
        time_slot = f"{s:%H:%M}-{e:%H:%M}"
        venue_obj = festival.venues_map.get(perf.venue)
        v_name = venue_obj.name if venue_obj else perf.venue
        print(f"{time_slot} | {v_name} | {perf.title} ({perf.kind})")


def print_artist(festival, artist_slug: str) -> None:
    artist = festival.find_artist(artist_slug)
    if not artist:
        raise ValueError(f"No artist '{artist_slug}'.")

    appearances = festival.artist_performances(artist_slug)
    print(artist.name)
    for perf, role in appearances:
        f_day = date.fromisoformat(perf.festival_day)
        day_prefix = f"{f_day:%a %d}".replace(" 0", " ")
        s = perf.start_datetime
        e = perf.end_datetime
        time_slot = f"{s:%H:%M}-{e:%H:%M}"
        v_obj = festival.venues_map.get(perf.venue)
        v_name = v_obj.name if v_obj else perf.venue
        print(f"{day_prefix} {time_slot} | {v_name} | {perf.title} ({role})")


def print_now(festival, moment_str: str) -> None:
    try:
        target_moment = datetime.fromisoformat(moment_str)
    except ValueError as e:
        raise ValueError(
            f"'{moment_str}' is not a valid ISO datetime (use YYYY-MM-DDTHH:MM)."
        ) from e

    on_stage = festival.now_playing(target_moment)
    up_next = festival.up_next(target_moment, limit=3)

    time_display = target_moment.strftime("%Y-%m-%d %H:%M")
    print(f"On stage at {time_display}:")
    for p in on_stage:
        v_obj = festival.venues_map.get(p.venue)
        v_name = v_obj.name if v_obj else p.venue
        print(f"- {p.title} at {v_name}, until {p.end_datetime:%H:%M}")

    print("Up next:")
    for p in up_next:
        s = p.start_datetime
        e = p.end_datetime
        v_obj = festival.venues_map.get(p.venue)
        v_name = v_obj.name if v_obj else p.venue
        print(f"- {s:%H:%M}-{e:%H:%M} | {v_name} | {p.title} ({p.kind})")


def add_solo_interactive(festival, storage: Storage) -> None:
    title = input("Title: ").strip()
    if not title:
        raise ValueError("Title cannot be empty.")

    artist = input("Artist (slug): ").strip()
    venue = input("Venue (slug): ").strip()

    start_raw = input("Start (YYYY-MM-DDTHH:MM): ").strip()
    try:
        _ = datetime.fromisoformat(start_raw)
    except ValueError as e:
        raise ValueError(
            f"'{start_raw}' is not a valid datetime format (YYYY-MM-DDTHH:MM)."
        ) from e

    duration_raw = input("Duration (minutes): ").strip()
    if not duration_raw.isdigit():
        raise ValueError(f"'{duration_raw}' is not a number of minutes.")
    duration = int(duration_raw)

    new_perf = SoloShow(
        title=title,
        venue=venue,
        start=start_raw,
        duration_minutes=duration,
        artist=artist,
    )

    festival.add_performance(new_perf)
    storage.save(festival)
    print(f"Added: {new_perf.id}")


def cancel_performance_cli(festival, storage: Storage, perf_id: str) -> None:
    cancelled_title = festival.cancel_performance(perf_id)
    storage.save(festival)
    print(f"Cancelled: {cancelled_title}")


def run_server(storage: Storage, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run uvicorn server directly."""
    app = create_app(storage=storage)
    uvicorn.run(app, host=host, port=port)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deauville Festival du Rire CLI")
    parser.add_argument(
        "--data", default="data/festival.json", help="Path to festival JSON file"
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("venues", help="List venues")

    prog_parser = subparsers.add_parser("programme", help="Show programme for a day")
    prog_parser.add_argument("day", help="Day in YYYY-MM-DD format")

    artist_parser = subparsers.add_parser("artist", help="Show artist performances")
    artist_parser.add_argument("slug", help="Artist slug")

    now_parser = subparsers.add_parser("now", help="Shows on stage now")
    now_parser.add_argument("moment", help="ISO datetime YYYY-MM-DDTHH:MM")

    subparsers.add_parser("add", help="Add solo show interactively")

    cancel_parser = subparsers.add_parser("cancel", help="Cancel a performance")
    cancel_parser.add_argument("perf_id", help="Performance ID")

    serve_parser = subparsers.add_parser("serve", help="Start the web API server")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    storage = JSONStorage(path=args.data)

    try:
        if args.command is None:
            festival = storage.load()
            print_summary(festival)
        elif args.command == "venues":
            festival = storage.load()
            print_venues(festival)
        elif args.command == "programme":
            festival = storage.load()
            print_programme(festival, args.day)
        elif args.command == "artist":
            festival = storage.load()
            print_artist(festival, args.slug)
        elif args.command == "now":
            festival = storage.load()
            print_now(festival, args.moment)
        elif args.command == "add":
            festival = storage.load()
            add_solo_interactive(festival, storage)
        elif args.command == "cancel":
            festival = storage.load()
            cancel_performance_cli(festival, storage, args.perf_id)
        elif args.command == "serve":
            run_server(storage, host=args.host, port=args.port)
        else:
            parser.print_help()

    except (FestivalError, ValueError, FileNotFoundError) as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
