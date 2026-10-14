"""Remembers which channels the bot watches in each server, saved in a small file."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from pathlib import Path

log = logging.getLogger(__name__)


class ChannelStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._channels: dict[str, list[int]] = self._load()

    def get(self, guild_id: int) -> frozenset[int]:
        return frozenset(self._channels.get(str(guild_id), ()))

    def is_watched(self, guild_id: int, channel_id: int) -> bool:
        return channel_id in self._channels.get(str(guild_id), ())

    def set(self, guild_id: int, channel_ids: Iterable[int]) -> None:
        self._channels[str(guild_id)] = sorted(set(channel_ids))
        self._save()

    def _load(self) -> dict[str, list[int]]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return {str(guild): [int(channel) for channel in ids] for guild, ids in raw.items()}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, TypeError, AttributeError):
            # A damaged file shouldn't stop the bot starting; channels just need choosing again.
            log.exception("Could not read %s; starting with no channels chosen", self._path)
            return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._channels, indent=2), encoding="utf-8")
        # Swapping the finished file in is atomic, so a crash can't leave a half-written one.
        os.replace(temporary, self._path)
