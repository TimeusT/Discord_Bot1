"""Fetching an Instagram post: caption, username and its actual videos / photos."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from pathlib import Path

import httpx
import yt_dlp

from src.placebot.models import MediaFile, PostData

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


class PostUnavailableError(Exception):
    """The post could not be read. The message is safe to show to Discord users."""


@dataclass(frozen=True)
class _RawMedia:
    """A media item before photos are downloaded: either a saved video or a photo link."""

    video_path: Path | None = None
    duration: float | None = None
    image_url: str | None = None


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


async def fetch_post(url: str, workdir: Path, cookies_file: str | None, max_items: int) -> PostData:
    """Read a post and save its videos/photos into `workdir`.

    yt-dlp is tried first because it handles videos. If it fails, the post's public
    preview tags are used instead, which still give the caption and one photo.
    """
    try:
        # yt-dlp is blocking, so it runs in a thread to keep the bot responsive.
        info, entries = await asyncio.to_thread(
            _download_with_ytdlp, url, workdir, cookies_file, max_items
        )
        username, caption, raw_media = parse_ytdlp_info(info, entries)
        media = await _save_photos(raw_media, workdir)
        if media or caption:
            return PostData(url=url, username=username, caption=caption, media=media)
    except Exception as exc:  # yt-dlp raises many different error types
        log.info("yt-dlp could not read %s (%s); trying page metadata", url, exc)

    try:
        return await _fetch_open_graph(url, workdir)
    except (httpx.HTTPError, ValueError) as exc:
        raise PostUnavailableError(
            "I couldn't read that Instagram post. It may be private or deleted, "
            "or Instagram is blocking the bot."
        ) from exc


def _download_with_ytdlp(
    url: str, workdir: Path, cookies_file: str | None, max_items: int
) -> tuple[dict, list[dict]]:
    options = {
        # Prefer one file that already contains sound, so no extra video tools are needed.
        "format": "best[ext=mp4]/best/bv*",
        # 720p keeps most reels small enough for Discord's upload limit.
        "format_sort": ["res:720"],
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "playlist_items": f"1-{max_items}",  # carousels come back as a list of items
        "ignore_no_formats_error": True,  # photo items have no video, which is fine
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 20,
        "retries": 2,
    }
    if cookies_file:
        options["cookiefile"] = cookies_file

    with yt_dlp.YoutubeDL(options) as ydl:
        # Step 1: read the post without downloading. Doing it in two steps matters because
        # a one-go download crashes on carousels that contain photos.
        info = ydl.extract_info(url, download=False)
        entries = [entry for entry in (info.get("entries") or [info]) if entry][:max_items]

        # Step 2: download only the items that are videos.
        for index, entry in enumerate(entries):
            if entry.get("formats"):
                entries[index] = ydl.process_ie_result(entry, download=True) or entry
    return info, entries


def parse_ytdlp_info(info: dict, entries: list[dict]) -> tuple[str, str, list[_RawMedia]]:
    """Turn yt-dlp's answer into (username, caption, media items)."""
    sources = [info, *entries]

    caption = next((s["description"] for s in sources if s.get("description")), "") or next(
        (s["title"] for s in sources if s.get("title")), ""
    )

    media: list[_RawMedia] = []
    for entry in entries:
        downloaded = next(
            (d["filepath"] for d in entry.get("requested_downloads", []) if d.get("filepath")), None
        )
        if downloaded:
            media.append(_RawMedia(video_path=Path(downloaded), duration=entry.get("duration")))
        elif image_url := _best_image_url(entry):
            media.append(_RawMedia(image_url=image_url))

    return _pick_username(sources), caption, media


def _pick_username(sources: list[dict]) -> str:
    """Find the poster's @handle.

    yt-dlp's 'uploader_id' is often Instagram's internal number (e.g. 25025320), so the
    handle is taken from 'channel' first, and numbers are only a last resort.
    """
    for source in sources:
        if source.get("channel"):
            return str(source["channel"])
    for source in sources:
        uploader_id = str(source.get("uploader_id") or "")
        if uploader_id and not uploader_id.isdigit():
            return uploader_id
    for source in sources:
        if source.get("uploader"):
            return str(source["uploader"])
    return "Instagram user"


def _best_image_url(entry: dict) -> str | None:
    """The largest photo link for an item (Instagram lists several sizes)."""
    thumbnails = [t for t in entry.get("thumbnails") or [] if t.get("url")]
    if thumbnails:
        return max(thumbnails, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))["url"]
    return entry.get("thumbnail")


async def _save_photos(raw_media: list[_RawMedia], workdir: Path) -> list[MediaFile]:
    """Download the photo items (videos are already saved), keeping the post's order."""
    media: list[MediaFile] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": _BROWSER_UA}, follow_redirects=True, timeout=30
    ) as client:
        for index, item in enumerate(raw_media, start=1):
            if item.video_path:
                media.append(MediaFile(item.video_path, is_video=True, duration=item.duration))
            elif path := await _save_image(client, item.image_url, workdir / f"photo{index}"):
                media.append(MediaFile(path, is_video=False))
    return media


async def _save_image(client: httpx.AsyncClient, url: str | None, destination: Path) -> Path | None:
    """Download one image, adding the right file extension. Returns None if it fails."""
    if not url:
        return None
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPError:
        log.warning("Could not download image %s", url)
        return None

    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in _IMAGE_EXTENSIONS:
        return None
    path = destination.with_suffix(f".{_IMAGE_EXTENSIONS[content_type]}")
    path.write_bytes(response.content)
    return path


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


def parse_open_graph(html: str) -> tuple[str, str, str | None]:
    """Read (username, caption, image link) from the preview tags on a public post page."""
    parser = _MetaTagParser()
    parser.feed(html)
    meta = parser.meta

    title = meta.get("og:title", "")
    description = meta.get("og:description", "")
    if not (title or description):
        raise ValueError("page had no readable post details")

    # The description looks like: '1,234 likes, 5 comments - username on May 1, 2025: "caption"'
    match = re.search(r"-\s*([\w.]+)\s+on\s", description)
    caption = "\n".join(part for part in (title, description) if part)
    return (match.group(1) if match else "Instagram user"), caption, meta.get("og:image")


async def _fetch_open_graph(url: str, workdir: Path) -> PostData:
    async with httpx.AsyncClient(
        headers={"User-Agent": _BROWSER_UA}, follow_redirects=True, timeout=30
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        username, caption, image_url = parse_open_graph(response.text)
        image = await _save_image(client, image_url, workdir / "photo1")

    post = PostData(url=url, username=username, caption=caption)
    return replace(post, media=[MediaFile(image, is_video=False)] if image else [])
