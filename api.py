from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from festival import (
    get_artists_list,
    get_festival_days,
    get_venues_list,
    load_festival,
)

app = FastAPI(title="Deauville Festival du Rire API")


@app.get("/api/festival")
def get_festival() -> dict:
    data = load_festival()
    return {
        "name": data["name"],
        "first_day": data["first_day"],
        "last_day": data["last_day"],
        "days": get_festival_days(data),
    }


@app.get("/api/venues")
def list_venues() -> list[dict]:
    data = load_festival()
    return get_venues_list(data)


@app.get("/api/artists")
def list_artists() -> list[dict]:
    data = load_festival()
    return get_artists_list(data)


# Serve static web frontend at the root (must be mounted after routes)
public_path = Path("web/public")
if public_path.exists():
    app.mount("/", StaticFiles(directory=str(public_path), html=True), name="static")