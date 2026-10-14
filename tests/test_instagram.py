from pathlib import Path

import pytest

from src.placebot.instagram import extract_instagram_urls, parse_open_graph, parse_ytdlp_info


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


def test_username_uses_the_handle_not_the_numeric_id():
    info = {"channel": "justfooddxd", "uploader_id": "25025320", "uploader": "Just Food", "description": "cap"}
    username, caption, media = parse_ytdlp_info(info, [info])
    assert username == "justfooddxd"
    assert caption == "cap"


def test_username_falls_back_without_ever_using_a_number_first():
    old_style = {"uploader_id": "naomipq", "uploader": "Naomi"}
    assert parse_ytdlp_info(old_style, [old_style])[0] == "naomipq"

    only_numbers = {"uploader_id": "25025320", "uploader": "Just Food"}
    assert parse_ytdlp_info(only_numbers, [only_numbers])[0] == "Just Food"

    assert parse_ytdlp_info({}, [])[0] == "Instagram user"


def test_carousel_mixes_downloaded_videos_and_photo_links():
    video = {
        "channel": "someone",
        "duration": 12.5,
        "requested_downloads": [{"filepath": "/tmp/a.mp4"}],
        "thumbnails": [{"url": "https://cdn/video-cover.jpg", "width": 100, "height": 100}],
    }
    photo = {
        "channel": "someone",
        "formats": [],
        "thumbnails": [
            {"url": "https://cdn/small.jpg", "width": 320, "height": 320},
            {"url": "https://cdn/big.jpg", "width": 1080, "height": 1080},
            {"url": "https://cdn/medium.jpg", "width": 640, "height": 640},
        ],
    }
    _, _, media = parse_ytdlp_info({"channel": "someone", "_type": "playlist"}, [video, photo])

    assert media[0].video_path == Path("/tmp/a.mp4")  # the video itself, not its cover photo
    assert media[0].duration == 12.5
    assert media[1].image_url == "https://cdn/big.jpg"  # the biggest size of the photo
    assert len(media) == 2


def test_parse_open_graph_reads_username_caption_and_image():
    html = (
        '<html><head>'
        '<meta property="og:title" content="Food on Instagram: &quot;Amazing spa&quot;">'
        '<meta property="og:description" content="12 likes, 1 comments - justfooddxd on May 1, 2025: Amazing spa">'
        '<meta property="og:image" content="https://cdn.example.com/a.jpg">'
        "</head></html>"
    )
    username, caption, image_url = parse_open_graph(html)
    assert username == "justfooddxd"
    assert "Amazing spa" in caption
    assert image_url == "https://cdn.example.com/a.jpg"


def test_parse_open_graph_rejects_empty_pages():
    with pytest.raises(ValueError):
        parse_open_graph("<html></html>")
