import os
import re
import json

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

MODEL = "muse-spark-1.3-contributor"

_client = None


def client():
    # Created lazily so the rest of the bot still runs without MUSE_API_KEY
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url="https://api.meta.ai/v1", api_key=os.getenv("MUSE_API_KEY"))
    return _client

# Match states where the score will not change again
FINAL_STATES = {"result", "abandoned"}

INSTRUCTIONS = """You report live sports scores. Use web search to find the CURRENT state of the \
match the user describes (prefer live scorecards such as Cricbuzz, ESPNcricinfo or official \
sources), then reply with a single JSON object matching the schema and nothing else.

- found: false if you cannot identify a single specific match that is live, recently finished or \
about to start. When false, other fields may be null/empty.
- innings: every innings so far, in batting order. For cricket, runs/wickets/overs are the innings \
total (overs as a string such as "42.3"). For other sports, put the team's points in runs and use \
null for wickets and overs.
- state: "upcoming", "live", "break" (innings break, lunch, tea, rain delay), "stumps", "result" \
or "abandoned".
- status_text: the short official status line, e.g. "India need 45 runs from 30 balls", \
"Australia won by 5 wickets", "Day 2: Stumps - England lead by 120 runs".
- batters: the batters currently at the crease (striker first); empty list if none.
- bowler: the current bowler; null if none.
Never guess numbers. If a value is not available, use null."""

TEAM = {
    "type": "object",
    "additionalProperties": False,
    "required": ["team", "runs", "wickets", "overs", "declared"],
    "properties": {
        "team": {"type": "string"},
        "runs": {"type": ["integer", "null"]},
        "wickets": {"type": ["integer", "null"]},
        "overs": {"type": ["string", "null"]},
        "declared": {"type": "boolean"},
    },
}

SCORE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["found", "title", "series", "state", "innings", "status_text", "batters", "bowler"],
    "properties": {
        "found": {"type": "boolean"},
        "title": {"type": ["string", "null"], "description": "e.g. 'Australia vs India, 2nd ODI'"},
        "series": {"type": ["string", "null"]},
        "state": {"type": "string", "enum": ["upcoming", "live", "break", "stumps", "result", "abandoned"]},
        "innings": {"type": "array", "items": TEAM},
        "status_text": {"type": ["string", "null"]},
        "batters": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "runs", "balls"],
                "properties": {
                    "name": {"type": "string"},
                    "runs": {"type": ["integer", "null"]},
                    "balls": {"type": ["integer", "null"]},
                },
            },
        },
        "bowler": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["name", "overs", "maidens", "runs", "wickets"],
            "properties": {
                "name": {"type": "string"},
                "overs": {"type": ["string", "null"]},
                "maidens": {"type": ["integer", "null"]},
                "runs": {"type": ["integer", "null"]},
                "wickets": {"type": ["integer", "null"]},
            },
        },
    },
}


def _parse_json(text):
    # Search-grounded answers can have a Sources list appended, so pull out the JSON object
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON in model response: {text[:200]}")
        return json.loads(match.group(0))


async def get_score(match_description):
    """
    Ask Muse Spark (with web search) for the current score of a match.

    Returns a dict matching SCORE_SCHEMA.
    """
    print(f"Asking {MODEL} for score: {match_description}")
    resp = await client().responses.create(
        model=MODEL,
        instructions=INSTRUCTIONS,
        input=f"Current score: {match_description}",
        tools=[{"type": "web_search"}],
        reasoning={"effort": "low"},
        text={"format": {"type": "json_schema", "name": "match_score", "schema": SCORE_SCHEMA, "strict": True}},
    )
    return _parse_json(resp.output_text)


def is_final(score):
    return score["state"] in FINAL_STATES


STATE_LABELS = {
    "upcoming": "🕒 Upcoming",
    "live": "🔴 LIVE",
    "break": "⏸️ Break",
    "stumps": "🌙 Stumps",
    "result": "🏁 Result",
    "abandoned": "🌧️ Abandoned",
}


def _innings_line(inn, flags):
    # Whole-word match so e.g. "India" doesn't flag "Indiana Fever"
    flag = next((f for name, f in flags.items()
                 if re.search(rf"\b{re.escape(name)}\b", inn["team"], re.IGNORECASE)), "")
    team = f"{flag} {inn['team']}".strip()
    if inn["runs"] is None:
        return f"{team}  `Yet to bat`"
    score = str(inn["runs"])
    if inn["wickets"] is not None and inn["wickets"] < 10:
        score += f"/{inn['wickets']}"
    if inn["declared"]:
        score += "d"
    if inn["overs"]:
        score += f" ({inn['overs']} ov)"
    return f"{team}  `{score}`"


def format_score(score, updated, flags=None):
    """Render a score dict as a Discord message. Always the same layout so updates don't jump around."""
    lines = [f"**{score['title'] or 'Match'}**"]
    if score["series"]:
        lines[0] += f"  ·  {score['series']}"
    lines.append(STATE_LABELS.get(score["state"], score["state"]))
    lines.append("")
    lines += [_innings_line(inn, flags or {}) for inn in score["innings"]]
    if score["status_text"]:
        lines += ["", f"*{score['status_text']}*"]

    if score["state"] == "live":
        if score["batters"]:
            batters = []
            for i, b in enumerate(score["batters"]):
                runs = "?" if b["runs"] is None else b["runs"]
                balls = f" ({b['balls']})" if b["balls"] is not None else ""
                batters.append(f"{b['name']} {runs}{'*' if i == 0 else ''}{balls}")
            lines.append(f"🏏 {'  ·  '.join(batters)}")
        bowler = score["bowler"]
        if bowler:
            figures = "-".join("?" if v is None else str(v)
                               for v in (bowler["overs"], bowler["maidens"], bowler["runs"], bowler["wickets"]))
            lines.append(f"🎯 {bowler['name']} {figures}")

    lines += ["", f"-# Updated {updated}"]
    return "\n".join(lines)
