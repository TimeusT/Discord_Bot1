from src.placebot.analysis import parse_places
from src.placebot.models import Category

GOOD = {
    "name": "Galaxy Cloud Valley",
    "name_local": "星河云谷",
    "place_type": "24 Hour Spa",
    "city": "Xi'an",
    "city_local": "西安",
    "country": "China",
    "country_code": "cn",
    "categories": ["hotel", "cultural_traditional", "not_a_category"],
    "highlights": ["Great facilities.", "  ", "Modern design."],
}


def test_parses_a_complete_place():
    (place,) = parse_places({"places": [GOOD]}, limit=5)
    assert place.country_code == "CN"
    assert place.categories == [Category.HOTEL, Category.CULTURAL]  # unknown category dropped
    assert place.highlights == ["Great facilities.", "Modern design."]  # blanks removed
    assert place.name_local == "星河云谷"


def test_null_text_becomes_none_and_bad_code_is_blanked():
    raw = {**GOOD, "name_local": "null", "city_local": None, "country_code": "CHN"}
    (place,) = parse_places({"places": [raw]}, limit=5)
    assert place.name_local is None
    assert place.city_local is None
    assert place.country_code == ""


def test_incomplete_entries_are_skipped():
    broken = {k: v for k, v in GOOD.items() if k != "city"}
    assert len(parse_places({"places": [broken, GOOD]}, limit=5)) == 1


def test_limit_is_respected():
    assert len(parse_places({"places": [GOOD] * 10}, limit=3)) == 3


def test_empty_answer_gives_no_places():
    assert parse_places({"places": []}, limit=5) == []
    assert parse_places({}, limit=5) == []
