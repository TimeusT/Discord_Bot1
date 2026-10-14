"""The Discord side: listens to chosen channels and replies with formatted places."""

from __future__ import annotations

import asyncio
import io
import logging

import discord

from src.placebot.analysis import PlaceAnalyzer
from src.placebot.config import Settings
from src.placebot.instagram import PostUnavailableError, extract_instagram_urls
from src.placebot.pipeline import build_replies
from src.placebot.transcription import Transcriber

log = logging.getLogger(__name__)

MAX_LINKS_PER_MESSAGE = 3  # protects against someone pasting dozens of links at once
MAX_PARALLEL_JOBS = 2  # transcribing is heavy, so only a couple of links run at a time


class PlaceBot(discord.Client):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # required to read the links people post
        super().__init__(intents=intents)

        self._settings = settings
        self._transcriber = Transcriber(settings.whisper_model)
        self._analyzer = PlaceAnalyzer(
            settings.anthropic_api_key, settings.anthropic_model, settings.max_places
        )
        self._limiter = asyncio.Semaphore(MAX_PARALLEL_JOBS)

    async def on_ready(self) -> None:
        log.info("Logged in as %s, watching %d channel(s)", self.user, len(self._settings.channel_ids))

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.channel.id not in self._settings.channel_ids:
            return
        for url in extract_instagram_urls(message.content)[:MAX_LINKS_PER_MESSAGE]:
            await self._handle_link(message, url)

    async def _handle_link(self, message: discord.Message, url: str) -> None:
        try:
            async with self._limiter, message.channel.typing():
                replies = await build_replies(url, self._settings, self._transcriber, self._analyzer)
        except PostUnavailableError as exc:
            await message.reply(f"⚠️ {exc}", mention_author=False)
            return
        except Exception:
            log.exception("Failed to process %s", url)
            await message.reply("⚠️ Something went wrong while reading that post.", mention_author=False)
            return

        if not replies:
            await message.reply("I couldn't find a specific place in that post.", mention_author=False)
            return

        for reply in replies:
            files = [discord.File(io.BytesIO(img.data), filename=img.filename) for img in reply.images]
            # suppress_embeds stops Discord adding its own Instagram preview under our message.
            await message.channel.send(reply.text, files=files, suppress_embeds=True)
