import json
from pathlib import Path


def slugify_venue(name: str) -> str:
    """Slugify venue name handling French accents."""
    return (
        name.lower()
        .replace("é", "e")
        .replace("â", "a")
        .replace(" ", "-")
    )


def main():
    data_path = Path("data/festival.json")
    with open(data_path, "r", encoding="utf-8") as f:
        festival = json.load(f)

    venues = festival["venues"]
    performances = festival["performances"]

    # 1. Build venue slug -> display name mapping
    venue_names = {slugify_venue(v["name"]): v["name"] for v in venues}

    # 2. Extract and sort unique days present in the performances
    # Using a set to collect all unique dates from the start string (YYYY-MM-DD)
    days_set = {perf["start"][:10] for perf in performances}
    available_days = sorted(days_set)
    days_str = ", ".join(available_days)

    # 3. Prompt user until valid day is given
    while True:
        user_input = input("Day (YYYY-MM-DD): ").strip()
        if user_input in available_days:
            selected_day = user_input
            break
        print(f"No performance on '{user_input}'. Days: {days_str}")

    # 4. Print the programme for the selected day
    print(f"Programme for {selected_day}:")
    day_performances = [
        perf for perf in performances if perf["start"][:10] == selected_day
    ]
    # Sort chronologically by start time
    day_performances.sort(key=lambda p: p["start"])

    for perf in day_performances:
        time_str = perf["start"][11:16]
        venue_display = venue_names.get(perf["venue"], perf["venue"])
        title = perf["title"]
        kind = perf["kind"]
        print(f"{time_str} | {venue_display} | {title} ({kind})")


if __name__ == "__main__":
    main()