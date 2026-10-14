# PlaceBot

A Discord bot that turns Instagram travel posts into tidy, easy-to-read place summaries.

Paste an Instagram link into a watched channel and the bot replies with the place's name, location, category, the original poster, a short "What to expect" list, and the post's actual video or photos.

## How it works

```
Instagram link posted in a watched channel
  -> read the post (caption, @username, and download its video / photos)
  -> turn the video's speech into text (a transcript)
  -> Claude reads the caption + transcript and picks out the place details
  -> post the formatted message with the video / photos attached
```

Videos too big for the server's upload limit are shrunk automatically (needs ffmpeg, see below). If one still can't fit, the message says so and the post link is there to open.

## Project layout

```
Discord_Bot1/
├── src/placebot/
│   ├── __main__.py         Starts the bot (python -m placebot)
│   ├── bot.py              Discord side: listens to channels, sends replies
│   ├── channel_command.py  The /change-channel command and its channel picker
│   ├── channels.py         Remembers the chosen channels (saved in data/channels.json)
│   ├── pipeline.py         Runs the steps above for one link
│   ├── instagram.py        Finds links in messages, reads posts, downloads media
│   ├── media.py            Shrinks big videos, splits files across messages
│   ├── transcription.py    Speech -> text (runs on your own computer)
│   ├── analysis.py         Asks Claude for the place details and categories
│   ├── formatter.py        Builds the final Discord message layout
│   ├── models.py           Simple data containers (Place, PostData, Category)
│   └── config.py           Reads your settings from .env
├── tests/                  Automatic checks for the logic above
├── Dockerfile, docker-compose.yml, .dockerignore   For running 24/7 (see below)
├── .env.example            Template for your private settings
└── pyproject.toml          Project details and the list of libraries used
```

## Setup (first time)

### 1. Install Python
Install Python 3.11 or newer from <https://www.python.org/downloads/>. On Windows, tick **"Add Python to PATH"** in the installer.

### 2. Create the Discord bot
1. Go to <https://discord.com/developers/applications> and click **New Application**.
2. Open the **Bot** tab. Under **Privileged Gateway Intents**, turn on **Message Content Intent** (the bot can't read links without it) and save.
3. Click **Reset Token** and copy the token. This is your `DISCORD_TOKEN`. Treat it like a password.
4. Open **OAuth2 → URL Generator**. Tick the scopes **`bot`** and **`applications.commands`** (the second one is needed for the `/change-channel` command). Then tick the permissions **View Channels**, **Send Messages**, **Read Message History** and **Attach Files**.
5. Open the generated URL and add the bot to your server. If the bot is already in your server, open the new URL anyway: it updates the bot's permissions without removing it.

### 3. Get an Anthropic API key
Create one at <https://console.anthropic.com>. The default model (`claude-haiku-5-5`) is the cheapest option and is plenty for this job.

### 4. Install the bot
Open a terminal in this folder and run:

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Mac / Linux:  source .venv/bin/activate
pip install -e ".[dev]"
```

### 5. Add your settings
Copy `.env.example` to a new file called `.env` and fill in the two required values (Discord token and Anthropic API key).

### 6. Run it
```bash
python -m placebot
```
You should see "Logged in as ..." in the terminal. The first video you post is slower because the speech-to-text model downloads once.

### 7. Choose the channels
In your server, type **`/change-channel`**. A menu of your channels appears: tick the ones the bot should read Instagram links in. Each choice is saved as soon as you make it, and you can run the command again whenever you want to change it. The first time, it can take a few minutes for the command to show up in Discord.

- Only people with the **Manage Server** permission can use it.
- Until you pick at least one channel, the bot ignores every message.
- Each server has its own list.

### Optional: install ffmpeg
ffmpeg lets the bot shrink videos that are over your server's upload limit (10 MB on servers without boosts). Without it, big videos are skipped with a note. Get it from <https://ffmpeg.org/download.html> (on Windows, `winget install ffmpeg` also works), then restart the bot. The Docker setup below includes it already.

## Keeping it online 24/7

The bot only replies while the program is running, so for 24/7 it has to run on a computer that is always on:

- **A rented server (VPS):** the most reliable choice, usually a few dollars a month. Pick Linux with at least 2 GB of RAM, because the speech-to-text model needs memory.
- **A computer at home** (spare laptop, mini PC, Raspberry Pi) left on: no rental cost, and Instagram is less likely to block a home internet connection.
- **Container hosting services** can also run the Dockerfile. If you use one, attach a persistent storage volume at `/data` so your channel choices are not lost on restart.

### Running it with Docker
On the always-on computer, install Docker, copy this project folder onto it, then run these commands inside the folder:

```bash
cp .env.example .env        # then edit .env and fill in your two keys
docker compose up -d --build
docker compose logs -f      # watch it start (Ctrl+C stops watching, not the bot)
```

The bot now restarts by itself after a crash or reboot. Your channel choices and the speech model are kept in a Docker volume, so updates don't lose them.

To update after changing the code: `docker compose up -d --build`.
Instagram changes often, so about once a month also refresh the video-downloading library: `docker compose build --pull --no-cache && docker compose up -d`.

**Heads up:** Instagram is stricter with rented servers than with home connections. If posts that worked on your own computer start failing on the server, use an Instagram cookies file (see Troubleshooting).

## Troubleshooting

| Problem | Fix |
|---|---|
| "I couldn't read that Instagram post" | Instagram sometimes blocks bots. First run `pip install -U yt-dlp` (Instagram changes often). If it still fails, export your Instagram cookies to a file (a browser extension that exports `cookies.txt` works) and set `INSTAGRAM_COOKIES_FILE` in `.env`. Cookies expire, so repeat this if it stops working. |
| `/change-channel` doesn't appear | Re-add the bot using an invite link that includes the `applications.commands` scope (step 2.4), then wait a few minutes. |
| Bot is online but ignores links | Run `/change-channel` and tick the channel. Also check **Message Content Intent** is on. |
| "Setup problem: Missing in .env" | A required value in `.env` is empty. |
| A video didn't upload | It was over the server's upload limit and couldn't be shrunk enough (very long, or ffmpeg isn't installed). |

## Changing things

- **Message layout:** everything is in `format_place` in `formatter.py`.
- **How the AI picks details:** edit the instructions at the top of `analysis.py`.
- **How strict category choosing is:** every place gets one main category, and a second only if it is a strong match too. Change `SECONDARY_CATEGORY_MIN_SCORE` in `analysis.py` (0.6 now): raise it for fewer second categories, lower it for more.

## Running the tests

```bash
pytest
```
