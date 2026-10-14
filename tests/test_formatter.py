from src.placebot.formatter import DISCORD_MESSAGE_LIMIT, flag_emoji, format_place
from src.placebot.models import Category, Place, PostData

POST = PostData(url="https://www.instagram.com/reel/ABC/", username="justfooddxd", caption="")


def make_place(**overrides) -> Place:
    values = dict(
        name="Galaxy Cloud Valley",
        name_local="星河云谷",
        place_type="24 Hour Spa",
        city="Xi'an",
        city_local="西安",
        country="China",
        country_code="CN",
        categories=[Category.HOTEL, Category.ENTERTAINMENT],
        highlights=["Extensive facilities.", "Stunning exterior design."],
    )
    values.update(overrides)
    return Place(**values)


def test_flag_emoji():
    assert flag_emoji("CN") == "🇨🇳"
    assert flag_emoji("jp") == "🇯🇵"
    assert flag_emoji("") == ""
    assert flag_emoji("CHN") == ""


def test_matches_requested_layout():
    lines = format_place(make_place(), POST).splitlines()
    assert lines[0] == "# Galaxy Cloud Valley (星河云谷) - 24 Hour Spa"
    assert lines[1] == "## 📍 Xi'an (**西安**), China   🇨🇳"
    assert lines[2] == "## 🔷 Hotel   •   Entertainment"
    assert lines[3] == "## 🔍 **From [justfooddxd](https://www.instagram.com/reel/ABC/)**"
    assert lines[4] == "## What to expect:"
    assert lines[5] == "- Extensive facilities."


def test_no_booking_line():
    assert "Book at" not in format_place(make_place(), POST)


def test_single_category_shows_just_one():
    text = format_place(make_place(categories=[Category.HOTEL]), POST)
    assert "## 🔷 Hotel\n" in text
    assert "•" not in text


def test_english_only_names_have_no_brackets():
    text = format_place(make_place(name_local=None, city_local=None), POST)
    assert text.splitlines()[0] == "# Galaxy Cloud Valley - 24 Hour Spa"
    assert "## 📍 Xi'an, China" in text


def test_category_line_is_skipped_when_empty():
    assert "🔷" not in format_place(make_place(categories=[]), POST)


def test_notice_is_added_at_the_end():
    text = format_place(make_place(), POST, notice="⚠️ Too big.")
    assert text.splitlines()[-1] == "⚠️ Too big."


def test_long_messages_are_trimmed_to_discord_limit_and_keep_the_notice():
    place = make_place(highlights=["x" * 300 for _ in range(20)])
    text = format_place(place, POST, notice="⚠️ Too big.")
    assert len(text) <= DISCORD_MESSAGE_LIMIT
    assert text.splitlines()[-1] == "⚠️ Too big."
    assert text.splitlines()[-3].startswith("- x")  # whole bullets kept, extras dropped
