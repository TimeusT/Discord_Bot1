import pytest

from src.placebot.instagram import extract_instagram_urls, parse_open_graph


def test_extracts_and_cleans_reel_link():
    text = "look https://www.instagram.com/reel/DMkKaGgpHKP/?igsh=MXNhYmhndXIzYmx5bw%3D%3D !"
    assert extract_instagram_urls(text) == ["https://www.instagram.com/reel/DMkKaGgpHKP/"]


def test_handles_username_in_path_and_plural_reels():
    text = "https://instagram.com/someone/p/ABC123/ https://www.instagram.com/reels/XYZ_9-/"
    assert extract_instagram_urls(text) == [
        "https://www.instagram.com/p/ABC123/",
        "https://www.instagram.com/reel/XYZ_9-/",
    ]


def test_duplicates_and_other_sites_are_ignored():
    text = (
        "https://www.instagram.com/p/ABC/ https://www.instagram.com/p/ABC/?x=1 "
        "https://example.com/p/ABC/"
    )
    assert extract_instagram_urls(text) == ["https://www.instagram.com/p/ABC/"]


def test_parse_open_graph_reads_username_caption_and_image():
    html = (
        '<html><head>'
        '<meta property="og:title" content="Food on Instagram: &quot;Amazing spa&quot;">'
        '<meta property="og:description" content="12 likes, 1 comments - justfooddxd on May 1, 2025: Amazing spa">'
        '<meta property="og:image" content="https://cdn.example.com/a.jpg">'
        "</head></html>"
    )
    post = parse_open_graph(html, "https://www.instagram.com/p/ABC/")
    assert post.username == "justfooddxd"
    assert "Amazing spa" in post.caption
    assert post.image_urls == ["https://cdn.example.com/a.jpg"]


def test_parse_open_graph_rejects_empty_pages():
    with pytest.raises(ValueError):
        parse_open_graph("<html></html>", "https://www.instagram.com/p/ABC/")
