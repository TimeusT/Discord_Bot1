# PlaceBot

A Discord bot that turns Instagram travel posts into tidy, easy-to-read place summaries.

Paste an Instagram link intow a chosen channel and the bot replies with the place's name, location, categories, a booking link, the original poster, a short "What to expect" list, and up to 3 images.

## How it works

```
Instagram link posted in the channel
  -> read the post (caption, username, images, audio if it's a video)
  -> turn the audio into text (a transcript)
  -> Claude reads the caption + transcript and picks out the place details
  -> work out the booking link (Trip.com for Asia, Booking.com elsewhere)
  -> post the formatted message with images
```

## Project layout

```
Discord_Bot1/
├── src/placebot/
│   ├── __main__.py       Starts the bot (python -m placebot)
│   ├── bot.py            Discord side: listens to channels, sends replies
│   ├── pipeline.py       Runs the steps above for one link
│   ├── instagram.py      Finds links in messages, reads posts, downloads images
│   ├── transcription.py  Audio -> text (runs on your own computer)
│   ├── analysis.py       Asks Claude for the place details
│   ├── links.py          Trip.com vs Booking.com logic
│   ├── formatter.py      Builds the final Discord message layout
│   ├── models.py         Simple data containers (Place, PostData, Category)
│   └── config.py         Reads your settings from .env
├── tests/                Automatic checks for the logic above
├── .env.example          Template for your private settings
└── pyproject.toml        Project details and the list of libraries used
```

## Setup (first time)

### 1. Install Python
Install Python 3.11 or newer from <https://www.python.org/downloads/>. On Windows, tick **"Add Python to PATH"** in the installer.

### 2. Create the Discord bot
1. Go to <https://discord.com/developers/applications> and click **New Application**.
2. Open the **Bot** tab. Under **Privileged Gateway Intents**, turn on **Message Content Intent** (the bot can't read links without it) and save.
3. Click **Reset Token** and copy the token. This is your `DISCORD_TOKEN`. Treat it like a password.
4. Open **OAuth2 → URL Generator**. Tick the scope `bot`, then the permissions **View Channels**, **Send Messages**, **Read Message History** and **Attach Files**.
5. Open the generated URL and add the bot to your server.

### 3. Get the channel ID
In Discord go to **Settings → Advanced** and turn on **Developer Mode**. Right-click the channel the bot should watch and choose **Copy Channel ID**.

### 4. Get an Anthropic API key
Create one at <https://console.anthropic.com>. The default model (`claude-haiku-5-5`) is the cheapest option and is plenty for this job.

### 5. Install the bot
Open a terminal in this folder and run:

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Mac / Linux:  source .venv/bin/activate
pip install -e ".[dev]"
```

### 6. Add your settings
Copy `.env.example` to a new file called `.env` and fill in the three required values (token, channel ID, API key).

### 7. Run it
```bash
python -m placebot
```
You should see "Logged in as ..." in the terminal. Post an Instagram link in your channel to try it. The first video you post is slower because the speech-to-text model downloads once.

The bot only works while this command is running. To keep it online around the clock you will later need to host it on an always-on computer or service.

## Troubleshooting

| Problem | Fix |
|---|---|
| "I couldn't read that Instagram post" | Instagram sometimes blocks bots. First run `pip install -U yt-dlp` (Instagram changes often). If it still fails, export your Instagram cookies to a file and set `INSTAGRAM_COOKIES_FILE` in `.env`. |
| Bot is online but ignores links | Check **Message Content Intent** is on, and that the channel ID is in `DISCORD_CHANNEL_IDS`. |
| "Setup problem: Missing in .env" | A required value in `.env` is empty. |

## Changing things

- **Which countries use Trip.com:** edit `ASIA_COUNTRY_CODES` in `links.py`.
- **Message layout:** everything is in `format_place` in `formatter.py`.
- **How the AI picks details and categories:** edit the instructions at the top of `analysis.py`.

## Running the tests

```bash
pytest
```
