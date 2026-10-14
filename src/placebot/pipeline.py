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
from src.placebot.instagram import DownloadedImage, download_images, fetch_post
from src.placebot.links import build_booking_link
from src.placebot.transcription import Transcriber

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaceReply:
    """One Discord message to send: the text plus any images to attach."""

    text: str
    images: list[DownloadedImage]


async def build_replies(
    url: str, settings: Settings, transcriber: Transcriber, analyzer: PlaceAnalyzer
) -> list[PlaceReply]:
    # Downloaded audio lives in a temporary folder that is deleted automatically.
    with tempfile.TemporaryDirectory(prefix="placebot_") as workdir:
        post = await fetch_post(url, Path(workdir), settings.instagram_cookies_file, settings.max_images)

        if post.audio_path:
            try:
                transcript = await asyncio.to_thread(transcriber.transcribe, post.audio_path)
                post = replace(post, transcript=transcript)
            except Exception:
                # A failed transcript shouldn't stop us: the caption may be enough.
                log.exception("Transcription failed for %s", url)

    places = await analyzer.extract_places(post)
    images = await download_images(post.image_urls[: settings.max_images])

    # The images belong to the post, so they go under the first place only.
    return [
        PlaceReply(
            text=format_place(place, post, build_booking_link(place)),
            images=images if index == 0 else [],
        )
        for index, place in enumerate(places)
    ]
