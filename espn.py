import re
import time
import asyncio
from datetime import datetime, timedelta, timezone

import aiohttp

HEADER_URL = "https://site.web.api.espn.com/apis/v2/scoreboard/header"
SUMMARY_URL = "https://site.web.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary"

SPORT_EMOJI = {
    "cricket": "🏏",
    "basketball": "🏀",
    "football": "🏈",
    "soccer": "⚽",
    "baseball": "⚾",
    "hockey": "🏒",
    "field-hockey": "🏑",
    "golf": "⛳",
    "tennis": "🎾",
    "volleyball": "🏐",
    "rugby": "🏉",
    "rugby-league": "🏉",
    "australian-football": "🏉",
    "lacrosse": "🥍",
    "mma": "🥊",
    "racing": "🏎️",
}

# Statuses where the match is in progress but nothing is happening
PAUSED = {"stumps", "lunch", "tea", "dinner", "drinks", "innings break", "halftime", "rain delay"}

# Multi-day cricket: later days usually start at the same time of day as day 1
DAY_START_EARLY = timedelta(minutes=30)
PLAY_WINDOW = timedelta(hours=6)
DELAYED_START_POLL = timedelta(minutes=10)

# Scoreboards searched when looking up a match. The bare header only has featured leagues,
# so also pull full lists for the sports people are most likely to ask about.
CANDIDATE_QUERIES = [
    {},
    {"sport": "cricket"},
    {"sport": "soccer"},
    {"sport": "football", "league": "nfl"},
    {"sport": "football", "league": "college-football"},
    {"sport": "basketball", "league": "nba"},
    {"sport": "basketball", "league": "wnba"},
    {"sport": "baseball", "league": "mlb"},
    {"sport": "hockey", "league": "nhl"},
]


async def _fetch_header(session, params):
    async with session.get(HEADER_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


def _events(header):
    """Flatten a header response into (sport, league, event) tuples."""
    for sport in header.get("sports", []):
        for league in sport.get("leagues", []):
            for event in league.get("events", []):
                if event.get("competitors"):
                    yield sport["slug"], league, event


async def list_events():
    """All of today's events ESPN knows about, deduplicated by event id."""
    async with aiohttp.ClientSession() as session:
        headers = await asyncio.gather(*(_fetch_header(session, q) for q in CANDIDATE_QUERIES),
                                       return_exceptions=True)
    errors = [h for h in headers if isinstance(h, Exception)]
    if len(errors) == len(headers):
        raise RuntimeError(f"Couldn't reach ESPN: {errors[0]}")

    events = {}
    for header in headers:
        if isinstance(header, Exception):
            print(f"Error fetching ESPN scoreboard: {header}")
            continue
        for sport, league, event in _events(header):
            events.setdefault(event["id"], {
                "id": event["id"],
                "sport": sport,
                # Some cricket leagues have an empty slug, and the scoreboard takes the id instead
                "league": league.get("slug") or league["id"],
                "league_name": league.get("shortName") or league.get("name"),
                "name": event["name"],
                "date": event.get("date"),
                "status": event.get("status"),
                "teams": [c.get("displayName") for c in event["competitors"]],
            })
    return list(events.values())


async def get_event(sport, league, event_id):
    """Fetch the latest state of one event, or None if it's no longer on the scoreboard."""
    async with aiohttp.ClientSession() as session:
        header = await _fetch_header(session, {"sport": sport, "league": league})
        for sport_slug, league_info, event in _events(header):
            if event["id"] == event_id:
                event["sport"] = sport_slug
                event["league_name"] = league_info.get("shortName") or league_info.get("name")
                if sport_slug == "cricket" and event.get("status") == "in":
                    try:
                        event["cricket_players"] = await _cricket_players(session, league, event_id)
                    except Exception as e:
                        # Nice to have; the score still shows without it
                        print(f"Error fetching cricket players for {event_id}: {e}")
                return event
    return None


def _current_innings_stats(player):
    """A player's stats for the latest innings they've batted or bowled in, as {name: displayValue}."""
    periods = sorted(player.get("linescores") or [], key=lambda l: l.get("period", 0))
    if not periods:
        return {}
    stats = {}
    for line in periods[-1].get("linescores", []):
        for category in line.get("statistics", {}).get("categories", []):
            for stat in category.get("stats", []):
                stats[stat["name"]] = stat.get("displayValue")
    return stats


async def _cricket_players(session, league, event_id):
    """Who's batting and bowling right now, from ESPN's match summary."""
    url = SUMMARY_URL.format(sport="cricket", league=league)
    async with session.get(url, params={"event": event_id}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        resp.raise_for_status()
        summary = await resp.json(content_type=None)
    players = {}
    for roster in summary.get("rosters", []):
        for player in roster.get("roster", []):
            role = player.get("activeName")
            if role in ("striker", "non-striker", "current bowler", "previous bowler"):
                athlete = player.get("athlete", {})
                players[role] = {
                    "name": athlete.get("displayName") or athlete.get("name"),
                    "stats": _current_innings_stats(player),
                }
    return players


def _batter(player, on_strike):
    s = player["stats"]
    return f"{player['name']}{'*' if on_strike else ''} {s.get('runs', 0)} ({s.get('ballsFaced', 0)})"


def _bowler(player):
    s = player["stats"]
    # Cricket's usual overs-maidens-runs-wickets
    return f"{player['name']} {s.get('overs', 0)}-{s.get('maidens', 0)}-{s.get('conceded', 0)}-{s.get('wickets', 0)}"


def _cricket_lines(players):
    lines = []
    batters = [_batter(players[r], r == "striker") for r in ("striker", "non-striker") if r in players]
    if batters:
        lines.append("🏏 " + " · ".join(batters))
    bowlers = [_bowler(players[r]) for r in ("current bowler", "previous bowler") if r in players]
    if bowlers:
        lines.append("🔴 " + " · ".join(bowlers))
    return lines


def is_final(event):
    return event.get("status") == "post"


def _is_stumps(event):
    return (event.get("fullStatus") or {}).get("type", {}).get("description") == "Stumps"


def next_poll_time(event, now=None):
    """
    When to poll next for a multi-day match at stumps, so we don't poll overnight.

    Returns a UTC datetime, or None to poll at the normal interval.
    """
    if not _is_stumps(event) or not event.get("date"):
        return None
    now = now or datetime.now(timezone.utc)
    first_day_start = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
    day_start = datetime.combine(now.date(), first_day_start.timetz())
    if now > day_start + PLAY_WINDOW:
        day_start += timedelta(days=1)
    wake = day_start - DAY_START_EARLY
    if wake > now:
        return wake
    # Past the usual start time but still stumps, so probably a delayed start
    return now + DELAYED_START_POLL


def _status_line(event):
    detail = event.get("summary") or ""
    if event.get("status") == "pre" and event.get("date"):
        # ESPN's summary has the start in US Eastern; a Discord timestamp shows in each viewer's own time zone
        start = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        detail = f"<t:{int(start.timestamp())}:R>"  # relative, e.g. "in 3 hours"
    label = {"pre": "🕒 Upcoming", "in": "🔴 LIVE", "post": "🏁 Final"}.get(event.get("status"), "")
    if event.get("status") == "in" and detail.lower() in PAUSED:
        label, detail = f"⏸️ {detail}", ""
    if event.get("status") == "post" and detail in ("Final", "Result"):
        detail = ""
    return " · ".join(part for part in (label, detail) if part)


def _team_line(competitor, flags):
    name = competitor.get("displayName") or competitor.get("name")
    # Whole-word match so e.g. "India" doesn't flag "Indiana Fever"
    flag = next((f for country, f in flags.items()
                 if re.search(rf"\b{re.escape(country)}\b", name, re.IGNORECASE)), "")
    team = f"{flag} {name}".strip()
    score = competitor.get("score")
    if not score:
        return team
    if competitor.get("winner"):
        return f"{team}  **`{score}`**"
    return f"{team}  `{score}`"


def format_score(event, flags=None, next_poll=None):
    """Render an ESPN event as a Discord message. Always the same layout so updates don't jump around."""
    title = f"{SPORT_EMOJI.get(event.get('sport'), '🏆')} **{event['name']}**"
    context = [event.get("league_name"), event.get("note") or event.get("title")]
    context = " · ".join(c for c in context if c)
    if context:
        title += f"  ·  {context}"

    lines = [title, _status_line(event), ""]

    # Away team first, matching "Away at Home" naming
    competitors = sorted(event["competitors"], key=lambda c: c.get("homeAway") != "away")
    lines += [_team_line(c, flags or {}) for c in competitors]

    players = _cricket_lines(event.get("cricket_players") or {})
    if players:
        lines += [""] + players

    full_status = event.get("fullStatus") or {}
    note = full_status.get("longSummary") or event.get("seriesSummary")
    if note:
        lines += ["", f"*{note}*"]

    # Discord timestamps show in each viewer's own time zone; "R" is relative ("2 minutes ago")
    footer = f"-# Updated <t:{int(time.time())}:R>"
    if next_poll:
        footer += f" · next update ~<t:{int(next_poll.timestamp())}:t>"
    lines += ["", footer]
    return "\n".join(lines)
