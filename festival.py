from abc import ABC, abstractmethod
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Artist):
            return False
        return self.slug == other.slug

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


class Performance(ABC):
    """Abstract base class for all festival performances."""

    kind: str = ""

    def __init__(
        self,
        title: str,
        venue: str,
        start: str,
        duration_minutes: int,
        description: str = "",
        **extra: Any,
    ) -> None:
        self.title = title
        self.venue = venue
        self.start = start
        self.duration_minutes = duration_minutes
        self.description = description
        self.extra = extra
        self.check_self_rules()

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

    def __lt__(self, other: "Performance") -> bool:
        if self.start_datetime != other.start_datetime:
            return self.start_datetime < other.start_datetime
        return self.venue < other.venue

    @abstractmethod
    def check_self_rules(self) -> None:
        """Subclass specific constraints from the brief."""
        pass

    @abstractmethod
    def involves(self, artist_slug: str) -> str | None:
        """Return the role if the artist is involved, else None."""
        pass

    @abstractmethod
    def get_involved_artists(self) -> list[str]:
        """Return all artist slugs on stage in any role."""
        pass

    @abstractmethod
    def summary(self, artists_map: dict[str, Artist]) -> str:
        """Formatted summary string according to API.md."""
        pass

    @abstractmethod
    def get_capacity(self, venue_capacity: int) -> int:
        """Calculate effective capacity for this performance."""
        pass

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
            "capacity": self.get_capacity(v_cap),
            "summary": self.summary(artists_map),
            "artists": artists_list,
        }
        self.populate_view_extras(data)
        return data

    @abstractmethod
    def populate_view_extras(self, data: dict[str, Any]) -> None:
        """Add subclass-specific fields to the view payload."""
        pass

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize back to raw JSON format."""
        pass


class SoloShow(Performance):
    kind = "solo"

    def __init__(
        self,
        title: str,
        venue: str,
        start: str,
        duration_minutes: int,
        artist: str,
        min_age: int | None = None,
        description: str = "",
        **extra: Any,
    ) -> None:
        self.artist = artist
        self.min_age = min_age
        super().__init__(
            title=title,
            venue=venue,
            start=start,
            duration_minutes=duration_minutes,
            description=description,
            **extra,
        )

    def check_self_rules(self) -> None:
        if not self.artist:
            raise ValueError("A solo show requires an artist.")
        if self.min_age is not None and not (0 <= self.min_age <= 18):
            raise ValueError(f"Minimum age must be between 0 and 18 (got {self.min_age}).")

    def involves(self, artist_slug: str) -> str | None:
        return "solo" if self.artist == artist_slug else None

    def get_involved_artists(self) -> list[str]:
        return [self.artist]

    def summary(self, artists_map: dict[str, Artist]) -> str:
        # Check if matching exact sample: "Léa Fontaine"
        artist_obj = artists_map.get(self.artist)
        return artist_obj.name if artist_obj else self.artist

    def get_capacity(self, venue_capacity: int) -> int:
        return venue_capacity

    def populate_view_extras(self, data: dict[str, Any]) -> None:
        data["artist"] = self.artist
        if self.min_age is not None:
            data["min_age"] = self.min_age

    def to_dict(self) -> dict[str, Any]:
        raw: dict[str, Any] = {
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue,
            "start": self.start,
            "duration_minutes": self.duration_minutes,
            "description": self.description,
            "artist": self.artist,
        }
        if self.min_age is not None:
            raw["min_age"] = self.min_age
        raw.update(self.extra)
        return raw


class Lineup(Performance):
    kind = "lineup"

    def __init__(
        self,
        title: str,
        venue: str,
        start: str,
        duration_minutes: int,
        host: str,
        acts: list[str],
        description: str = "",
        **extra: Any,
    ) -> None:
        self.host = host
        self.acts = list(acts)
        super().__init__(
            title=title,
            venue=venue,
            start=start,
            duration_minutes=duration_minutes,
            description=description,
            **extra,
        )

    def check_self_rules(self) -> None:
        if len(self.acts) < 2:
            raise ValueError(f"A lineup requires at least 2 acts (got {len(self.acts)}).")
        if len(set(self.acts)) != len(self.acts):
            raise ValueError("Each act in a lineup must be unique.")
        if self.host in self.acts:
            raise ValueError(f"The host '{self.host}' cannot also be an act in the lineup.")

        # Rule: 10 minutes per act + 3 minutes for host between every 2 acts[cite: 1]
        n_acts = len(self.acts)
        min_duration = n_acts * 10 + (n_acts - 1) * 3
        if self.duration_minutes < min_duration:
            raise ValueError(
                f"Lineup with {n_acts} acts requires at least {min_duration} minutes (got {self.duration_minutes}).[cite: 1]"
            )

    def involves(self, artist_slug: str) -> str | None:
        if self.host == artist_slug:
            return "host"
        if artist_slug in self.acts:
            return "act"
        return None

    def get_involved_artists(self) -> list[str]:
        return [self.host] + list(self.acts)

    def summary(self, artists_map: dict[str, Artist]) -> str:
        host_name = artists_map[self.host].name if self.host in artists_map else self.host
        act_names = [artists_map[a].name if a in artists_map else a for a in self.acts]
        return f"hosted by {host_name}, with {', '.join(act_names)}"

    def get_capacity(self, venue_capacity: int) -> int:
        return venue_capacity

    def populate_view_extras(self, data: dict[str, Any]) -> None:
        data["host"] = self.host
        data["acts"] = self.acts

    def to_dict(self) -> dict[str, Any]:
        raw: dict[str, Any] = {
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue,
            "start": self.start,
            "duration_minutes": self.duration_minutes,
            "description": self.description,
            "host": self.host,
            "acts": self.acts,
        }
        raw.update(self.extra)
        return raw


class Workshop(Performance):
    kind = "workshop"

    def __init__(
        self,
        title: str,
        venue: str,
        start: str,
        duration_minutes: int,
        teacher: str,
        max_participants: int,
        participants: list[str] | None = None,
        description: str = "",
        **extra: Any,
    ) -> None:
        self.teacher = teacher
        self.max_participants = max_participants
        self.participants = list(participants or [])
        super().__init__(
            title=title,
            venue=venue,
            start=start,
            duration_minutes=duration_minutes,
            description=description,
            **extra,
        )

    def check_self_rules(self) -> None:
        if not self.teacher:
            raise ValueError("A workshop requires a teacher.")
        if self.max_participants < 1:
            raise ValueError(
                f"A workshop must have at least 1 place (got {self.max_participants}).[cite: 1]"
            )

    def involves(self, artist_slug: str) -> str | None:
        return "teacher" if self.teacher == artist_slug else None

    def get_involved_artists(self) -> list[str]:
        return [self.teacher]

    def get_capacity(self, venue_capacity: int) -> int:
        # places = min(max_participants, venue capacity)[cite: 1]
        return min(self.max_participants, venue_capacity)

    def summary(self, artists_map: dict[str, Artist]) -> str:
        teacher_name = artists_map[self.teacher].name if self.teacher in artists_map else self.teacher
        taken = len(self.participants)
        return f"with {teacher_name}, {taken}/{self.max_participants} places taken"

    def populate_view_extras(self, data: dict[str, Any]) -> None:
        data["teacher"] = self.teacher
        data["max_participants"] = self.max_participants
        data["participants"] = self.participants
        data["places_left"] = max(0, self.max_participants - len(self.participants))

    def to_dict(self) -> dict[str, Any]:
        raw: dict[str, Any] = {
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue,
            "start": self.start,
            "duration_minutes": self.duration_minutes,
            "description": self.description,
            "teacher": self.teacher,
            "max_participants": self.max_participants,
            "participants": self.participants,
        }
        raw.update(self.extra)
        return raw


# Mapping for polymorphic instantiation without if/elif[cite: 1]
PERFORMANCE_CLASSES: dict[str, type[Performance]] = {
    "solo": SoloShow,
    "lineup": Lineup,
    "workshop": Workshop,
}


class Festival:
    def __init__(
        self,
        name: str,
        first_day: str,
        last_day: str,
        venues: list[Venue],
        artists: list[Artist],
        performances: list[Performance],
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.first_day = first_day
        self.last_day = last_day
        self.venues = venues
        self.artists = artists
        self._performances = list(performances)
        self.extra = extra or {}

    @property
    def performances(self) -> list[Performance]:
        return list(self._performances)

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
        for p in self._performances:
            if p.id == perf_id:
                return p
        return None

    def find_artist(self, slug: str) -> Artist | None:
        return self.artists_map.get(slug)

    def find_venue(self, slug: str) -> Venue | None:
        return self.venues_map.get(slug)

    def check_rules(self, new_perf: Performance) -> None:
        if new_perf.venue not in self.venues_map:
            raise ValueError(f"Unknown venue '{new_perf.venue}'.[cite: 1]")

        for a_slug in new_perf.get_involved_artists():
            if a_slug not in self.artists_map:
                raise ValueError(f"Unknown artist '{a_slug}'.[cite: 1]")

        if not (1 <= new_perf.duration_minutes <= 360):
            raise ValueError(
                f"Duration must be between 1 and 360 minutes (got {new_perf.duration_minutes}).[cite: 1]"
            )

        first_d = date.fromisoformat(self.first_day)
        last_d = date.fromisoformat(self.last_day)
        p_day = date.fromisoformat(new_perf.festival_day)
        if not (first_d <= p_day <= last_d):
            raise ValueError(f"{p_day} is not a day of the festival.[cite: 1]")

        new_s = new_perf.start_datetime
        new_e = new_perf.end_datetime
        gap = timedelta(minutes=30)
        v_name = self.venues_map[new_perf.venue].name
        new_involved = new_perf.get_involved_artists()

        for ex in self._performances:
            ex_s = ex.start_datetime
            ex_e = ex.end_datetime

            if ex.venue == new_perf.venue:
                if new_s < ex_e + gap and ex_s < new_e + gap:
                    raise ValueError(
                        f"{v_name} is busy with {ex.title} ({ex_s:%Y-%m-%d %H:%M}-{ex_e:%H:%M}).[cite: 1]"
                    )

            ex_involved = ex.get_involved_artists()
            for a_slug in new_involved:
                if a_slug in ex_involved:
                    if new_s < ex_e + gap and ex_s < new_e + gap:
                        a_name = self.artists_map[a_slug].name
                        raise ValueError(f"{a_name} is on stage in {ex.title}.[cite: 1]")

    def add_performance(self, perf: Performance) -> None:
        self.check_rules(perf)
        self._performances.append(perf)

    def cancel_performance(self, perf_id: str) -> str:
        idx = None
        title = ""
        for i, p in enumerate(self._performances):
            if p.id == perf_id:
                idx = i
                title = p.title
                break
        if idx is None:
            raise ValueError(f"No performance with ID '{perf_id}'.")
        self._performances.pop(idx)
        return title

    def now_playing(self, moment: datetime) -> list[Performance]:
        current = [p for p in self._performances if p.start_datetime <= moment < p.end_datetime]
        return sorted(current)

    def up_next(self, moment: datetime, limit: int = 3) -> list[Performance]:
        upcoming = [p for p in self._performances if p.start_datetime > moment]
        return sorted(upcoming)[:limit]

    def programme_for_day(self, day: date, venue_slug: str | None = None) -> list[Performance]:
        day_str = day.isoformat()
        perfs = [p for p in self._performances if p.festival_day == day_str]
        if venue_slug:
            perfs = [p for p in perfs if p.venue == venue_slug]
        return sorted(perfs)

    def artist_performances(self, artist_slug: str) -> list[tuple[Performance, str]]:
        appearances = []
        for p in self._performances:
            role = p.involves(artist_slug)
            if role:
                appearances.append((p, role))
        appearances.sort(key=lambda item: item[0])
        return appearances

    def to_dict(self) -> dict[str, Any]:
        data = {
            "name": self.name,
            "first_day": self.first_day,
            "last_day": self.last_day,
            "venues": [v.to_dict() for v in self.venues],
            "artists": [a.to_dict() for a in self.artists],
            "performances": [p.to_dict() for p in self._performances],
        }
        data.update(self.extra)
        return data


def load_festival(path: str = "data/festival.json") -> Festival:
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

    # Instantiate via polymorphism without 'if kind =='[cite: 1]
    performances: list[Performance] = []
    for item in data.get("performances", []):
        kind = item.get("kind", "")
        cls = PERFORMANCE_CLASSES.get(kind)
        if not cls:
            raise ValueError(f"Unknown performance kind '{kind}'.")
        raw_kwargs = {k: v for k, v in item.items() if k != "kind"}
        performances.append(cls(**raw_kwargs))

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
    with open(Path(path), "w", encoding="utf-8") as f:
        json.dump(festival.to_dict(), f, ensure_ascii=False, indent=2)