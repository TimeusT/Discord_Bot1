from src.placebot.analysis import SECONDARY_CATEGORY_MIN_SCORE, choose_categories, parse_places
from src.placebot.models import Category

GOOD = {
    "name": "Galaxy Cloud Valley",
    "name_local": "星河云谷",
    "place_type": "24 Hour Spa",
    "city": "Xi'an",
    "city_local": "西安",
    "country": "China",
    "country_code": "cn",
    "category_scores": {"hotel": 0.9, "entertainment": 0.3, "cultural_traditional": 0.1},
    "highlights": ["Great facilities.", "  ", "Modern design."],
}


def test_parses_a_complete_place():
    (place,) = parse_places({"places": [GOOD]}, limit=5)
    assert place.country_code == "CN"
    assert place.categories == [Category.HOTEL]  # entertainment (0.3) is too weak to add
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


def test_weak_second_category_is_dropped():
    scores = {"hotel": 0.95, "entertainment": SECONDARY_CATEGORY_MIN_SCORE - 0.01}
    assert choose_categories(scores) == [Category.HOTEL]


def test_strong_second_category_is_kept_after_the_main_one():
    scores = {"hotel": 0.7, "entertainment": 0.85, "shopping": 0.2}
    assert choose_categories(scores) == [Category.ENTERTAINMENT, Category.HOTEL]


def test_never_more_than_two_categories():
    scores = {"hotel": 0.9, "cruise": 0.9, "shopping": 0.9, "sightseeing": 0.9}
    assert len(choose_categories(scores)) == 2


def test_main_category_is_kept_even_if_the_score_is_low():
    assert choose_categories({"sightseeing": 0.2}) == [Category.SIGHTSEEING]


def test_bad_or_missing_scores_give_no_category():
    assert choose_categories({}) == []
    assert choose_categories({"hotel": "high", "cruise": None}) == []
    assert choose_categories({"hotel": 5}) == [Category.HOTEL]  # values are clamped to 0-1
