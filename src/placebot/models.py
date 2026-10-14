"""Plain data containers shared by the rest of the bot."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Category(Enum):
    """The place categories. The value is what the AI returns; label is what Discord shows."""

    HOTEL = "hotel"
    CRUISE = "cruise"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    SIGHTSEEING = "sightseeing"
    CULTURAL = "cultural_traditional"

    @property
    def label(self) -> str:
        return "Cultural/Traditional" if self is Category.CULTURAL else self.value.title()


@dataclass(frozen=True)
class PostData:
    """Everything we learned from one Instagram post."""

    url: str
    username: str
    caption: str
    image_urls: list[str] = field(default_factory=list)
    audio_path: Path | None = None  # only set for videos, used to make the transcript
    transcript: str = ""


@dataclass(frozen=True)
class Place:
    """One place mentioned in a post, ready to be formatted."""

    name: str
    place_type: str  # short description, e.g. "24 Hour Spa"
    city: str
    country: str
    country_code: str  # two-letter code like "CN"; empty if unknown
    categories: list[Category]
    highlights: list[str]  # the "What to expect" bullets
    name_local: str | None = None  # name in its original language, if different
    city_local: str | None = None  # city in its original language, if different
