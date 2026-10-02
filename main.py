import os
import json
import asyncio
import traceback
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

import discord
from discord import app_commands
from discord.ext import commands

import espn
import muse

load_dotenv()

REFRESH_INT_S = 30
MAX_RETRY_BACKOFF_S = 600
SUBSCRIPTIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscriptions.json")

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RAPID_API_KEY = os.getenv('RAPID_API_KEY')

team_flag_mapping_2 = {
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

# Global dictionary to store tasks: match_description -> (task, comment, event)
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
    await update_activity()
    await bot.tree.sync()
    await resume_subscriptions()

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

    await interaction.followup.send(espn.format_score(score, datetime.now().strftime('%H:%M:%S'), team_flag_mapping_2))


# help


@bot.tree.command(name="help", description="Display all Commands")
async def help_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=discord.Embed(title="Stay in the game with Cricbot: Your LIVE cricket score companion!",
                            description=f"**Cricbot is used in over `{len(bot.guilds)}` servers, where cricket fans from all over the world always stay in the game.\n\nCommands:\n\n`/live_score` to get the current score of a match.\n\n`/subscribe` to pin a message that keeps updating with the live score.\n\n`/list_subscribed` and `/unsubscribe` to manage those.\n\n`/batters_rankings` to get latest ICC rankings of top 10 batters.\n\n`/bowlers_rankings` to get latest ICC rankings of top 10 bowlers.\n\n`/allrounders_rankings` to get latest ICC rankings of top 10 all-rounders.\n\n`/team_rankings` to get top 10 ICC ranked teams.\n\n`/help` to display this message.**", color=discord.Color.random())
    )


# bowlers_rankings

@bot.tree.command(name="bowlers_rankings", description="Get top 10 ICC ranked bowlers")
@app_commands.describe(format="Game Format")
async def rankings(interaction: discord.Interaction, format: str):
    url = "https://cricbuzz-cricket.p.rapidapi.com/stats/v1/rankings/bowlers"

    format = format.lower()

    if format == 'odi' or format == 't20' or format == "t20i" or format == "test":
        if format == "t20i":
            format = "t20"
        querystring = {"formatType": format}
    else:
        await interaction.response.send_message(
            embed=discord.Embed(title="Invalid format name",
                                description="", color=discord.Color.random())
        )

    new_format = format.upper()

    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": "cricbuzz-cricket.p.rapidapi.com"
    }

    try:
        response = await asyncio.to_thread(requests.get, url, headers=headers, params=querystring, timeout=15)

        if response.status_code == 200:
            data = response.json()

            try:
                embed = discord.Embed(
                    title=f"Bowlers {new_format} ICC Rankings", description="", color=discord.Color.random())
                embed.add_field(
                    name="Rank                    Name", value="", inline=True)
                country_flag = ""
                for player in data["rank"]:
                    rank = player["rank"]
                    if rank == "1":
                        rank = "01"
                    if rank == "2":
                        rank = "02"
                    if rank == "3":
                        rank = "03"
                    if rank == "4":
                        rank = "04"
                    if rank == "5":
                        rank = "05"
                    if rank == "6":
                        rank = "06"
                    if rank == "7":
                        rank = "07"
                    if rank == "8":
                        rank = "08"
                    if rank == "9":
                        rank = "09"
                    name = player["name"]
                    country = player['country']

                    if any(abbreviation in country for abbreviation in team_flag_mapping_2.keys()):
                        for abbreviation, flag in team_flag_mapping_2.items():
                            if abbreviation in country:
                                country_flag = flag
                                break

                    embed.add_field(
                        name=f"{rank}                    {country_flag}  {name}", value="", inline=False)

                await interaction.response.send_message(embed=embed)

            except Exception as e:
                print(e)
        else:
            pass

    except Exception as e:
        print(e)


# batters_rankings

@bot.tree.command(name="batters_rankings", description="Get top 10 ICC ranked batters")
@app_commands.describe(format="Game Format")
async def rankings(interaction: discord.Interaction, format: str):
    url = "https://cricbuzz-cricket.p.rapidapi.com/stats/v1/rankings/batsmen"

    format = format.lower()

    if format == 'odi' or format == 't20' or format == "t20i" or format == "test":
        if format == "t20i":
            format = "t20"
        querystring = {"formatType": format}
    else:
        await interaction.response.send_message(
            embed=discord.Embed(title="Invalid format name",
                                description="", color=discord.Color.random())
        )

    new_format = format.upper()

    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": "cricbuzz-cricket.p.rapidapi.com"
    }

    try:
        response = await asyncio.to_thread(requests.get, url, headers=headers, params=querystring, timeout=15)

        if response.status_code == 200:
            data = response.json()

            try:
                embed = discord.Embed(
                    title=f"Batters {new_format} ICC Rankings", description="", color=discord.Color.random())
                embed.add_field(
                    name="Rank                    Name", value="", inline=True)
                country_flag = ""
                for player in data["rank"]:
                    rank = player["rank"]
                    if rank == "1":
                        rank = "01"
                    if rank == "2":
                        rank = "02"
                    if rank == "3":
                        rank = "03"
                    if rank == "4":
                        rank = "04"
                    if rank == "5":
                        rank = "05"
                    if rank == "6":
                        rank = "06"
                    if rank == "7":
                        rank = "07"
                    if rank == "8":
                        rank = "08"
                    if rank == "9":
                        rank = "09"
                    name = player["name"]
                    country = player['country']

                    if any(abbreviation in country for abbreviation in team_flag_mapping_2.keys()):
                        for abbreviation, flag in team_flag_mapping_2.items():
                            if abbreviation in country:
                                country_flag = flag
                                break

                    embed.add_field(
                        name=f"{rank}                    {country_flag}  {name}", value="", inline=False)

                await interaction.response.send_message(embed=embed)

            except Exception as e:
                print(e)
        else:
            pass

    except Exception as e:
        print(e)


# allrounders_rankings

@bot.tree.command(name="allrounders_rankings", description="Get top 10 ICC ranked allrounders")
@app_commands.describe(format="Game Format")
async def rankings(interaction: discord.Interaction, format: str):
    print("All rounder ratings...")

    url = "https://cricbuzz-cricket.p.rapidapi.com/stats/v1/rankings/allrounders"

    format = format.lower()

    if format == 'odi' or format == 't20' or format == "t20i" or format == "test":
        if format == "t20i":
            format = "t20"
        querystring = {"formatType": format}
    else:
        await interaction.response.send_message(
            embed=discord.Embed(title="Invalid format name",
                                description="", color=discord.Color.random())
        )

    new_format = format.upper()

    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": "cricbuzz-cricket.p.rapidapi.com"
    }

    try:
        response = await asyncio.to_thread(requests.get, url, headers=headers, params=querystring, timeout=15)

        if response.status_code == 200:
            data = response.json()

            try:
                embed = discord.Embed(
                    title=f"Allrounders {new_format} ICC Rankings", description="", color=discord.Color.random())
                embed.add_field(
                    name="Rank                    Name", value="", inline=True)
                country_flag = ""
                for player in data["rank"]:
                    rank = player["rank"]
                    if rank == "1":
                        rank = "01"
                    if rank == "2":
                        rank = "02"
                    if rank == "3":
                        rank = "03"
                    if rank == "4":
                        rank = "04"
                    if rank == "5":
                        rank = "05"
                    if rank == "6":
                        rank = "06"
                    if rank == "7":
                        rank = "07"
                    if rank == "8":
                        rank = "08"
                    if rank == "9":
                        rank = "09"
                    name = player["name"]
                    country = player['country']

                    if any(abbreviation in country for abbreviation in team_flag_mapping_2.keys()):
                        for abbreviation, flag in team_flag_mapping_2.items():
                            if abbreviation in country:
                                country_flag = flag
                                break

                    embed.add_field(
                        name=f"{rank}                    {country_flag}  {name}", value="", inline=False)

                await interaction.response.send_message(embed=embed)

            except Exception as e:
                print(e)
        else:
            pass

    except Exception as e:
        print(e)

# team_rankings


@bot.tree.command(name="team_rankings", description="Get top 10 ICC ranked teams")
@app_commands.describe(format="Game Format")
async def rankings(interaction: discord.Interaction, format: str):
    url = "https://cricbuzz-cricket.p.rapidapi.com/stats/v1/rankings/teams"

    format = format.lower()

    if format == 'odi' or format == 't20' or format == "t20i" or format == "test":
        if format == "t20i":
            format = "t20"
        querystring = {"formatType": format}
    else:
        await interaction.response.send_message(
            embed=discord.Embed(title="Invalid format name",
                                description="", color=discord.Color.random())
        )

    new_format = format.upper()

    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": "cricbuzz-cricket.p.rapidapi.com"
    }

    try:
        response = await asyncio.to_thread(requests.get, url, headers=headers, params=querystring, timeout=15)

        if response.status_code == 200:
            data = response.json()

            try:
                embed = discord.Embed(
                    title=f"Teams {new_format} ICC Rankings", description="", color=discord.Color.random())
                embed.add_field(name="Rank               Country",
                                value="", inline=True)
                country_flag = ""
                for i in range(10):
                    team = data["rank"][i]
                    rank = team["rank"]
                    if rank == "1":
                        rank = "01"
                    if rank == "2":
                        rank = "02"
                    if rank == "3":
                        rank = "03"
                    if rank == "4":
                        rank = "04"
                    if rank == "5":
                        rank = "05"
                    if rank == "6":
                        rank = "06"
                    if rank == "7":
                        rank = "07"
                    if rank == "8":
                        rank = "08"
                    if rank == "9":
                        rank = "09"
                    country = team["name"]

                    if any(abbreviation in country for abbreviation in team_flag_mapping_2.keys()):
                        for abbreviation, flag in team_flag_mapping_2.items():
                            if abbreviation in country:
                                country_flag = flag
                                break

                    embed.add_field(
                        name=f"{rank}                    {country_flag}  {country}", value="", inline=False)

                await interaction.response.send_message(embed=embed)

            except:
                pass
        else:
            pass

    except:
        pass

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
        await delete_subscription_inner(match_description)

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
            sleep_time = max(REFRESH_INT_S - elapsed_time, 10)
        print(f"sleeping for {sleep_time} seconds")
        await asyncio.sleep(sleep_time)

    await delete_subscription_inner(match_description)

async def _subscribe_to_score_inner(match_description, event, comment):
    print(f"in subscribe to score {match_description}: {event['sport']}/{event['league']} {event['id']}")
    score = await espn.get_event(event["sport"], event["league"], event["id"])

    if not score:
        await comment.edit(content=f"No score found for '{match_description}'")
        return False, None

    print("updating with new score")
    pst_time = datetime.now().strftime('%H:%M:%S')
    next_poll = espn.next_poll_time(score)
    next_update = next_poll.astimezone().strftime('%H:%M') if next_poll else None
    await comment.edit(content=espn.format_score(score, pst_time, team_flag_mapping_2, next_update))

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
    subscribed_tasks[match_description] = task, comment, event
    save_subscriptions()

def save_subscriptions():
    data = {
        match_description: {"channel_id": comment.channel.id, "message_id": comment.id, "event": event}
        for match_description, (_, comment, event) in subscribed_tasks.items()
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
    for match_description, sub in load_subscriptions().items():
        if match_description in subscribed_tasks:
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
    if subscribed_tasks:
        subscribed_list = "\n".join(
            f"{index + 1}. {key}" for index, key in enumerate(subscribed_tasks)
        )
        await interaction.response.send_message(f"Current subscriptions:\n{subscribed_list}")
    else:
        await interaction.response.send_message("No current subscriptions")

@bot.tree.command(name="unsubscribe", description="Unsubscribe from a score update")
@app_commands.describe(subscription_number="Subscription number")
async def unsubscribe(interaction: discord.Interaction, subscription_number: int):
    descriptions = list(subscribed_tasks.keys())
    if not 1 <= subscription_number <= len(descriptions):
        await interaction.response.send_message(f"No subscription #{subscription_number}, see /list_subscribed")
        return

    match_description = descriptions[subscription_number - 1]
    await delete_subscription_inner(match_description)
    await interaction.response.send_message(f"Unsubscribed from '{match_description}'")

async def delete_subscription_inner(match_description):
    print(f"Deleting subscription for {match_description}")
    if match_description in subscribed_tasks:
        comment = subscribed_tasks[match_description][1]
        try:
            await comment.unpin()
        except Exception as e:
            print(f"Error unpinning comment: {e}")

        try:
            subscribed_tasks[match_description][0].cancel()
        except Exception as e:
            print(f"Error deleting subscription: {e}")

        del subscribed_tasks[match_description]
        save_subscriptions()

bot.run(DISCORD_TOKEN)
