"""The Discord side: listens to chosen channels and replies with formatted places."""

from __future__ import annotations

import asyncio
import io
import logging

import discord
from discord import app_commands

from src.placebot.analysis import PlaceAnalyzer
from src.placebot.channel_command import register_channel_command
from src.placebot.channels import ChannelStore
from src.placebot.config import Settings
from src.placebot.instagram import PostUnavailableError, extract_instagram_urls
from src.placebot.media import batch_attachments
from src.placebot.pipeline import build_replies
from src.placebot.transcription import Transcriber

log = logging.getLogger(__name__)

MAX_LINKS_PER_MESSAGE = 3  # protects against someone pasting dozens of links at once
MAX_PARALLEL_JOBS = 2  # transcribing is heavy, so only a couple of links run at a time
UPLOAD_SAFETY_MARGIN = 0.95  # stay a little under the server's upload limit


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

        self._channels = ChannelStore(settings.data_dir / "channels.json")
        self.tree = app_commands.CommandTree(self)
        register_channel_command(self.tree, self._channels)

    async def setup_hook(self) -> None:
        await self.tree.sync()  # makes /change-channel appear in Discord

    async def on_ready(self) -> None:
        log.info("Logged in as %s", self.user)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        if not self._channels.is_watched(message.guild.id, message.channel.id):
            return
        for url in extract_instagram_urls(message.content)[:MAX_LINKS_PER_MESSAGE]:
            await self._handle_link(message, url)

    async def _handle_link(self, message: discord.Message, url: str) -> None:
        upload_limit = int(message.guild.filesize_limit * UPLOAD_SAFETY_MARGIN)
        try:
            async with self._limiter, message.channel.typing():
                replies = await build_replies(
                    url, self._settings, self._transcriber, self._analyzer, upload_limit
                )
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
            # A big carousel may not fit in one message, so extra files follow in later messages.
            first, *rest = batch_attachments(reply.attachments, upload_limit) or [[]]
            await self._send(message.channel, reply.text, first)
            for batch in rest:
                await self._send(message.channel, None, batch)

    @staticmethod
    async def _send(channel: discord.abc.Messageable, text: str | None, attachments: list) -> None:
        files = [discord.File(io.BytesIO(a.data), filename=a.filename) for a in attachments]
        # suppress_embeds stops Discord adding its own Instagram preview under our message.
        await channel.send(text, files=files, suppress_embeds=True)
