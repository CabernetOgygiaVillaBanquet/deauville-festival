import json
from pathlib import Path


def slugify(text: str) -> str:
    return text.lower().replace(" ", "-")


def main():
    data_path = Path("data/festival.json")
    with open(data_path, "r", encoding="utf-8") as f:
        festival = json.load(f)

    # Step 00 - Summary
    name = festival["name"]
    start_date = festival["first_day"]
    end_date = festival["last_day"]
    venues = festival["venues"]
    artists = festival["artists"]
    performances = festival["performances"]

    print(f"{name}")
    print(f"From {start_date} to {end_date}")
    print(f"{len(venues)} venues, {len(artists)} artists, {len(performances)} performances")
    print()

    # Step 01 - Question 1: Venues and total seats
    print("Venues:")
    total_seats = 0
    kiosque_slug = None
    for venue in venues:
        seats = venue.get("capacity", 0)
        total_seats += seats
        print(f"- {venue['name']}: {seats} seats ({venue.get('address', '')})")
        if venue["name"] == "Le Kiosque":
            kiosque_slug = slugify(venue["name"])
    print(f"Total: {total_seats} seats")
    print()

    # Step 01 - Question 2: Performances by kind
    kinds_count = {}
    for perf in performances:
        kind = perf.get("kind")
        kinds_count[kind] = kinds_count.get(kind, 0) + 1

    for kind, count in kinds_count.items():
        print(f"{kind}: {count}")
    print()

    # Step 01 - Question 3: Performances at Le Kiosque
    print("At Le Kiosque:")
    for perf in performances:
        if perf.get("venue") == kiosque_slug:
            print(f"- {perf['start']} {perf['title']}")
    print()

    # Step 01 - Question 4: Longest performance
    longest_perf = max(performances, key=lambda p: p.get("duration_minutes", 0))
    print(f"Longest: {longest_perf['title']} ({longest_perf['duration_minutes']} min)")
    print()

    # Step 01 - Question 5: Workshop registrations
    for perf in performances:
        if perf.get("kind") == "workshop":
            registered = len(perf.get("participants", []))
            max_reg = perf.get("max_participants", 0)
            day = perf["start"][:10]
            print(f"{perf['title']} on {day}: {registered}/{max_reg} registered")
    print()

    # Step 01 - Question 6: Artists on stage the most often
    stage_counts = {}
    for perf in performances:
        kind = perf.get("kind")
        if kind == "solo":
            artist = perf.get("artist")
            if artist:
                stage_counts[artist] = stage_counts.get(artist, 0) + 1
        elif kind == "lineup":
            host = perf.get("host")
            if host:
                stage_counts[host] = stage_counts.get(host, 0) + 1
            for act in perf.get("acts", []):
                stage_counts[act] = stage_counts.get(act, 0) + 1
        elif kind == "workshop":
            teacher = perf.get("teacher")
            if teacher:
                stage_counts[teacher] = stage_counts.get(teacher, 0) + 1

    if stage_counts:
        max_appearances = max(stage_counts.values())
        top_artists = [artist for artist, count in stage_counts.items() if count == max_appearances]
        print(f"On stage {max_appearances} times: {', '.join(top_artists)}")


if __name__ == "__main__":
    main()