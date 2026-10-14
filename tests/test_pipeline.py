import asyncio
import shutil
import subprocess
from dataclasses import replace

import pytest

from src.placebot import pipeline
from src.placebot.config import Settings
from src.placebot.models import Category, MediaFile, Place, PostData

PLACE = Place(
    name="Galaxy Cloud Valley",
    place_type="Spa",
    city="Xi'an",
    country="China",
    country_code="CN",
    categories=[Category.HOTEL],
    highlights=["Great facilities."],
)


class FakeTranscriber:
    def transcribe(self, path):
        return "spoken words"


class FakeAnalyzer:
    def __init__(self, places):
        self.places = places
        self.seen_post = None

    async def extract_places(self, post):
        self.seen_post = post
        return self.places


SETTINGS = Settings(discord_token="x", anthropic_api_key="y")


def run(monkeypatch, post_factory, places, upload_limit):
    async def fake_fetch(url, workdir, cookies, max_items):
        return post_factory(workdir)

    monkeypatch.setattr(pipeline, "fetch_post", fake_fetch)
    analyzer = FakeAnalyzer(places)
    replies = asyncio.run(
        pipeline.build_replies("https://www.instagram.com/reel/ABC/", SETTINGS, FakeTranscriber(), analyzer, upload_limit)
    )
    return replies, analyzer


def photo_post(workdir):
    photo = workdir / "photo1.jpg"
    photo.write_bytes(b"jpegdata")
    return PostData(
        url="https://www.instagram.com/p/ABC/",
        username="someone",
        caption="cap",
        media=[MediaFile(photo, is_video=False)],
    )


def test_photo_post_attaches_the_photo_and_formats_the_place(monkeypatch):
    replies, analyzer = run(monkeypatch, photo_post, [PLACE], upload_limit=1000)
    (reply,) = replies
    assert [a.data for a in reply.attachments] == [b"jpegdata"]
    assert reply.attachments[0].filename == "instagram_1.jpg"
    assert "From [someone](https://www.instagram.com/p/ABC/)" in reply.text
    assert analyzer.seen_post.transcript == ""  # photos have no speech


def test_media_goes_under_the_first_place_only(monkeypatch):
    replies, _ = run(monkeypatch, photo_post, [PLACE, replace(PLACE, name="Second Place")], upload_limit=1000)
    assert len(replies[0].attachments) == 1
    assert replies[1].attachments == []


def test_no_places_gives_no_replies(monkeypatch):
    replies, _ = run(monkeypatch, photo_post, [], upload_limit=1000)
    assert replies == []


def test_files_over_the_limit_are_skipped_with_a_notice(monkeypatch):
    replies, _ = run(monkeypatch, photo_post, [PLACE], upload_limit=3)  # photo is 8 bytes
    (reply,) = replies
    assert reply.attachments == []
    assert "too big to upload" in reply.text


needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed")


def video_post(workdir):
    video = workdir / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=duration=6:size=1280x720:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
            "-c:v", "libx264", "-b:v", "6M", "-c:a", "aac", str(video),
        ],
        check=True,
    )
    return PostData(
        url="https://www.instagram.com/reel/ABC/",
        username="someone",
        caption="cap",
        media=[MediaFile(video, is_video=True, duration=6.0)],
    )


@needs_ffmpeg
def test_oversized_video_is_shrunk_transcribed_and_attached(monkeypatch):
    limit = 1_000_000
    replies, analyzer = run(monkeypatch, video_post, [PLACE], upload_limit=limit)
    (reply,) = replies
    assert len(reply.attachments) == 1
    assert len(reply.attachments[0].data) <= limit
    assert reply.attachments[0].filename.endswith(".mp4")
    assert analyzer.seen_post.transcript == "spoken words"
    assert "too big" not in reply.text
