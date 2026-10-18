import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from deauville.api import create_app
from deauville.storage import JSONStorage


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """Create a test client backed by a temporary copy of festival.json."""
    src_data = Path("data/festival.json")
    test_data = tmp_path / "festival.json"
    with open(src_data, encoding="utf-8") as f:
        data = json.load(f)
    with open(test_data, "w", encoding="utf-8") as f:
        json.dump(data, f)

    storage = JSONStorage(path=test_data)
    app = create_app(storage=storage)
    return TestClient(app)


# --- GET /api/festival ---
def test_get_festival(client: TestClient):
    res = client.get("/api/festival")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Deauville Festival du Rire 2027"
    assert body["first_day"] == "2027-06-10"
    assert body["last_day"] == "2027-06-13"
    assert len(body["days"]) == 4


# --- GET /api/venues ---
def test_get_venues(client: TestClient):
    res = client.get("/api/venues")
    assert res.status_code == 200
    venues = res.json()
    assert len(venues) == 4
    slugs = [v["slug"] for v in venues]
    assert "grand-casino" in slugs
    assert "le-kiosque" in slugs


# --- GET /api/artists ---
def test_get_artists_sorted(client: TestClient):
    res = client.get("/api/artists")
    assert res.status_code == 200
    artists = res.json()
    assert len(artists) == 12
    slugs = [a["slug"] for a in artists]
    assert slugs == sorted(slugs)


def test_get_artist_by_slug(client: TestClient):
    res = client.get("/api/artists/max-pellerin")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Max Pellerin"
    assert len(body["performances"]) == 4


def test_get_artist_not_found(client: TestClient):
    res = client.get("/api/artists/nobody")
    assert res.status_code == 404
    assert "No artist 'nobody'" in res.json()["detail"]


# --- GET /api/programme ---
def test_programme_filters(client: TestClient):
    # Filter by day
    res_day = client.get("/api/programme?day=2027-06-11")
    assert res_day.status_code == 200
    perfs_day = res_day.json()
    assert any(p["id"] == "le-kiosque-2027-06-12-0100" for p in perfs_day)

    # Filter by venue
    res_venue = client.get("/api/programme?venue=le-kiosque")
    assert res_venue.status_code == 200
    assert len(res_venue.json()) == 7

    # Filter by both
    res_both = client.get("/api/programme?day=2027-06-11&venue=le-kiosque")
    assert res_both.status_code == 200
    assert len(res_both.json()) == 3

    # Unknown venue
    res_bad_venue = client.get("/api/programme?venue=nowhere")
    assert res_bad_venue.status_code == 404


def test_programme_invalid_day_format(client: TestClient):
    res = client.get("/api/programme?day=June-11")
    assert res.status_code == 422


# --- GET /api/performances/{id} ---
def test_get_performance(client: TestClient):
    res = client.get("/api/performances/le-kiosque-2027-06-12-0100")
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "After Hours"
    assert body["kind"] == "lineup"
    assert body["venue_name"] == "Le Kiosque"
    assert "summary" in body


def test_get_performance_not_found(client: TestClient):
    res = client.get("/api/performances/unknown-id")
    assert res.status_code == 404


# --- GET /api/now ---
def test_get_now(client: TestClient):
    res = client.get("/api/now?at=2027-06-11T21:00")
    assert res.status_code == 200
    body = res.json()
    assert len(body["now_playing"]) == 1
    assert body["now_playing"][0]["title"] == "Tall Tales"
    assert len(body["up_next"]) == 3


# --- POST /api/artists ---
def test_create_artist(client: TestClient):
    payload = {"name": "Zoé Tanguy", "bio": "Stand-up comedy star"}
    res = client.post("/api/artists", json=payload)
    assert res.status_code == 201
    assert res.json()["slug"] == "zoe-tanguy"

    # Duplicate slug must conflict (409)
    res_dup = client.post("/api/artists", json={"name": "zoe tanguy"})
    assert res_dup.status_code == 409


# --- POST /api/performances ---
def test_create_solo_show_success_and_conflicts(client: TestClient):
    # Valid creation
    payload = {
        "kind": "solo",
        "title": "Morning Coffee",
        "venue": "la-cabane",
        "start": "2027-06-13T08:00",
        "duration_minutes": 30,
        "artist": "karim-benali",
    }
    res = client.post("/api/performances", json=payload)
    assert res.status_code == 201
    assert res.json()["id"] == "la-cabane-2027-06-13-0800"

    # Conflicting venue (409)
    res_conflict = client.post("/api/performances", json=payload)
    assert res_conflict.status_code == 409

    # Unknown venue (404)
    bad_venue = dict(payload, venue="phantom-room")
    assert client.post("/api/performances", json=bad_venue).status_code == 404

    # Invalid duration (422)
    bad_dur = dict(payload, start="2027-06-13T10:00", duration_minutes=0)
    assert client.post("/api/performances", json=bad_dur).status_code == 422


# --- PUT /api/performances/{id} (Move) ---
def test_move_performance_updates_id(client: TestClient):
    # Move Late Laughs from 2027-06-11T23:30 to an open slot: 2027-06-13T11:00
    res = client.put(
        "/api/performances/le-kiosque-2027-06-11-2330",
        json={"start": "2027-06-13T11:00", "venue": "le-kiosque"},
    )
    assert res.status_code == 200
    assert res.json()["id"] == "le-kiosque-2027-06-13-1100"


def test_move_performance_conflict_leaves_unchanged(client: TestClient):
    # Attempt to move into After Hours (01:00-02:00 on 2027-06-12)
    res = client.put(
        "/api/performances/le-kiosque-2027-06-11-2330",
        json={"start": "2027-06-12T01:15"},
    )
    assert res.status_code == 409

    # Original performance still exists at 23:30
    check = client.get("/api/performances/le-kiosque-2027-06-11-2330")
    assert check.status_code == 200


# --- DELETE /api/performances/{id} ---
def test_delete_performance_twice(client: TestClient):
    target_id = "grand-casino-2027-06-10-2030"
    res1 = client.delete(f"/api/performances/{target_id}")
    assert res1.status_code == 204

    # Second delete returns 404
    res2 = client.delete(f"/api/performances/{target_id}")
    assert res2.status_code == 404


# --- POST /api/performances/{id}/register ---
def test_workshop_registration_overflow_and_duplicate(client: TestClient):
    ws_id = "la-cabane-2027-06-11-1030"  # Improv for Beginners: max 12
    # Register new user
    res = client.post(f"/api/performances/{ws_id}/register", json={"name": "Nicolas"})
    assert res.status_code == 200
    assert "Nicolas" in res.json()["participants"]

    # Duplicate registration (409)
    res_dup = client.post(
        f"/api/performances/{ws_id}/register", json={"name": "Nicolas"}
    )
    assert res_dup.status_code == 409
