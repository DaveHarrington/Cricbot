import os
import json
import asyncio
import traceback
from datetime import datetime, timezone

from dotenv import load_dotenv

import discord
from discord import app_commands
from discord.ext import commands

import espn
import muse

load_dotenv()

REFRESH_INT_S = 30
# Sports whose scores change fast enough to be worth polling more often
SPORT_REFRESH_INT_S = {"basketball": 5}
MAX_RETRY_BACKOFF_S = 600
SUBSCRIPTIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscriptions.json")

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

team_flags = {
    "Afghanistan": ":flag_af:",
    "Australia": ":flag_au:",
    "Bangladesh": ":flag_bd:",
    "England": ":england:",
    "India": ":flag_in:",
    "Ireland": ":four_leaf_clover:",
    "New Zealand": ":flag_nz:",
    "Pakistan": ":flag_pk:",
    "South Africa": ":flag_za:",
    "Sri Lanka": ":flag_lk:",
    "West Indies": ":palm_tree:",
    "Zimbabwe": ":flag_zw:",
    "Namibia": ":flag_na:",
    "Scotland": ":scotland:",
    "Netherlands": ":flag_nl:",
    "United States of America": ":flag_us:",
    "Oman": ":flag_om:",
    "United Arab Emirates": ":flag_ae:",
    "Nepal": ":flag_np:",
    "Canada": ":flag_ca:",
    "Hong Kong": ":flag_hk:",
    "Malaysia": ":flag_my:",
    "Papua New Guinea": ":flag_pg:"
}

bot = commands.Bot(command_prefix='/', intents=discord.Intents.all())

# Active subscriptions: message id -> (task, comment, event, match_description)
subscribed_tasks = {}

@bot.event
async def on_guild_join(guild):
    await update_activity()


@bot.event
async def on_guild_remove(guild):
    await update_activity()


async def update_activity():
    activity = discord.Activity(
        type=discord.ActivityType.watching, name=f"Cricket in {len(bot.guilds)} servers")
    await bot.change_presence(status=discord.Status.online, activity=activity)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    await resume_subscriptions()
    await update_activity()
    try:
        await bot.tree.sync()
    except Exception as e:
        print(f"Error syncing commands: {e}")

# livescore

async def find_event(match_description):
    """Match a free-text description to one of today's ESPN events."""
    return await muse.match_event(match_description, await espn.list_events())


@bot.tree.command(name="live_score", description="Get the current score of a match")
@app_commands.describe(match_description="Match Description (e.g., 'india', 'fever vs aces')")
async def live_score(interaction: discord.Interaction, match_description: str):
    # Matching takes a few seconds, longer than Discord's 3s limit to respond
    await interaction.response.defer()
    try:
        event = await find_event(match_description)
        score = event and await espn.get_event(event["sport"], event["league"], event["id"])
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Couldn't look up '{match_description}': {e}")
        return

    if not score:
        await interaction.followup.send(f"No match found on ESPN for '{match_description}'")
        return

    await interaction.followup.send(espn.format_score(score, team_flags))


# help


@bot.tree.command(name="help", description="Display all Commands")
async def help_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=discord.Embed(title="Stay in the game with Cricbot: Your LIVE cricket score companion!",
                            description=f"**Cricbot is used in over `{len(bot.guilds)}` servers, where cricket fans from all over the world always stay in the game.\n\nCommands:\n\n`/live_score` to get the current score of a match.\n\n`/subscribe` to pin a message that keeps updating with the live score.\n\n`/list_subscribed` and `/unsubscribe` to manage this channel's subscriptions.\n\n`/help` to display this message.**", color=discord.Color.random())
    )


async def subscribe_to_score(match_description, event, comment):
    try:
        await _subscribe_to_score(match_description, event, comment)
    except Exception as e:
        print(f"Error in _subscribe_to_score: {e}")
        traceback.print_exc()
        try:
            await comment.edit(content=f"¯\\_(ツ)_/¯ Fuck: {e}")
        except Exception as edit_error:
            print(f"Error showing subscription error: {edit_error}")
        await delete_subscription_inner(comment.id)

async def _subscribe_to_score(match_description, event, comment):
    failures = 0
    while True:
        start_time = datetime.now()
        try:
            keep_running, next_poll = await _subscribe_to_score_inner(match_description, event, comment)
            failures = 0
        except (discord.NotFound, discord.Forbidden):
            # Message deleted or we lost access to it, so there's nothing left to update
            raise
        except Exception as e:
            # Probably ESPN or Discord having a moment; keep trying so outages don't end the subscription
            failures += 1
            sleep_time = min(5 * 2 ** failures, MAX_RETRY_BACKOFF_S)
            print(f"Error updating {match_description} (failure {failures}), retrying in {sleep_time}s: {e}")
            await asyncio.sleep(sleep_time)
            continue

        if not keep_running:
            break

        if next_poll:
            sleep_time = max((next_poll - datetime.now(timezone.utc)).total_seconds(), 10)
        else:
            elapsed_time = (datetime.now() - start_time).total_seconds()
            refresh_interval = SPORT_REFRESH_INT_S.get(event["sport"], REFRESH_INT_S)
            sleep_time = max(refresh_interval - elapsed_time, 1)
        print(f"sleeping for {sleep_time} seconds")
        await asyncio.sleep(sleep_time)

    await delete_subscription_inner(comment.id)

async def _subscribe_to_score_inner(match_description, event, comment):
    print(f"in subscribe to score {match_description}: {event['sport']}/{event['league']} {event['id']}")
    score = await espn.get_event(event["sport"], event["league"], event["id"])

    if not score:
        await comment.edit(content=f"No score found for '{match_description}'")
        return False, None

    print("updating with new score")
    next_poll = espn.next_poll_time(score)
    await comment.edit(content=espn.format_score(score, team_flags, next_poll))

    return not espn.is_final(score), next_poll

@bot.tree.command(name="subscribe", description="Subscribe to live score updates")
@app_commands.describe(match_description="Match Description (e.g., 'Australia vs India cricket')")
async def subscribe(interaction: discord.Interaction, match_description: str):
    print(f"Subscribe!: {match_description}")
    await interaction.response.send_message(f"Getting score for '{match_description}'")
    comment = await interaction.original_response()

    try:
        event = await find_event(match_description)
        if not event:
            await comment.edit(content=f"No match found on ESPN for '{match_description}'")
            return

        print(f"Found event: {event}")
        # Interaction tokens expire after 15 minutes, so edit the message as a normal channel message
        comment = await interaction.channel.fetch_message(comment.id)
        await comment.edit(content=f"Found {event['name']}. Will start updating.")
    except Exception as e:
        traceback.print_exc()
        await comment.edit(content=f"Couldn't subscribe to '{match_description}': {e}")
        return

    try:
        await comment.pin()
    except Exception as e:
        print(f"Error pinning comment: {e}")

    start_subscription(match_description, event, comment)

def start_subscription(match_description, event, comment):
    task = bot.loop.create_task(subscribe_to_score(match_description, event, comment))
    subscribed_tasks[comment.id] = task, comment, event, match_description
    save_subscriptions()

def save_subscriptions():
    data = {
        str(message_id): {"description": match_description, "channel_id": comment.channel.id,
                          "message_id": message_id, "event": event}
        for message_id, (_, comment, event, match_description) in subscribed_tasks.items()
    }
    try:
        # Write then rename so a crash mid-write can't leave a truncated file
        tmp_file = SUBSCRIPTIONS_FILE + ".tmp"
        with open(tmp_file, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_file, SUBSCRIPTIONS_FILE)
    except Exception as e:
        print(f"Error saving subscriptions: {e}")

def load_subscriptions():
    try:
        with open(SUBSCRIPTIONS_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error loading subscriptions: {e}")
        return {}

async def resume_subscriptions():
    # on_ready fires again on reconnect, so skip anything already running
    for key, sub in load_subscriptions().items():
        # Older files were keyed by description
        match_description = sub.get("description", key)
        if sub["message_id"] in subscribed_tasks:
            continue
        try:
            channel = bot.get_channel(sub["channel_id"]) or await bot.fetch_channel(sub["channel_id"])
            comment = await channel.fetch_message(sub["message_id"])
        except Exception as e:
            print(f"Dropping subscription for {match_description}, can't find its message: {e}")
            continue
        print(f"Resuming subscription for {match_description}")
        start_subscription(match_description, sub["event"], comment)
    # Persist any dropped subscriptions
    save_subscriptions()

@bot.tree.command(name="list_subscribed", description="List all current score subscriptions")
async def list_subscribed(interaction: discord.Interaction):
    subscriptions = channel_subscriptions(interaction.channel_id)
    if subscriptions:
        subscribed_list = "\n".join(
            f"{index + 1}. {match_description}" for index, (_, match_description) in enumerate(subscriptions)
        )
        await interaction.response.send_message(f"Current subscriptions:\n{subscribed_list}")
    else:
        await interaction.response.send_message("No current subscriptions in this channel")

def channel_subscriptions(channel_id):
    """(message id, description) for each subscription in a channel, oldest first."""
    return [(message_id, match_description)
            for message_id, (_, comment, _, match_description) in subscribed_tasks.items()
            if comment.channel.id == channel_id]

@bot.tree.command(name="unsubscribe", description="Unsubscribe from a score update")
@app_commands.describe(subscription_number="Subscription number")
async def unsubscribe(interaction: discord.Interaction, subscription_number: int):
    subscriptions = channel_subscriptions(interaction.channel_id)
    if not 1 <= subscription_number <= len(subscriptions):
        await interaction.response.send_message(f"No subscription #{subscription_number}, see /list_subscribed")
        return

    message_id, match_description = subscriptions[subscription_number - 1]
    await delete_subscription_inner(message_id)
    await interaction.response.send_message(f"Unsubscribed from '{match_description}'")

async def delete_subscription_inner(message_id):
    if message_id in subscribed_tasks:
        task, comment, _, match_description = subscribed_tasks[message_id]
        print(f"Deleting subscription for {match_description}")
        try:
            await comment.unpin()
        except Exception as e:
            print(f"Error unpinning comment: {e}")

        try:
            task.cancel()
        except Exception as e:
            print(f"Error deleting subscription: {e}")

        del subscribed_tasks[message_id]
        save_subscriptions()

bot.run(DISCORD_TOKEN)
