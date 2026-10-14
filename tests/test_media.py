import asyncio
import shutil
import subprocess

import pytest

from src.placebot.media import MAX_FILES_PER_MESSAGE, batch_attachments, shrink_video
from src.placebot.models import Attachment


def make_files(*sizes: int) -> list[Attachment]:
    return [Attachment(f"f{i}.bin", b"x" * size) for i, size in enumerate(sizes)]


def test_files_that_fit_stay_in_one_message():
    assert len(batch_attachments(make_files(10, 10, 10), limit_bytes=100)) == 1


def test_files_are_split_by_size():
    batches = batch_attachments(make_files(60, 60, 30), limit_bytes=100)
    assert [len(b) for b in batches] == [1, 2]


def test_files_are_split_by_count():
    batches = batch_attachments(make_files(*[1] * (MAX_FILES_PER_MESSAGE + 2)), limit_bytes=10_000)
    assert [len(b) for b in batches] == [MAX_FILES_PER_MESSAGE, 2]


def test_no_files_gives_no_messages():
    assert batch_attachments([], limit_bytes=100) == []


needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed")


@pytest.fixture
def big_video(tmp_path):
    """A 6 second 720p test video with sound, encoded at a high bitrate (so it is large)."""
    path = tmp_path / "big.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=duration=6:size=1280x720:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
            "-c:v", "libx264", "-b:v", "6M", "-c:a", "aac", str(path),
        ],
        check=True,
    )
    return path


@needs_ffmpeg
def test_big_video_is_shrunk_to_fit(big_video):
    limit = 1_000_000
    assert big_video.stat().st_size > limit

    result = asyncio.run(shrink_video(big_video, duration=6.0, limit_bytes=limit))

    assert result is not None
    assert result.stat().st_size <= limit


@needs_ffmpeg
def test_impossible_limits_and_unknown_length_give_up(big_video):
    assert asyncio.run(shrink_video(big_video, duration=6.0, limit_bytes=50_000)) is None
    assert asyncio.run(shrink_video(big_video, duration=None, limit_bytes=1_000_000)) is None
