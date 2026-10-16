from datetime import datetime
import pytest

from festival import (
    Artist,
    Festival,
    Lineup,
    Performance,
    SoloShow,
    Venue,
    Workshop,
    load_festival,
)


@pytest.fixture
def festival() -> Festival:
    venues = [
        Venue(name="Grand Casino", capacity=650, address="Seafront", slug="grand-casino"),
        Venue(name="Le Kiosque", capacity=120, address="Promenade", slug="le-kiosque"),
        Venue(name="La Cabane", capacity=40, address="Beach", slug="la-cabane"),
    ]
    artists = [
        Artist(name="Max Pellerin", slug="max-pellerin"),
        Artist(name="Karim Benali", slug="karim-benali"),
        Artist(name="Nora Lebrun", slug="nora-lebrun"),
        Artist(name="Léa Fontaine", slug="lea-fontaine"),
        Artist(name="Hugo Lemaire", slug="hugo-lemaire"),
    ]
    performances = [
        SoloShow(
            title="Late Laughs",
            venue="le-kiosque",
            start="2027-06-11T23:30",
            duration_minutes=60,
            artist="max-pellerin",
        ),
        Lineup(
            title="After Hours",
            venue="le-kiosque",
            start="2027-06-12T01:00",
            duration_minutes=60,
            host="karim-benali",
            acts=["nora-lebrun", "lea-fontaine"],
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


def test_cannot_instantiate_abstract_performance():
    with pytest.raises(TypeError):
        Performance(title="Direct", venue="la-cabane", start="2027-06-11T10:00", duration_minutes=30)  # type: ignore


def test_festival_day_midnight_cutoff(festival: Festival):
    p = festival.find_performance("le-kiosque-2027-06-12-0100")
    assert p is not None
    assert p.festival_day == "2027-06-11"


def test_rule_venue_busy(festival: Festival):
    too_early = SoloShow(
        title="Night Owl",
        venue="le-kiosque",
        start="2027-06-12T02:15",
        duration_minutes=30,
        artist="karim-benali",
    )
    with pytest.raises(ValueError, match="Le Kiosque is busy"):
        festival.add_performance(too_early)


def test_rule_artist_busy_in_another_venue(festival: Festival):
    conflicting = SoloShow(
        title="Double Booked",
        venue="la-cabane",
        start="2027-06-11T23:45",
        duration_minutes=30,
        artist="max-pellerin",
    )
    with pytest.raises(ValueError, match="Max Pellerin is on stage"):
        festival.add_performance(conflicting)


def test_rule_artist_busy_as_act_in_lineup(festival: Festival):
    conflicting = SoloShow(
        title="Secret Set",
        venue="la-cabane",
        start="2027-06-12T01:15",
        duration_minutes=30,
        artist="nora-lebrun",
    )
    with pytest.raises(ValueError, match="Nora Lebrun is on stage"):
        festival.add_performance(conflicting)


def test_rule_day_outside_festival(festival: Festival):
    out_of_bounds = SoloShow(
        title="Too Late",
        venue="la-cabane",
        start="2027-06-14T10:00",
        duration_minutes=60,
        artist="karim-benali",
    )
    with pytest.raises(ValueError, match="not a day of the festival"):
        festival.add_performance(out_of_bounds)


def test_rule_duration_boundaries(festival: Festival):
    zero_min = SoloShow(
        title="Instant",
        venue="la-cabane",
        start="2027-06-11T14:00",
        duration_minutes=0,
        artist="karim-benali",
    )
    with pytest.raises(ValueError, match="Duration must be between 1 and 360"):
        festival.add_performance(zero_min)


def test_rule_unknown_venue_and_artist(festival: Festival):
    unknown_v = SoloShow(
        title="Mystery",
        venue="nowhere",
        start="2027-06-11T14:00",
        duration_minutes=45,
        artist="karim-benali",
    )
    with pytest.raises(ValueError, match="Unknown venue 'nowhere'"):
        festival.add_performance(unknown_v)


def test_lineup_duration_rules():
    with pytest.raises(ValueError, match="requires at least 36 minutes"):
        Lineup(
            title="Short Lineup",
            venue="grand-casino",
            start="2027-06-11T14:00",
            duration_minutes=35,
            host="karim-benali",
            acts=["max-pellerin", "nora-lebrun", "lea-fontaine"],
        )

    valid_lineup = Lineup(
        title="Exact Lineup",
        venue="grand-casino",
        start="2027-06-11T14:00",
        duration_minutes=36,
        host="karim-benali",
        acts=["max-pellerin", "nora-lebrun", "lea-fontaine"],
    )
    assert valid_lineup.duration_minutes == 36


def test_lineup_acts_constraints():
    with pytest.raises(ValueError, match="at least 2 acts"):
        Lineup(
            title="Lone Act",
            venue="grand-casino",
            start="2027-06-11T14:00",
            duration_minutes=30,
            host="karim-benali",
            acts=["max-pellerin"],
        )

    with pytest.raises(ValueError, match="must be unique"):
        Lineup(
            title="Duplicate Act",
            venue="grand-casino",
            start="2027-06-11T14:00",
            duration_minutes=30,
            host="karim-benali",
            acts=["max-pellerin", "max-pellerin"],
        )

    with pytest.raises(ValueError, match="cannot also be an act"):
        Lineup(
            title="Host as Act",
            venue="grand-casino",
            start="2027-06-11T14:00",
            duration_minutes=30,
            host="max-pellerin",
            acts=["max-pellerin", "nora-lebrun"],
        )


def test_workshop_capacity_clamped(festival: Festival):
    workshop = Workshop(
        title="Massive Workshop",
        venue="grand-casino",
        start="2027-06-11T10:00",
        duration_minutes=90,
        teacher="karim-benali",
        max_participants=999,
    )
    v_cap = festival.venues_map["grand-casino"].capacity
    assert workshop.get_capacity(v_cap) == 650


def test_soloshow_min_age():
    with pytest.raises(ValueError, match="between 0 and 18"):
        SoloShow(
            title="Old",
            venue="la-cabane",
            start="2027-06-11T14:00",
            duration_minutes=45,
            artist="karim-benali",
            min_age=21,
        )


def test_dataset_summaries():
    fest = load_festival()

    after_hours = fest.find_performance("le-kiosque-2027-06-12-0100")
    assert after_hours is not None
    assert after_hours.summary(fest.artists_map) == "hosted by Tom Vasseur, with Hugo Lemaire, Maya Choukri"

    improv = fest.find_performance("la-cabane-2027-06-11-1030")
    assert improv is not None
    assert improv.summary(fest.artists_map) == "with Inès Moreau, 3/12 places taken"

    tall_tales = fest.find_performance("grand-casino-2027-06-11-2030")
    assert tall_tales is not None
    assert tall_tales.summary(fest.artists_map) == "Léa Fontaine"