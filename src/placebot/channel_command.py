"""The /change-channel command: a channel picker for choosing where the bot listens."""

from __future__ import annotations

import discord
from discord import app_commands

from src.placebot.channels import ChannelStore

_PICKABLE_TYPES = [discord.ChannelType.text, discord.ChannelType.news]
_MAX_CHOICES = 25  # Discord's limit for one picker menu


class ChannelPicker(discord.ui.View):
    """A multi-select menu of the server's channels. Each choice is saved straight away."""

    def __init__(self, store: ChannelStore, guild_id: int, current_ids: list[int]) -> None:
        super().__init__(timeout=300)
        self._store = store
        self._guild_id = guild_id
        # Pre-tick the channels that are already chosen.
        self.picker.default_values = [
            discord.SelectDefaultValue(id=channel_id, type=discord.SelectDefaultValueType.channel)
            for channel_id in current_ids
        ]

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=_PICKABLE_TYPES,
        min_values=0,
        max_values=_MAX_CHOICES,
        placeholder="Pick the channels to watch",
    )
    async def picker(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect) -> None:
        self._store.set(self._guild_id, [channel.id for channel in select.values])
        await interaction.response.edit_message(content=_summary(select.values), view=self)


def _summary(channels: list) -> str:
    if not channels:
        return "⚠️ No channels chosen, so I'll ignore all messages until you pick at least one."
    return "✅ Saved. I'm now watching: " + ", ".join(channel.mention for channel in channels)


def register_channel_command(tree: app_commands.CommandTree, store: ChannelStore) -> None:
    @tree.command(name="change-channel", description="Choose which channels the bot reads Instagram links in")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)  # hides it from regular members
    async def change_channel(interaction: discord.Interaction) -> None:
        # Hiding the command isn't enough on its own: server owners can change who sees it.
        if not interaction.permissions.manage_guild:
            await interaction.response.send_message(
                "You need the **Manage Server** permission to change this.", ephemeral=True
            )
            return

        guild = interaction.guild
        # Only pre-tick channels that still exist, in case one was deleted.
        current = [cid for cid in sorted(store.get(guild.id)) if guild.get_channel(cid)]
        view = ChannelPicker(store, guild.id, current[:_MAX_CHOICES])

        intro = (
            "Choose the channels I should read Instagram links in. Ticked channels are watched:"
            if current
            else "I'm not watching any channel yet. Choose the channels I should read Instagram links in:"
        )
        await interaction.response.send_message(intro, view=view, ephemeral=True)
