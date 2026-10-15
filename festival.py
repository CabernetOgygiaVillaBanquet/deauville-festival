from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any
import unicodedata


def slugify(text: str) -> str:
    """Normalize text into an ASCII URL slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def load_festival(path: str = "data/festival.json") -> dict[str, Any]:
    """Load festival data from JSON file with validation."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Festival file '{path}' not found.")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupted festival data file: {e}") from e


def save_festival(festival: dict[str, Any], path: str = "data/festival.json") -> None:
    """Persist festival data to JSON file."""
    with open(Path(path), "w", encoding="utf-8") as f:
        json.dump(festival, f, ensure_ascii=False, indent=2)


def get_venues_list(festival: dict[str, Any]) -> list[dict[str, Any]]:
    """Return venues in original order, ensuring slug, name, capacity, address."""
    result = []
    for v in festival["venues"]:
        result.append({
            "slug": v.get("slug") or slugify(v["name"]),
            "name": v["name"],
            "capacity": v.get("capacity", 0),
            "address": v.get("address", "")
        })
    return result


def get_venues_map(festival: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map venue slug -> venue dict."""
    return {v["slug"]: v for v in get_venues_list(festival)}


def get_artists_list(festival: dict[str, Any]) -> list[dict[str, Any]]:
    """Return artists sorted alphabetically by slug, each with slug."""
    result = []
    for a in festival["artists"]:
        slug = a.get("slug") or slugify(a["name"])
        artist_obj = dict(a)
        artist_obj["slug"] = slug
        result.append(artist_obj)
    result.sort(key=lambda x: x["slug"])
    return result


def get_artists_map(festival: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map artist slug -> artist dict."""
    return {a["slug"]: a for a in get_artists_list(festival)}


def get_festival_days(festival: dict[str, Any]) -> list[str]:
    """Return list of ISO dates (YYYY-MM-DD) from first_day to last_day inclusive."""
    first = date.fromisoformat(festival["first_day"])
    last = date.fromisoformat(festival["last_day"])
    days = []
    current = first
    while current <= last:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def start_of(perf: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(perf["start"])


def end_of(perf: dict[str, Any]) -> datetime:
    return start_of(perf) + timedelta(minutes=perf["duration_minutes"])


def festival_day_of(perf: dict[str, Any]) -> date:
    return (start_of(perf) - timedelta(hours=6)).date()


def performance_id(perf: dict[str, Any]) -> str:
    s = start_of(perf)
    time_compact = f"{s:%H%M}"
    return f"{perf['venue']}-{s:%Y-%m-%d}-{time_compact}"


def get_involved_artists(perf: dict[str, Any]) -> list[str]:
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
    gap = timedelta(minutes=gap_minutes)
    return s1 < e2 + gap and s2 < e1 + gap


def check_performance_rules(festival: dict[str, Any], new_perf: dict[str, Any]) -> None:
    venues_map = get_venues_map(festival)
    artists_map = get_artists_map(festival)

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

        if existing["venue"] == venue_slug:
            if overlaps_with_gap(new_s, new_e, ex_s, ex_e, gap_minutes=30):
                raise ValueError(
                    f"{venue_name} is busy with {existing['title']} ({ex_s:%Y-%m-%d %H:%M}-{ex_e:%H:%M})."
                )

        ex_involved = get_involved_artists(existing)
        for a_slug in involved:
            if a_slug in ex_involved:
                if overlaps_with_gap(new_s, new_e, ex_s, ex_e, gap_minutes=30):
                    a_name = artists_map[a_slug]["name"]
                    raise ValueError(f"{a_name} is on stage in {existing['title']}.")