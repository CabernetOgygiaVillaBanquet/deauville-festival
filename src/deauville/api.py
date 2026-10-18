from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from deauville.errors import FestivalError, NotFoundError
from deauville.models import (
    PERFORMANCE_CLASSES,
    Artist,
)
from deauville.storage import JSONStorage, Storage


def create_app(storage: Storage | None = None) -> FastAPI:
    storage = storage or JSONStorage()
    app = FastAPI(title="Deauville Festival du Rire API")

    @app.exception_handler(FestivalError)
    async def festival_error_handler(request: Request, exc: FestivalError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc)},
        )

    class ArtistCreate(BaseModel):
        name: str = Field(..., min_length=1)
        bio: str = ""
        photo_url: str = ""

    class PerformanceCreate(BaseModel):
        kind: Literal["solo", "lineup", "workshop"]
        title: str = Field(..., min_length=1)
        venue: str
        start: str
        duration_minutes: int
        description: str = ""
        artist: str | None = None
        min_age: int | None = None
        host: str | None = None
        acts: list[str] | None = None
        teacher: str | None = None
        max_participants: int | None = None

    class PerformanceMove(BaseModel):
        start: str
        venue: str | None = None

    class RegisterParticipant(BaseModel):
        name: str = Field(..., min_length=1)

    @app.get("/api/festival")
    def get_festival() -> dict:
        festival = storage.load()
        return {
            "name": festival.name,
            "first_day": festival.first_day,
            "last_day": festival.last_day,
            "days": festival.days,
        }

    @app.get("/api/venues")
    def list_venues() -> list[dict]:
        festival = storage.load()
        return [v.to_dict() for v in festival.venues]

    @app.get("/api/artists")
    def list_artists() -> list[dict]:
        festival = storage.load()
        artists = [a.to_dict() for a in festival.artists]
        artists.sort(key=lambda a: a["slug"])
        return artists

    @app.get("/api/artists/{slug}")
    def get_artist(slug: str) -> dict:
        festival = storage.load()
        artist = festival.find_artist(slug)
        if not artist:
            raise NotFoundError(f"No artist '{slug}'.")

        appearances = festival.artist_performances(slug)
        res = artist.to_dict()
        res["performances"] = [
            p.to_view(festival.venues_map, festival.artists_map) for p, _ in appearances
        ]
        return res

    @app.get("/api/programme")
    def get_programme(day: date | None = None, venue: str | None = None) -> list[dict]:
        festival = storage.load()

        if venue and venue not in festival.venues_map:
            raise NotFoundError(f"No venue '{venue}'.")

        if day:
            perfs = festival.programme_for_day(day, venue_slug=venue)
        else:
            perfs = festival.performances
            if venue:
                perfs = [p for p in perfs if p.venue == venue]
            perfs = sorted(perfs)

        return [p.to_view(festival.venues_map, festival.artists_map) for p in perfs]

    @app.get("/api/performances/{perf_id}")
    def get_performance(perf_id: str) -> dict:
        festival = storage.load()
        perf = festival.find_performance(perf_id)
        if not perf:
            raise NotFoundError(f"No performance with ID '{perf_id}'.")
        return perf.to_view(festival.venues_map, festival.artists_map)

    @app.get("/api/now")
    def get_now(at: datetime | None = None) -> dict:
        festival = storage.load()
        moment = at or datetime.now()
        now_playing = festival.now_playing(moment)
        up_next = festival.up_next(moment, limit=3)
        return {
            "at": moment.strftime("%Y-%m-%dT%H:%M"),
            "now_playing": [p.to_view(festival.venues_map, festival.artists_map) for p in now_playing],
            "up_next": [p.to_view(festival.venues_map, festival.artists_map) for p in up_next],
        }

    @app.post("/api/artists", status_code=status.HTTP_201_CREATED)
    def create_artist(data: ArtistCreate) -> dict:
        festival = storage.load()
        artist = Artist(name=data.name, bio=data.bio, photo_url=data.photo_url)
        festival.add_artist(artist)
        storage.save(festival)
        return artist.to_dict()

    @app.post("/api/performances", status_code=status.HTTP_201_CREATED)
    def create_performance(data: PerformanceCreate) -> dict:
        festival = storage.load()
        cls = PERFORMANCE_CLASSES[data.kind]

        raw_kwargs: dict[str, Any] = {
            "title": data.title,
            "venue": data.venue,
            "start": data.start,
            "duration_minutes": data.duration_minutes,
            "description": data.description,
        }
        if data.kind == "solo":
            raw_kwargs["artist"] = data.artist
            raw_kwargs["min_age"] = data.min_age
        elif data.kind == "lineup":
            raw_kwargs["host"] = data.host
            raw_kwargs["acts"] = data.acts or []
        elif data.kind == "workshop":
            raw_kwargs["teacher"] = data.teacher
            raw_kwargs["max_participants"] = data.max_participants or 0

        new_perf = cls(**raw_kwargs)
        festival.add_performance(new_perf)
        storage.save(festival)
        return new_perf.to_view(festival.venues_map, festival.artists_map)

    @app.put("/api/performances/{perf_id}")
    def move_performance(perf_id: str, data: PerformanceMove) -> dict:
        festival = storage.load()
        updated = festival.move_performance(perf_id, new_start=data.start, new_venue=data.venue)
        storage.save(festival)
        return updated.to_view(festival.venues_map, festival.artists_map)

    @app.delete("/api/performances/{perf_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_performance(perf_id: str) -> Response:
        festival = storage.load()
        festival.cancel_performance(perf_id)
        storage.save(festival)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/api/performances/{perf_id}/register")
    def register_for_workshop(perf_id: str, data: RegisterParticipant) -> dict:
        festival = storage.load()
        view = festival.register_participant(perf_id, data.name)
        storage.save(festival)
        return view

    admin_path = Path("web/admin")
    if admin_path.exists():
        app.mount("/admin", StaticFiles(directory=str(admin_path), html=True), name="admin")

    public_path = Path("web/public")
    if public_path.exists():
        app.mount("/", StaticFiles(directory=str(public_path), html=True), name="static")

    return app


app = create_app()