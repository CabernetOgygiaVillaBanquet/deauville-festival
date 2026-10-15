from datetime import datetime
import pytest

from festival import Artist, Festival, Performance, Venue


@pytest.fixture
def festival() -> Festival:
    """Provide a fresh minimal festival instance for testing rules."""
    venues = [
        Venue(name="Le Kiosque", capacity=120, address="Promenade", slug="le-kiosque"),
        Venue(name="La Cabane", capacity=40, address="Beach", slug="la-cabane"),
    ]
    artists = [
        Artist(name="Max Pellerin", slug="max-pellerin"),
        Artist(name="Karim Benali", slug="karim-benali"),
        Artist(name="Nora Lebrun", slug="nora-lebrun"),
    ]
    performances = [
        Performance(
            kind="solo",
            title="Late Laughs",
            venue="le-kiosque",
            start="2027-06-11T23:30",
            duration_minutes=60,
            artist="max-pellerin",
        ),
        Performance(
            kind="lineup",
            title="After Hours",
            venue="le-kiosque",
            start="2027-06-12T01:00",
            duration_minutes=60,
            host="karim-benali",
            acts=["nora-lebrun"],
        ),
    ]
    return Festival(
        name="Deauville Festival du Rire 2027",
        first_day="2027-06-10",
        last_day="2027-06-13",
        venues=venues,
        artists=artists,
        performances=performances,
    )


def test_festival_day_midnight_cutoff(festival: Festival):
    """Shows at 01:00 belong to the festival day of the previous calendar day."""
    p = festival.find_performance("le-kiosque-2027-06-12-0100")
    assert p is not None
    assert p.festival_day == "2027-06-11"


def test_rule_venue_busy(festival: Festival):
    """Refuse show if venue is busy (within 30m turnaround gap)."""
    # After Hours runs 01:00-02:00 at le-kiosque; next available slot is 02:30
    too_early = Performance(
        kind="solo",
        title="Night Owl",
        venue="le-kiosque",
        start="2027-06-12T02:15",
        duration_minutes=30,
        artist="karim-benali",
    )
    with pytest.raises(ValueError, match="Le Kiosque is busy"):
        festival.add_performance(too_early)


def test_rule_artist_busy_in_another_venue(festival: Festival):
    """Refuse show if artist is already performing in another venue."""
    # Max Pellerin is on stage at le-kiosque 23:30-00:30
    conflicting = Performance(
        kind="solo",
        title="Double Booked",
        venue="la-cabane",
        start="2027-06-11T23:45",
        duration_minutes=30,
        artist="max-pellerin",
    )
    with pytest.raises(ValueError, match="Max Pellerin is on stage"):
        festival.add_performance(conflicting)


def test_rule_artist_busy_as_act_in_lineup(festival: Festival):
    """Refuse show if artist is booked as an act in a lineup elsewhere."""
    # Nora Lebrun is an act in After Hours (01:00-02:00)
    conflicting = Performance(
        kind="solo",
        title="Secret Set",
        venue="la-cabane",
        start="2027-06-12T01:15",
        duration_minutes=30,
        artist="nora-lebrun",
    )
    with pytest.raises(ValueError, match="Nora Lebrun is on stage"):
        festival.add_performance(conflicting)


def test_rule_day_outside_festival(festival: Festival):
    """Refuse show on a day outside festival dates."""
    out_of_bounds = Performance(
        kind="solo",
        title="Too Late",
        venue="la-cabane",
        start="2027-06-14T10:00",
        duration_minutes=60,
        artist="karim-benali",
    )
    with pytest.raises(ValueError, match="not a day of the festival"):
        festival.add_performance(out_of_bounds)


def test_rule_duration_boundaries(festival: Festival):
    """Duration must be between 1 and 360 minutes inclusive[cite: 1]."""
    zero_min = Performance(
        kind="solo",
        title="Instant",
        venue="la-cabane",
        start="2027-06-11T14:00",
        duration_minutes=0,
        artist="karim-benali",
    )
    with pytest.raises(ValueError, match="Duration must be between 1 and 360"):
        festival.add_performance(zero_min)

    too_long = Performance(
        kind="solo",
        title="Marathon",
        venue="la-cabane",
        start="2027-06-11T14:00",
        duration_minutes=361,
        artist="karim-benali",
    )
    with pytest.raises(ValueError, match="Duration must be between 1 and 360"):
        festival.add_performance(too_long)


def test_rule_unknown_venue_and_artist(festival: Festival):
    """Refuse unknown venue and unknown artist[cite: 1]."""
    unknown_v = Performance(
        kind="solo",
        title="Mystery",
        venue="nowhere",
        start="2027-06-11T14:00",
        duration_minutes=45,
        artist="karim-benali",
    )
    with pytest.raises(ValueError, match="Unknown venue 'nowhere'"):
        festival.add_performance(unknown_v)

    unknown_a = Performance(
        kind="solo",
        title="Ghost",
        venue="la-cabane",
        start="2027-06-11T14:00",
        duration_minutes=45,
        artist="ghost-artist",
    )
    with pytest.raises(ValueError, match="Unknown artist 'ghost-artist'"):
        festival.add_performance(unknown_a)


def test_now_playing_and_up_next(festival: Festival):
    """Check now_playing and up_next queries[cite: 1]."""
    at_moment = datetime.fromisoformat("2027-06-11T23:45")
    now = festival.now_playing(at_moment)
    assert len(now) == 1
    assert now[0].title == "Late Laughs"

    up = festival.up_next(at_moment, limit=3)
    assert len(up) == 1
    assert up[0].title == "After Hours"