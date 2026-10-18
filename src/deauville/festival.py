from datetime import date, datetime, timedelta
from typing import Any

from deauville.errors import ConflictError, InvalidValueError, NotFoundError
from deauville.models import (
    PERFORMANCE_CLASSES,
    Artist,
    Performance,
    Venue,
)


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
                f"Duration must be between 1 and 360 minutes "
                f"(got {new_perf.duration_minutes})."
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
                        f"{v_name} is busy with {ex.title} "
                        f"({ex_s:%Y-%m-%d %H:%M}-{ex_e:%H:%M})."
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

    def move_performance(
        self, perf_id: str, new_start: str, new_venue: str | None = None
    ) -> Performance:
        perf = self.find_performance(perf_id)
        if not perf:
            raise NotFoundError(f"No performance with ID '{perf_id}'.")

        venue_to_use = new_venue or perf.venue
        raw = perf.to_dict()
        raw["start"] = new_start
        raw["venue"] = venue_to_use

        cls = PERFORMANCE_CLASSES[perf.kind]
        raw_kwargs = {k: v for k, v in raw.items() if k != "kind"}
        updated_perf = cls(**raw_kwargs)

        self.check_rules(updated_perf, ignore_id=perf_id)

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

    def register_participant(
        self, perf_id: str, participant_name: str
    ) -> dict[str, Any]:
        perf = self.find_performance(perf_id)
        if not perf:
            raise NotFoundError(f"No performance with ID '{perf_id}'.")
        from deauville.models import Workshop

        if not isinstance(perf, Workshop):
            raise InvalidValueError(f"Performance '{perf.title}' is not a workshop.")

        venue_obj = self.venues_map.get(perf.venue)
        venue_cap = venue_obj.capacity if venue_obj else perf.max_participants
        perf.register(participant_name, venue_cap)
        return perf.to_view(self.venues_map, self.artists_map)

    def now_playing(self, moment: datetime) -> list[Performance]:
        current = [
            p for p in self._performances if p.start_datetime <= moment < p.end_datetime
        ]
        return sorted(current)

    def up_next(self, moment: datetime, limit: int = 3) -> list[Performance]:
        upcoming = [p for p in self._performances if p.start_datetime > moment]
        return sorted(upcoming)[:limit]

    def programme_for_day(
        self, day: date, venue_slug: str | None = None
    ) -> list[Performance]:
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Festival":
        venues = [Venue(**v) for v in data.get("venues", [])]
        artists = [Artist(**a) for a in data.get("artists", [])]
        performances: list[Performance] = []
        for item in data.get("performances", []):
            kind = item.get("kind", "")
            p_cls = PERFORMANCE_CLASSES.get(kind)
            if not p_cls:
                raise InvalidValueError(f"Unknown performance kind '{kind}'.")
            raw_kwargs = {k: v for k, v in item.items() if k != "kind"}
            performances.append(p_cls(**raw_kwargs))

        extra_fields = {
            k: v
            for k, v in data.items()
            if k
            not in {
                "name",
                "first_day",
                "last_day",
                "venues",
                "artists",
                "performances",
            }
        }

        return cls(
            name=data["name"],
            first_day=data["first_day"],
            last_day=data["last_day"],
            venues=venues,
            artists=artists,
            performances=performances,
            extra=extra_fields,
        )
