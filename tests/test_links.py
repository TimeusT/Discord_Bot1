from src.placebot.links import build_booking_link
from src.placebot.models import Category, Place


def make_place(country_code: str, country: str) -> Place:
    return Place(
        name="Galaxy Cloud Valley",
        place_type="Spa",
        city="Xi'an",
        country=country,
        country_code=country_code,
        categories=[Category.HOTEL],
        highlights=[],
    )


def test_asian_country_uses_trip_com():
    link = build_booking_link(make_place("CN", "China"))
    assert link.label == "Trip.com"
    assert "trip.com" in link.url


def test_other_country_uses_booking_com():
    link = build_booking_link(make_place("FR", "France"))
    assert link.label == "Booking.com"
    assert link.url.startswith("https://www.booking.com/searchresults.html?ss=")


def test_unknown_country_code_falls_back_to_booking_com():
    assert build_booking_link(make_place("", "Atlantis")).label == "Booking.com"


def test_query_is_url_encoded():
    link = build_booking_link(make_place("FR", "France"))
    assert " " not in link.url
    assert "Galaxy+Cloud+Valley" in link.url
