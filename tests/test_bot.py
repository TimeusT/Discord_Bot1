from src.placebot.bot import PlaceBot
from src.placebot.config import Settings


def test_change_channel_command_is_registered_for_servers_only(tmp_path):
    bot = PlaceBot(Settings(discord_token="x", anthropic_api_key="y", data_dir=tmp_path))
    (command,) = bot.tree.get_commands()
    assert command.name == "change-channel"
    assert command.guild_only
    assert command.default_permissions.manage_guild
