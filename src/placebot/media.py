"""Getting files ready for Discord: shrinking big videos and grouping files into messages."""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from src.placebot.models import Attachment

log = logging.getLogger(__name__)

MAX_FILES_PER_MESSAGE = 10  # Discord's own limit
_AUDIO_KBPS = 96
_MIN_VIDEO_KBPS = 150  # below this a video looks too bad to be worth sending
_FFMPEG_TIMEOUT_SECONDS = 180


async def shrink_video(source: Path, duration: float | None, limit_bytes: int) -> Path | None:
    """Re-encode a video so it fits in `limit_bytes`. Returns None if that isn't possible.

    Needs ffmpeg installed and a known video length. The picture quality is lowered just
    enough to fit; very long videos are skipped because they would look terrible.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not duration or duration <= 0:
        return None

    # Total bits available, with an 8% safety margin, minus the sound track.
    video_kbps = int(limit_bytes * 8 * 0.92 / duration / 1000) - _AUDIO_KBPS
    if video_kbps < _MIN_VIDEO_KBPS:
        return None

    target = source.with_name(f"{source.stem}_small.mp4")
    command = [
        ffmpeg, "-y", "-i", str(source),
        "-vf", "scale='min(720,iw)':-2",  # never wider than 720 pixels, height stays in proportion
        "-c:v", "libx264", "-preset", "veryfast",
        "-b:v", f"{video_kbps}k", "-maxrate", f"{video_kbps}k", "-bufsize", f"{video_kbps * 2}k",
        "-c:a", "aac", "-b:a", f"{_AUDIO_KBPS}k",
        "-movflags", "+faststart",  # lets the video start playing before it fully loads
        str(target),
    ]
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    try:
        await asyncio.wait_for(process.wait(), timeout=_FFMPEG_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        process.kill()
        log.warning("ffmpeg timed out shrinking %s", source.name)
        return None

    if process.returncode != 0 or not target.exists() or target.stat().st_size > limit_bytes:
        return None
    return target


def batch_attachments(attachments: list[Attachment], limit_bytes: int) -> list[list[Attachment]]:
    """Split files into groups that each fit in one Discord message (10 files, size limit)."""
    batches: list[list[Attachment]] = []
    current: list[Attachment] = []
    size = 0
    for attachment in attachments:
        if current and (
            len(current) >= MAX_FILES_PER_MESSAGE or size + len(attachment.data) > limit_bytes
        ):
            batches.append(current)
            current, size = [], 0
        current.append(attachment)
        size += len(attachment.data)
    if current:
        batches.append(current)
    return batches
