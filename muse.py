import os
import re
import json
from datetime import datetime

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


INSTRUCTIONS = """You match a user's description of a sports match to one event from a list of \
today's events on ESPN. Descriptions are informal: nicknames ("fever vs aces"), abbreviations \
("ind v aus"), or a sport hint ("england cricket").

Reply with the id of the single event that best matches, or null if none plausibly matches. If \
several match, prefer one that is live ("in"), then upcoming ("pre"), then finished ("post"), \
and prefer senior men's/main teams unless the description says otherwise."""

MATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["event_id"],
    "properties": {"event_id": {"type": ["string", "null"]}},
}


def _parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON in model response: {text[:200]}")
        return json.loads(match.group(0))


async def match_event(match_description, events):
    """
    Ask Muse Spark which of the given ESPN events the description refers to.

    Returns the matching event dict, or None.
    """
    if not events:
        return None

    listing = "\n".join(
        f"{e['id']} | {e['sport']} / {e['league_name']} | {e['name']} | {' vs '.join(e['teams'])} | {e['status']} | {e['date']}"
        for e in events
    )
    print(f"Asking {MODEL} to match '{match_description}' against {len(events)} events")
    resp = await client().responses.create(
        model=MODEL,
        instructions=INSTRUCTIONS,
        input=f"Now: {datetime.now().astimezone().isoformat(timespec='minutes')}\n"
              f"Description: {match_description}\n\n"
              f"Events (id | sport / league | name | teams | status | start):\n{listing}",
        reasoning={"effort": "low"},
        text={"format": {"type": "json_schema", "name": "event_match", "schema": MATCH_SCHEMA, "strict": True}},
    )
    event_id = _parse_json(resp.output_text)["event_id"]
    return next((e for e in events if e["id"] == event_id), None)
