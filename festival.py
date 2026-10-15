from dataclasses import dataclass, field
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


@dataclass
class Venue:
    name: str
    capacity: int
    address: str
    slug: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        name: str,
        capacity: int,
        address: str,
        slug: str = "",
        **extra: Any,
    ) -> None:
        self.name = name
        self.capacity = capacity
        self.address = address
        self.slug = slug or slugify(name)
        self.extra = extra

    def to_dict(self) -> dict[str, Any]:
        data = {
            "slug": self.slug,
            "name": self.name,
            "capacity": self.capacity,
            "address": self.address,
        }
        data.update(self.extra)
        return data


@dataclass
class Artist:
    name: str
    bio: str = ""
    slug: str = ""
    photo_url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        name: str,
        bio: str = "",
        slug: str = "",
        photo_url: str = "",
        **extra: Any,
    ) -> None:
        self.name = name
        self.bio = bio
        self.slug = slug or slugify(name)
        self.photo_url = photo_url or extra.get("photo_url", "")
        self.extra = extra

    def to_dict(self) -> dict[str, Any]:
        data = {
            "slug": self.slug,
            "name": self.name,
            "bio": self.bio,
        }
        if self.photo_url:
            data["photo_url"] = self.photo_url
        data.update(self.extra)
        return data


@dataclass
class Performance:
    kind: str
    title: str
    venue: str
    start: str
    duration_minutes: int
    description: str = ""
    artist: str | None = None
    min_age: int | None = None
    host: str | None = None
    acts: list[str] = field(default_factory=list)
    teacher: str | None = None
    max_participants: int | None = None
    participants: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        kind: str,
        title: str,
        venue: str,
        start: str,
        duration_minutes: int,
        description: str = "",
        artist: str | None = None,
        min_age: int | None = None,
        host: str | None = None,
        acts: list[str] | None = None,
        teacher: str | None = None,
        max_participants: int | None = None,
        participants: list[str] | None = None,
        **extra: Any,
    ) -> None:
        self.kind = kind
        self.title = title
        self.venue = venue
        self.start = start
        self.duration_minutes = duration_minutes
        self.description = description
        self.artist = artist
        self.min_age = min_age
        self.host = host
        self.acts = acts or []
        self.teacher = teacher
        self.max_participants = max_participants
        self.participants = participants or []
        self.extra = extra

    @property
    def start_datetime(self) -> datetime:
        return datetime.fromisoformat(self.start)

    @property
    def end_datetime(self) -> datetime:
        return self.start_datetime + timedelta(minutes=self.duration_minutes)

    @property
    def end(self) -> str:
        return self.end_datetime.strftime("%Y-%m-%dT%H:%M")

    @property
    def festival_day(self) -> str:
        """A festival day ends at 06:00: subtract 6 hours from start."""
        f_date = (self.start_datetime - timedelta(hours=6)).date()
        return f_date.isoformat()

    @property
    def id(self) -> str:
        time_compact = f"{self.start_datetime:%H%M}"
        return f"{self.venue}-{self.start_datetime:%Y-%m-%d}-{time_compact}"

    def involves(self, artist_slug: str) -> str | None:
        if self.kind == "solo" and self.artist == artist_slug:
            return "solo"
        if self.kind == "lineup":
            if self.host == artist_slug:
                return "host"
            if artist_slug in self.acts:
                return "act"
        if self.kind == "workshop" and self.teacher == artist_slug:
            return "teacher"
        return None

    def get_involved_artists(self) -> list[str]:
        if self.kind == "solo":
            return [self.artist] if self.artist else []
        if self.kind == "lineup":
            artists = []
            if self.host:
                artists.append(self.host)
            artists.extend(self.acts)
            return artists
        if self.kind == "workshop":
            return [self.teacher] if self.teacher else []
        return []

    def to_view(
        self,
        venues_map: dict[str, Venue],
        artists_map: dict[str, Artist],
    ) -> dict[str, Any]:
        venue_obj = venues_map.get(self.venue)
        v_name = venue_obj.name if venue_obj else self.venue
        v_cap = venue_obj.capacity if venue_obj else 0

        involved_slugs = self.get_involved_artists()
        artists_list = [
            {"slug": slug, "name": artists_map[slug].name if slug in artists_map else slug}
            for slug in involved_slugs
        ]

        data: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue,
            "venue_name": v_name,
            "start": self.start,
            "end": self.end,
            "duration_minutes": self.duration_minutes,
            "festival_day": self.festival_day,
            "description": self.description,
            "capacity": v_cap,
            "artists": artists_list,
        }

        if self.kind == "solo":
            artist_name = artists_map[self.artist].name if self.artist and self.artist in artists_map else self.artist
            data["artist"] = self.artist
            data["summary"] = f"by {artist_name}"
            if self.min_age is not None:
                data["min_age"] = self.min_age

        elif self.kind == "lineup":
            host_name = artists_map[self.host].name if self.host and self.host in artists_map else self.host
            act_names = [artists_map[a].name if a in artists_map else a for a in self.acts]
            acts_str = ", ".join(act_names)
            data["host"] = self.host
            data["acts"] = self.acts
            data["summary"] = f"hosted by {host_name}, with {acts_str}"

        elif self.kind == "workshop":
            teacher_name = artists_map[self.teacher].name if self.teacher and self.teacher in artists_map else self.teacher
            data["teacher"] = self.teacher
            data["max_participants"] = self.max_participants or 0
            data["participants"] = self.participants
            data["places_left"] = (self.max_participants or 0) - len(self.participants)
            data["summary"] = f"led by {teacher_name}"

        return data

    def to_dict(self) -> dict[str, Any]:
        raw: dict[str, Any] = {
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue,
            "start": self.start,
            "duration_minutes": self.duration_minutes,
            "description": self.description,
        }
        if self.kind == "solo":
            raw["artist"] = self.artist
            if self.min_age is not None:
                raw["min_age"] = self.min_age
        elif self.kind == "lineup":
            raw["host"] = self.host
            raw["acts"] = self.acts
        elif self.kind == "workshop":
            raw["teacher"] = self.teacher
            raw["max_participants"] = self.max_participants
            raw["participants"] = self.participants
        raw.update(self.extra)
        return raw


@dataclass
class Festival:
    name: str
    first_day: str
    last_day: str
    venues: list[Venue]
    artists: list[Artist]
    performances: list[Performance]
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def venues_map(self) -> dict[str, Venue]:
        return {v.slug: v for v in self.venues}

    @property
    def artists_map(self) -> dict[str, Artist]:
        return {a.slug: a for a in self.artists}

    @property
    def days(self) -> list[str]:
        first = date.fromisoformat(self.first_day)
        last = date.fromisoformat(self.last_day)
        day_list = []
        cur = first
        while cur <= last:
            day_list.append(cur.isoformat())
            cur += timedelta(days=1)
        return day_list

    def find_performance(self, perf_id: str) -> Performance | None:
        for p in self.performances:
            if p.id == perf_id:
                return p
        return None

    def find_artist(self, slug: str) -> Artist | None:
        return self.artists_map.get(slug)

    def find_venue(self, slug: str) -> Venue | None:
        return self.venues_map.get(slug)

    def check_rules(self, new_perf: Performance) -> None:
        if new_perf.venue not in self.venues_map:
            raise ValueError(f"Unknown venue '{new_perf.venue}'.")

        for a_slug in new_perf.get_involved_artists():
            if a_slug not in self.artists_map:
                raise ValueError(f"Unknown artist '{a_slug}'.")

        if not (1 <= new_perf.duration_minutes <= 360):
            raise ValueError(f"Duration must be between 1 and 360 minutes (got {new_perf.duration_minutes}).")

        first_d = date.fromisoformat(self.first_day)
        last_d = date.fromisoformat(self.last_day)
        p_day = date.fromisoformat(new_perf.festival_day)
        if not (first_d <= p_day <= last_d):
            raise ValueError(f"{p_day} is not a day of the festival.")

        new_s = new_perf.start_datetime
        new_e = new_perf.end_datetime
        gap = timedelta(minutes=30)
        v_name = self.venues_map[new_perf.venue].name
        new_involved = new_perf.get_involved_artists()

        for ex in self.performances:
            ex_s = ex.start_datetime
            ex_e = ex.end_datetime

            if ex.venue == new_perf.venue:
                if new_s < ex_e + gap and ex_s < new_e + gap:
                    raise ValueError(
                        f"{v_name} is busy with {ex.title} ({ex_s:%Y-%m-%d %H:%M}-{ex_e:%H:%M})."
                    )

            ex_involved = ex.get_involved_artists()
            for a_slug in new_involved:
                if a_slug in ex_involved:
                    if new_s < ex_e + gap and ex_s < new_e + gap:
                        a_name = self.artists_map[a_slug].name
                        raise ValueError(f"{a_name} is on stage in {ex.title}.")

    def add_performance(self, perf: Performance) -> None:
        self.check_rules(perf)
        self.performances.append(perf)

    def cancel_performance(self, perf_id: str) -> str:
        idx = None
        title = ""
        for i, p in enumerate(self.performances):
            if p.id == perf_id:
                idx = i
                title = p.title
                break
        if idx is None:
            raise ValueError(f"No performance with ID '{perf_id}'.")
        self.performances.pop(idx)
        return title

    def to_dict(self) -> dict[str, Any]:
        data = {
            "name": self.name,
            "first_day": self.first_day,
            "last_day": self.last_day,
            "venues": [v.to_dict() for v in self.venues],
            "artists": [a.to_dict() for a in self.artists],
            "performances": [p.to_dict() for p in self.performances],
        }
        data.update(self.extra)
        return data


def load_festival(path: str = "data/festival.json") -> Festival:
    """Load festival data into typed domain objects."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Festival file '{path}' not found.")
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupted festival data file: {e}") from e

    venues = [Venue(**v) for v in data.get("venues", [])]
    artists = [Artist(**a) for a in data.get("artists", [])]
    performances = [Performance(**perf) for perf in data.get("performances", [])]

    extra_fields = {
        k: v for k, v in data.items()
        if k not in {"name", "first_day", "last_day", "venues", "artists", "performances"}
    }

    return Festival(
        name=data["name"],
        first_day=data["first_day"],
        last_day=data["last_day"],
        venues=venues,
        artists=artists,
        performances=performances,
        extra=extra_fields,
    )


def save_festival(festival: Festival, path: str = "data/festival.json") -> None:
    """Persist domain objects back to JSON."""
    with open(Path(path), "w", encoding="utf-8") as f:
        json.dump(festival.to_dict(), f, ensure_ascii=False, indent=2)