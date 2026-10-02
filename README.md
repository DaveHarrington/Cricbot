# Cricbot

A Discord bot for live sports scores: cricket first, but anything on ESPN's scoreboard works (WNBA, NFL, soccer, ...).

## Commands

- `/live_score <match>`: post the current score of a match, e.g. `/live_score fever vs aces` or `/live_score india`.
- `/subscribe <match>`: post and pin a message that updates with the live score every 30s until the match ends.
  Multi-day cricket matches pause overnight at stumps and pick up shortly before the next day's play.
- `/list_subscribed`, `/unsubscribe <number>`: manage the subscriptions in the current channel.
- `/help`

## How scores work

- `espn.py` reads ESPN's free scoreboard API (`site.web.api.espn.com/apis/v2/scoreboard/header`) and formats the Discord message.
- `muse.py` asks `muse-spark-1.3-contributor` (Meta Model API) which of today's ESPN events a description like "fever vs aces" means.
  It's only used once per command; updates poll ESPN directly.
- Subscriptions are saved to `subscriptions.json` and resumed when the bot restarts.

## Setup

Requires Python 3.14 (see `.python-version`).

Add these to `.env`:

- `DISCORD_TOKEN="<token>"` from https://discord.com/developers/applications.
  The bot needs Send Messages, Read Message History and Manage Messages (to pin) in the channels it's used in.
- `MUSE_API_KEY="<key>"` from https://dev.meta.ai

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
