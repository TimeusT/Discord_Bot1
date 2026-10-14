"""The full journey of one link: fetch post -> transcribe -> analyse -> format."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from src.placebot.analysis import PlaceAnalyzer
from src.placebot.config import Settings
from src.placebot.formatter import format_place
from src.placebot.instagram import fetch_post
from src.placebot.media import shrink_video
from src.placebot.models import Attachment, PostData
from src.placebot.transcription import Transcriber

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaceReply:
    """One place's message: the text plus the post's video/photos to attach."""

    text: str
    attachments: list[Attachment]


async def build_replies(
    url: str,
    settings: Settings,
    transcriber: Transcriber,
    analyzer: PlaceAnalyzer,
    upload_limit: int,
) -> list[PlaceReply]:
    # Downloaded files live in a temporary folder that is deleted automatically,
    # so everything needed later is copied into memory before it closes.
    with tempfile.TemporaryDirectory(prefix="placebot_") as workdir:
        post = await fetch_post(url, Path(workdir), settings.instagram_cookies_file, settings.max_media_items)
        post = await _add_transcript(post, transcriber)
        attachments, skipped = await _prepare_attachments(post, upload_limit)

    places = await analyzer.extract_places(post)

    notice = ""
    if skipped:
        notice = f"⚠️ {skipped} file(s) were too big to upload here. Open the post link above to watch."

    # The media belongs to the post, so it goes under the first place only.
    return [
        PlaceReply(
            text=format_place(place, post, notice if index == 0 else ""),
            attachments=attachments if index == 0 else [],
        )
        for index, place in enumerate(places)
    ]


async def _add_transcript(post: PostData, transcriber: Transcriber) -> PostData:
    video = next((item for item in post.media if item.is_video), None)
    if not video:
        return post
    try:
        transcript = await asyncio.to_thread(transcriber.transcribe, video.path)
    except Exception:
        # A failed transcript (e.g. a silent video) shouldn't stop us: the caption may be enough.
        log.warning("Transcription failed for %s", post.url, exc_info=True)
        return post
    return replace(post, transcript=transcript)


async def _prepare_attachments(post: PostData, upload_limit: int) -> tuple[list[Attachment], int]:
    """Read each file into memory, shrinking videos that are too big. Returns (files, skipped)."""
    attachments: list[Attachment] = []
    skipped = 0
    for number, item in enumerate(post.media, start=1):
        path: Path | None = item.path
        if item.is_video and path.stat().st_size > upload_limit:
            path = await shrink_video(path, item.duration, upload_limit)
        if path is None or path.stat().st_size > upload_limit:
            skipped += 1
            continue
        attachments.append(Attachment(f"instagram_{number}{path.suffix}", path.read_bytes()))
    return attachments, skipped
