from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
from typing import Any
import unicodedata

from deauville.errors import ConflictError, InvalidValueError


def slugify(text: str) -> str:
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