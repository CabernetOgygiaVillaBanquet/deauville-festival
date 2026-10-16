from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any
import unicodedata


# --- Custom Exception Hierarchy ---
class FestivalError(Exception):
    """Base exception for all festival domain errors."""
    status_code: int = 400


class NotFoundError(FestivalError):
    """Resource not found (HTTP 404)."""
    status_code: int = 404


class ConflictError(FestivalError):
    """Schedule conflict or duplication (HTTP 409)."""
    status_code: int = 409


class InvalidValueError(FestivalError):
    """Invalid input values (HTTP 422)."""
    status_code: int = 422


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
        pass

    @abstractmethod
    def involves(self, artist_slug: str) -> str | None:
        pass

    @abstractmethod
    def get_involved_artists(self) -> list[str]:
        pass

    @abstractmethod
    def summary(self, artists_map: dict[str, Artist]) -> str:
        pass

    @abstractmethod
    def get_capacity(self, venue_capacity: int) -> int:
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
        pass

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
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
            raise InvalidValueError("A solo show requires an artist.")
        if self.min_age is not None and not (0 <= self.min_age <= 18):
            raise InvalidValueError(f"Minimum age must be between 0 and 18 (got {self.min_age}).")

    def involves(self, artist_slug: str) -> str | None:
        return "solo" if self.artist == artist_slug else None

    def get_involved_artists(self) -> list[str]:
        return [self.artist]

    def summary(self, artists_map: dict[str, Artist]) -> str:
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
        self._acts = list(acts)
        super().__init__(
            title=title,
            venue=venue,
            start=start,
            duration_minutes=duration_minutes,
            description=description,
            **extra,
        )

    @property
    def acts(self) -> list[str]:
        return list(self._acts)

    def check_self_rules(self) -> None:
        if len(self._acts) < 2:
            raise InvalidValueError(f"A lineup requires at least 2 acts (got {len(self._acts)}).")
        if len(set(self._acts)) != len(self._acts):
            raise InvalidValueError("Each act in a lineup must be unique.")
        if self.host in self._acts:
            raise InvalidValueError(f"The host '{self.host}' cannot also be an act in the lineup.")

        n_acts = len(self._acts)
        min_duration = n_acts * 10 + (n_acts - 1) * 3
        if self.duration_minutes < min_duration:
            raise InvalidValueError(
                f"Lineup with {n_acts} acts requires at least {min_duration} minutes (got {self.duration_minutes})."
            )

    def involves(self, artist_slug: str) -> str | None:
        if self.host == artist_slug:
            return "host"
        if artist_slug in self._acts:
            return "act"
        return None

    def get_involved_artists(self) -> list[str]:
        return [self.host] + list(self._acts)

    def summary(self, artists_map: dict[str, Artist]) -> str:
        host_name = artists_map[self.host].name if self.host in artists_map else self.host
        act_names = [artists_map[a].name if a in artists_map else a for a in self._acts]
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
        self._participants = list(participants or [])
        super().__init__(
            title=title,
            venue=venue,
            start=start,
            duration_minutes=duration_minutes,
            description=description,
            **extra,
        )

    @property
    def participants(self) -> list[str]:
        return list(self._participants)

    def check_self_rules(self) -> None:
        if not self.teacher:
            raise InvalidValueError("A workshop requires a teacher.")
        if self.max_participants < 1:
            raise InvalidValueError(
                f"A workshop must have at least 1 place (got {self.max_participants})."
            )

    def register(self, name: str, venue_capacity: int) -> None:
        effective_capacity = self.get_capacity(venue_capacity)
        if len(self._participants) >= effective_capacity:
            raise ConflictError("Workshop is full.")
        if name in self._participants:
            raise ConflictError(f"Participant '{name}' is already registered.")
        self._participants.append(name)

    def involves(self, artist_slug: str) -> str | None:
        return "teacher" if self.teacher == artist_slug else None

    def get_involved_artists(self) -> list[str]:
        return [self.teacher]

    def get_capacity(self, venue_capacity: int) -> int:
        return min(self.max_participants, venue_capacity)

    def summary(self, artists_map: dict[str, Artist]) -> str:
        teacher_name = artists_map[self.teacher].name if self.teacher in artists_map else self.teacher
        taken = len(self._participants)
        return f"with {teacher_name}, {taken}/{self.max_participants} places taken"

    def populate_view_extras(self, data: dict[str, Any]) -> None:
        data["teacher"] = self.teacher
        data["max_participants"] = self.max_participants
        data["participants"] = self.participants
        data["places_left"] = max(0, self.max_participants - len(self._participants))

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
        self._venues = list(venues)
        self._artists = list(artists)
        self._performances = list(performances)
        self.extra = extra or {}

    @property
    def venues(self) -> list[Venue]:
        return list(self._venues)

    @property
    def artists(self) -> list[Artist]:
        return list(self._artists)

    @property
    def performances(self) -> list[Performance]:
        return list(self._performances)

    @property
    def venues_map(self) -> dict[str, Venue]:
        return {v.slug: v for v in self._venues}

    @property
    def artists_map(self) -> dict[str, Artist]:
        return {a.slug: a for a in self._artists}

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

    def add_artist(self, artist: Artist) -> None:
        if artist.slug in self.artists_map:
            raise ConflictError(f"Artist '{artist.slug}' already exists.")
        self._artists.append(artist)

    def check_rules(self, new_perf: Performance, ignore_id: str | None = None) -> None:
        if new_perf.venue not in self.venues_map:
            raise NotFoundError(f"No venue '{new_perf.venue}'.")

        for a_slug in new_perf.get_involved_artists():
            if a_slug not in self.artists_map:
                raise NotFoundError(f"No artist '{a_slug}'.")

        if not (1 <= new_perf.duration_minutes <= 360):
            raise InvalidValueError(
                f"Duration must be between 1 and 360 minutes (got {new_perf.duration_minutes})."
            )

        first_d = date.fromisoformat(self.first_day)
        last_d = date.fromisoformat(self.last_day)
        p_day = date.fromisoformat(new_perf.festival_day)
        if not (first_d <= p_day <= last_d):
            raise ConflictError(f"{p_day} is not a day of the festival.")

        new_s = new_perf.start_datetime
        new_e = new_perf.end_datetime
        gap = timedelta(minutes=30)
        v_name = self.venues_map[new_perf.venue].name
        new_involved = new_perf.get_involved_artists()

        for ex in self._performances:
            if ignore_id and ex.id == ignore_id:
                continue

            ex_s = ex.start_datetime
            ex_e = ex.end_datetime

            if ex.venue == new_perf.venue:
                if new_s < ex_e + gap and ex_s < new_e + gap:
                    raise ConflictError(
                        f"{v_name} is busy with {ex.title} ({ex_s:%Y-%m-%d %H:%M}-{ex_e:%H:%M})."
                    )

            ex_involved = ex.get_involved_artists()
            for a_slug in new_involved:
                if a_slug in ex_involved:
                    if new_s < ex_e + gap and ex_s < new_e + gap:
                        a_name = self.artists_map[a_slug].name
                        raise ConflictError(f"{a_name} is on stage in {ex.title}.")

    def add_performance(self, perf: Performance) -> None:
        self.check_rules(perf)
        self._performances.append(perf)

    def move_performance(self, perf_id: str, new_start: str, new_venue: str | None = None) -> Performance:
        perf = self.find_performance(perf_id)
        if not perf:
            raise NotFoundError(f"No performance with ID '{perf_id}'.")

        # Snapshot for atomic rollback
        venue_to_use = new_venue or perf.venue
        raw = perf.to_dict()
        raw["start"] = new_start
        raw["venue"] = venue_to_use

        cls = PERFORMANCE_CLASSES[perf.kind]
        raw_kwargs = {k: v for k, v in raw.items() if k != "kind"}
        updated_perf = cls(**raw_kwargs)

        self.check_rules(updated_perf, ignore_id=perf_id)

        # Replace in-place
        idx = self._performances.index(perf)
        self._performances[idx] = updated_perf
        return updated_perf

    def cancel_performance(self, perf_id: str) -> str:
        idx = None
        title = ""
        for i, p in enumerate(self._performances):
            if p.id == perf_id:
                idx = i
                title = p.title
                break
        if idx is None:
            raise NotFoundError(f"No performance with ID '{perf_id}'.")
        self._performances.pop(idx)
        return title

    def register_participant(self, perf_id: str, participant_name: str) -> dict[str, Any]:
        perf = self.find_performance(perf_id)
        if not perf:
            raise NotFoundError(f"No performance with ID '{perf_id}'.")
        if not isinstance(perf, Workshop):
            raise InvalidValueError(f"Performance '{perf.title}' is not a workshop.")

        venue_obj = self.venues_map.get(perf.venue)
        venue_cap = venue_obj.capacity if venue_obj else perf.max_participants
        perf.register(participant_name, venue_cap)
        return perf.to_view(self.venues_map, self.artists_map)

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
            "venues": [v.to_dict() for v in self._venues],
            "artists": [a.to_dict() for a in self._artists],
            "performances": [p.to_dict() for p in self._performances],
        }
        data.update(self.extra)
        return data


def load_festival(path: str = "data/festival.json") -> Festival:
    p = Path(path)
    if not p.exists():
        raise NotFoundError(f"Festival file '{path}' not found.")
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise InvalidValueError(f"Corrupted festival data file: {e}") from e

    venues = [Venue(**v) for v in data.get("venues", [])]
    artists = [Artist(**a) for a in data.get("artists", [])]

    performances: list[Performance] = []
    for item in data.get("performances", []):
        kind = item.get("kind", "")
        cls = PERFORMANCE_CLASSES.get(kind)
        if not cls:
            raise InvalidValueError(f"Unknown performance kind '{kind}'.")
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