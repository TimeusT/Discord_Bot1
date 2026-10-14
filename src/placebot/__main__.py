"""Start the bot with:  python -m placebot"""

import logging

from src.placebot.bot import PlaceBot
from src.placebot.config import ConfigError, Settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        raise SystemExit(f"Setup problem: {exc}") from None

    # log_handler=None lets our logging setup above handle discord.py's logs too.
    PlaceBot(settings).run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
