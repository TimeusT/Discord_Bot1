"""Chooses where to send people to book a place: Trip.com for Asia, Booking.com elsewhere."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus

from src.placebot.models import Place

# Edit this list to change which countries count as "Asia" for Trip.com.
# Currently East, Southeast, South and Central Asia (the Middle East, Turkey and
# Russia use Booking.com).
ASIA_COUNTRY_CODES = frozenset({
    "CN", "HK", "MO", "TW", "JP", "KR", "KP", "MN",  # East
    "SG", "MY", "TH", "VN", "ID", "PH", "KH", "LA", "MM", "BN", "TL",  # Southeast
    "IN", "NP", "LK", "BD", "BT", "MV", "PK", "AF",  # South
    "KZ", "UZ", "KG", "TJ", "TM",  # Central
})


@dataclass(frozen=True)
class BookingLink:
    label: str
    url: str


def build_booking_link(place: Place) -> BookingLink:
    query = " ".join(part for part in (place.name, place.city, place.country) if part)

    if place.country_code in ASIA_COUNTRY_CODES:
        # Trip.com's own search links need an internal city ID we can't know, so this
        # searches Trip.com's hotel pages for the place instead. Swap this one line if
        # you later get access to Trip.com's affiliate/partner links.
        return BookingLink("Trip.com", f"https://www.google.com/search?q={quote_plus('site:trip.com/hotels ' + query)}")

    return BookingLink("Booking.com", f"https://www.booking.com/searchresults.html?ss={quote_plus(query)}")
