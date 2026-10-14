"""Fetching an Instagram post: its caption, username, images and (for videos) audio."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

import httpx
import yt_dlp

from src.placebot.models import PostData

log = logging.getLogger(__name__)

# Matches post, reel and tv links, with or without a username in the path.
_URL_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:[\w.]+/)?(p|reels?|tv)/([\w-]+)", re.IGNORECASE
)
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_IMAGE_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
_MAX_IMAGE_BYTES = 8 * 1024 * 1024  # stays under Discord's upload limit


class PostUnavailableError(Exception):
    """The post could not be read. The message is safe to show to Discord users."""


@dataclass(frozen=True)
class DownloadedImage:
    filename: str
    data: bytes


def extract_instagram_urls(text: str) -> list[str]:
    """Find Instagram post links in a message and return clean, de-duplicated versions.

    Tracking parameters such as ?igsh=... are dropped: they identify who shared the
    link, so removing them is better for privacy and keeps the link short.
    """
    urls: list[str] = []
    for match in _URL_RE.finditer(text):
        kind = "reel" if match.group(1).lower() == "reels" else match.group(1).lower()
        url = f"https://www.instagram.com/{kind}/{match.group(2)}/"
        if url not in urls:
            urls.append(url)
    return urls


async def fetch_post(url: str, workdir: Path, cookies_file: str | None, max_images: int) -> PostData:
    """Read a post, trying yt-dlp first (handles videos) and page metadata second."""
    try:
        # yt-dlp is blocking, so it runs in a thread to keep the bot responsive.
        return await asyncio.to_thread(_fetch_with_ytdlp, url, workdir, cookies_file, max_images)
    except Exception as exc:  # yt-dlp raises many different error types
        log.info("yt-dlp could not read %s (%s); trying page metadata", url, exc)

    try:
        return await _fetch_open_graph(url)
    except (httpx.HTTPError, ValueError) as exc:
        raise PostUnavailableError(
            "I couldn't read that Instagram post. It may be private or deleted, "
            "or Instagram is blocking the bot."
        ) from exc


def _fetch_with_ytdlp(url: str, workdir: Path, cookies_file: str | None, max_images: int) -> PostData:
    options = {
        "format": "bestaudio/best",  # audio is all we need for the transcript
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "playlist_items": f"1-{max_images}",  # carousels come back as a list of items
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 20,
        "retries": 2,
    }
    if cookies_file:
        options["cookiefile"] = cookies_file

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

    entries = [entry for entry in (info.get("entries") or [info]) if entry]

    def pick(key: str):
        """First non-empty value for `key`, looking at the post and then its items."""
        return next((src[key] for src in (info, *entries) if src.get(key)), None)

    audio_path = next(
        (
            Path(download["filepath"])
            for entry in entries
            for download in entry.get("requested_downloads", [])
            if download.get("filepath")
        ),
        None,
    )
    images = list(dict.fromkeys(e["thumbnail"] for e in entries if e.get("thumbnail")))

    return PostData(
        url=url,
        username=pick("uploader_id") or pick("channel") or pick("uploader") or "unknown",
        caption=pick("description") or pick("title") or "",
        image_urls=images[:max_images],
        audio_path=audio_path,
    )


class _MetaTagParser(HTMLParser):
    """Collects <meta property="og:..." content="..."> tags from a web page."""

    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attributes = dict(attrs)
        key = attributes.get("property") or attributes.get("name")
        if key and attributes.get("content"):
            self.meta.setdefault(key, attributes["content"])


def parse_open_graph(html: str, url: str) -> PostData:
    """Build a PostData from the preview tags Instagram puts on public post pages."""
    parser = _MetaTagParser()
    parser.feed(html)
    meta = parser.meta

    title = meta.get("og:title", "")
    description = meta.get("og:description", "")
    if not (title or description):
        raise ValueError("page had no readable post details")

    # The description looks like: '1,234 likes, 5 comments - username on May 1, 2025: "caption"'
    match = re.search(r"-\s*([\w.]+)\s+on\s", description)
    return PostData(
        url=url,
        username=match.group(1) if match else "Instagram user",
        caption="\n".join(part for part in (title, description) if part),
        image_urls=[meta["og:image"]] if meta.get("og:image") else [],
    )


async def _fetch_open_graph(url: str) -> PostData:
    async with httpx.AsyncClient(
        headers={"User-Agent": _BROWSER_UA}, follow_redirects=True, timeout=20
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
    return parse_open_graph(response.text, url)


async def download_images(urls: list[str]) -> list[DownloadedImage]:
    """Download images now, because Instagram's image links expire after a short time."""
    images: list[DownloadedImage] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": _BROWSER_UA}, follow_redirects=True, timeout=20
    ) as client:
        for number, image_url in enumerate(urls, start=1):
            try:
                response = await client.get(image_url)
                response.raise_for_status()
            except httpx.HTTPError:
                log.warning("Could not download image %s", image_url)
                continue

            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type in _IMAGE_EXTENSIONS and len(response.content) <= _MAX_IMAGE_BYTES:
                filename = f"image{number}.{_IMAGE_EXTENSIONS[content_type]}"
                images.append(DownloadedImage(filename, response.content))
    return images
