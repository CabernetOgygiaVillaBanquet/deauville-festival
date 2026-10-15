from datetime import date
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from festival import load_festival

app = FastAPI(title="Deauville Festival du Rire API")


@app.get("/api/festival")
def get_festival() -> dict:
    festival = load_festival()
    return {
        "name": festival.name,
        "first_day": festival.first_day,
        "last_day": festival.last_day,
        "days": festival.days,
    }


@app.get("/api/venues")
def list_venues() -> list[dict]:
    festival = load_festival()
    return [v.to_dict() for v in festival.venues]


@app.get("/api/artists")
def list_artists() -> list[dict]:
    festival = load_festival()
    artists = [a.to_dict() for a in festival.artists]
    artists.sort(key=lambda a: a["slug"])
    return artists


@app.get("/api/artists/{slug}")
def get_artist(slug: str) -> dict:
    festival = load_festival()
    artist = festival.find_artist(slug)
    if not artist:
        raise HTTPException(status_code=404, detail=f"No artist '{slug}'.")

    # Collect and sort performances involving this artist
    involved_perfs = [
        p.to_view(festival.venues_map, festival.artists_map)
        for p in festival.performances
        if p.involves(slug)
    ]
    involved_perfs.sort(key=lambda p: p["start"])

    res = artist.to_dict()
    res["performances"] = involved_perfs
    return res


@app.get("/api/programme")
def get_programme(day: date | None = None, venue: str | None = None) -> list[dict]:
    festival = load_festival()

    if venue and venue not in festival.venues_map:
        raise HTTPException(status_code=404, detail=f"No venue '{venue}'.")

    matching = festival.performances
    if day:
        day_str = day.isoformat()
        matching = [p for p in matching if p.festival_day == day_str]
    if venue:
        matching = [p for p in matching if p.venue == venue]

    matching.sort(key=lambda p: p.start)
    return [p.to_view(festival.venues_map, festival.artists_map) for p in matching]


@app.get("/api/performances/{perf_id}")
def get_performance(perf_id: str) -> dict:
    festival = load_festival()
    perf = festival.find_performance(perf_id)
    if not perf:
        raise HTTPException(status_code=404, detail=f"No performance with ID '{perf_id}'.")
    return perf.to_view(festival.venues_map, festival.artists_map)


# Serve static web frontend
public_path = Path("web/public")
if public_path.exists():
    app.mount("/", StaticFiles(directory=str(public_path), html=True), name="static")