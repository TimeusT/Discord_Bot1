"""Builds the Discord message for a place, using Discord's heading/markdown style."""

from __future__ import annotations

from src.placebot.links import BookingLink
from src.placebot.models import Place, PostData

DISCORD_MESSAGE_LIMIT = 2000


def flag_emoji(country_code: str) -> str:
    """Turn a country code like 'CN' into its flag emoji (empty if the code is invalid).

    Real emoji characters are used because Discord only converts :shortcodes: when
    a person types them, not when a bot sends them.
    """
    if len(country_code) != 2 or not country_code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(letter) - ord("A")) for letter in country_code.upper())


def format_place(place: Place, post: PostData, link: BookingLink) -> str:
    name = place.name
    if place.name_local and place.name_local.casefold() != place.name.casefold():
        name = f"{place.name} ({place.name_local})"

    city = place.city
    if place.city_local and place.city_local.casefold() != place.city.casefold():
        city = f"{place.city} (**{place.city_local}**)"
    flag = flag_emoji(place.country_code)
    location = f"{city}, {place.country}" + (f"   {flag}" if flag else "")

    lines = [
        f"# {name} - {place.place_type}",
        f"## 📍 {location}",
    ]
    if place.categories:
        lines.append("## 🔷 " + "   •   ".join(c.label for c in place.categories))
    lines += [
        f"## ℹ️ **Book at [{link.label}]({link.url})**",
        f"## 🔍 **From [{post.username}]({post.url})**",
        "## What to expect:",
    ]

    # Discord rejects messages over 2000 characters, so drop the last bullets if needed.
    bullets = [f"- {text}" for text in place.highlights]
    while bullets and len("\n".join(lines + bullets)) > DISCORD_MESSAGE_LIMIT:
        bullets.pop()

    return "\n".join(lines + bullets)[:DISCORD_MESSAGE_LIMIT]
