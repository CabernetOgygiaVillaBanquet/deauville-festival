from datetime import date, datetime
import sys

from festival import (
    Performance,
    load_festival,
    save_festival,
)


def print_summary(festival) -> None:
    print(f"{festival.name}")
    print(f"From {festival.first_day} to {festival.last_day}")
    print(f"{len(festival.venues)} venues, {len(festival.artists)} artists, {len(festival.performances)} performances")


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

    appearances: list[tuple[datetime, Performance, str]] = []
    for perf in festival.performances:
        role = perf.involves(artist_slug)
        if role:
            appearances.append((perf.start_datetime, perf, role))

    appearances.sort(key=lambda item: item[0])
    print(artist.name)
    for _, perf, role in appearances:
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
        raise ValueError(f"'{moment_str}' is not a valid ISO datetime (use YYYY-MM-DDTHH:MM).") from e

    perfs = festival.performances
    on_stage = [p for p in perfs if p.start_datetime <= target_moment < p.end_datetime]
    up_next = [p for p in perfs if p.start_datetime > target_moment]
    up_next.sort(key=lambda p: p.start_datetime)

    time_display = target_moment.strftime("%Y-%m-%d %H:%M")
    print(f"On stage at {time_display}:")
    for p in on_stage:
        v_obj = festival.venues_map.get(p.venue)
        v_name = v_obj.name if v_obj else p.venue
        print(f"- {p.title} at {v_name}, until {p.end_datetime:%H:%M}")

    print("Up next:")
    for p in up_next[:3]:
        s = p.start_datetime
        e = p.end_datetime
        v_obj = festival.venues_map.get(p.venue)
        v_name = v_obj.name if v_obj else p.venue
        print(f"- {s:%H:%M}-{e:%H:%M} | {v_name} | {p.title} ({p.kind})")


def add_solo_interactive(festival) -> None:
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

    new_perf = Performance(
        kind="solo",
        title=title,
        venue=venue,
        start=start_raw,
        duration_minutes=duration,
        artist=artist,
    )

    festival.add_performance(new_perf)
    save_festival(festival)
    print(f"Added: {new_perf.id}")


def cancel_performance_cli(festival, perf_id: str) -> None:
    cancelled_title = festival.cancel_performance(perf_id)
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
            cancel_performance_cli(festival, args[1])
        else:
            print_usage()

    except (ValueError, FileNotFoundError) as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()