import os
import re
import json
import asyncio
import traceback
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import discord
from discord import app_commands
from discord.ext import commands

import screengrab

load_dotenv()

REFRESH_INT_S = 30
REFRESH_STUMPS_INT_S = 15 * 60

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RAPID_API_KEY = os.getenv('RAPID_API_KEY')
data_2 = ""

team_flag_mapping = {
    "afg": ":flag_af:",
    "aus": ":flag_au:",
    "ban": ":flag_bd:",
    "eng": ":england:",
    "ind": ":flag_in:",
    "ire": ":four_leaf_clover:",
    "nz": ":flag_nz:",
    "pak": ":flag_pk:",
    "rsa": ":flag_za:",
    "sl": ":flag_lk:",
    "wi": ":palm_tree:",
    "zim": ":flag_zw:",
    "sco": ":scotland:",
    "ned": ":flag_nl:",
    "usa": ":flag_us:",
    "oma": ":flag_om:",
    "uae": ":flag_ae:",
    "nam": ":flag_na:",
    "nep": ":flag_np:",
    "can": ":flag_ca:",
    "hk": ":flag_hk:",
    "mly": ":flag_my:",
    "png": ":flag_pg:"
}

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

# Global dictionary to store tasks
subscribed_tasks = {}

SUBSCRIPTIONS_FILE = "/var/run/cricbot/subscriptions.json"

def save_subscriptions():
    """Save the current subscriptions to a JSON file."""
    with open(SUBSCRIPTIONS_FILE, 'w') as f:
        save_subscribed_tasks = {k: {"channel_id": v["channel_id"], "comment_id": v["comment_id"], "url": v["url"]} for k, v in subscribed_tasks.items()}
        json.dump(save_subscribed_tasks, f)

async def load_subscriptions():
    """Load subscriptions from a JSON file and restart tasks."""
    try:
        with open(SUBSCRIPTIONS_FILE, 'r') as f:
            subscriptions = json.load(f)
    except FileNotFoundError:
        print("No previous subscriptions found.")
        return
    except Exception as e:
        print(f"Error loading subscriptions: {e}")
        return

    try:
        for match_description, data in subscriptions.items():
            await create_subscription(match_description, data["url"], data["channel_id"], data["comment_id"])
    except Exception as e:
        print(f"Error loading subscriptions: {e}")

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
    await load_subscriptions()  # Load subscriptions on startup

# livescore

@bot.tree.command(name="live_score", description="Get LIVE scorecard")
@app_commands.describe(team_short_name="Team Name")
async def live_score(interaction: discord.Interaction, team_short_name: str):

    team_short_name = team_short_name.lower()

    if team_short_name == "india":
        team_short_name = "ind"
    elif team_short_name == "australia":
        team_short_name = "aus"
    elif team_short_name == "sa" or team_short_name == "south africa":
        team_short_name = "rsa"
    elif team_short_name == "new zealand":
        team_short_name = "nz"
    elif team_short_name == "pakistan":
        team_short_name = "pak"
    elif team_short_name == "afghanistan":
        team_short_name = "afg"
    elif team_short_name == "sri lanka":
        team_short_name = "sl"
    elif team_short_name == "england":
        team_short_name = "eng"
    elif team_short_name == "netherlands":
        team_short_name = "ned"
    elif team_short_name == "bangladesh":
        team_short_name = "ban"
    elif team_short_name == "west indies":
        team_short_name = "wi"
    elif team_short_name == "zimbabwe":
        team_short_name = "zim"

    url = 'https://www.cricbuzz.com/'
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    live_anchor = soup.find('a', class_='cb-mat-mnu-itm cb-ovr-flo', string=lambda text: (
        team_short_name.upper() in text and "Break" in text) or (team_short_name.upper() in text and "Live" in text))

    if live_anchor:

        link = live_anchor['href']
        split_link = link.split('/')

        if len(split_link) > 2:
            extracted_number = split_link[2]
            api_url = f"https://cricbuzz-cricket.p.rapidapi.com/mcenter/v1/{extracted_number}/scard"
            api_url_2 = f"https://cricbuzz-cricket.p.rapidapi.com/mcenter/v1/{extracted_number}/overs"

            headers = {
                "X-RapidAPI-Key": RAPID_API_KEY,
                "X-RapidAPI-Host": "cricbuzz-cricket.p.rapidapi.com"
            }

            try:
                api_response = requests.get(api_url, headers=headers)
                data = api_response.json()

                api_response_2 = requests.get(api_url_2, headers=headers)
                data_2 = api_response_2.json()

                match_type = data['matchHeader']['matchType']
                series_name = data["matchHeader"]["seriesDesc"]
                valid_series_names = ["Indian Premier League", "Big Bash League", "Pakistan Super League", "Caribbean Premier League",
                                      "Major League Cricket", "Lanka Premier League", "One-Day Cup", "T20I", "County", "World Cup"]

                if match_type == "International" or any(name in series_name for name in valid_series_names):

                    team1_name = data["matchHeader"]["matchTeamInfo"][0]["battingTeamShortName"]
                    team1_flag = ""
                    if any(abbreviation in team1_name.lower() for abbreviation in team_flag_mapping.keys()):
                        for abbreviation, flag in team_flag_mapping.items():
                            if abbreviation in team1_name.lower():
                                team1_flag = flag
                                team1_name = f"{team1_flag} {team1_name}"
                                break

                    team2_name = data["matchHeader"]["matchTeamInfo"][0]["bowlingTeamShortName"]
                    team2_flag = ""
                    if any(abbreviation in team2_name.lower() for abbreviation in team_flag_mapping.keys()):
                        for abbreviation, flag in team_flag_mapping.items():
                            if abbreviation in team2_name.lower():
                                team2_flag = flag
                                team2_name = f"{team2_flag} {team2_name}"
                                break

                    status = data['matchHeader']['status']

                    team1_score = "`Yet to bat`"
                    team1_info = ""
                    team1_runs = ""
                    team1_overs = ""
                    team1_wickets = ""
                    team1_runrate = ""

                    team2_score = "`Yet to bat`"
                    team2_info = ""
                    team2_runs = ""
                    team2_overs = ""
                    team2_wickets = ""
                    team2_runrate = ""

                    try:
                        team1_info = data['scoreCard'][0]
                        team1_runs = team1_info['scoreDetails']['runs']
                        team1_overs = team1_info['scoreDetails']['overs']
                        team1_wickets = team1_info['scoreDetails']['wickets']
                        team1_runrate = team1_info['scoreDetails']['runRate']
                        team1_score = f"{team1_runs}/{team1_wickets} ({team1_overs}) RR: {team1_runrate}"
                        scard = f"{team1_name}: `{team1_score}`\n\n{team2_name}: `{team2_score}`\n\n`{status}`"
                    except:
                        pass

                    try:
                        team2_info = data['scoreCard'][1]
                        team2_runs = team2_info['scoreDetails']['runs']
                        team2_overs = team2_info['scoreDetails']['overs']
                        team2_wickets = team2_info['scoreDetails']['wickets']
                        team2_runrate = team2_info['scoreDetails']['runRate']
                        required_rate = data_2["requiredRunRate"]
                        status = f"{status} (Required Rate: {required_rate})"
                        team2_score = f"{team2_runs}/{team2_wickets} ({team2_overs}) RR: {team2_runrate}"
                        scard = f"{team1_name}: `{team1_score}`\n\n{team2_name}: `{team2_score}`\n\n`{status}`"
                    except:
                        pass

                    strike_bat_name = data_2["batsmanStriker"]["batName"]
                    strike_bat_runs = data_2["batsmanStriker"]["batRuns"]
                    strike_bat_balls = data_2["batsmanStriker"]["batBalls"]

                    nonstrike_bat_name = data_2["batsmanNonStriker"]["batName"]
                    nonstrike_bat_runs = data_2["batsmanNonStriker"]["batRuns"]
                    nonstrike_bat_balls = data_2["batsmanNonStriker"]["batBalls"]

                    strike_bowl_name = data_2["bowlerStriker"]["bowlName"]
                    strike_bowl_wkts = data_2["bowlerStriker"]["bowlWkts"]
                    strike_bowl_runs = data_2["bowlerStriker"]["bowlRuns"]
                    strike_bowl_ovrs = data_2["bowlerStriker"]["bowlOvs"]
                    strike_bowl_eco = data_2["bowlerStriker"]["bowlEcon"]

                    nonstrike_bowl_name = data_2["bowlerNonStriker"]["bowlName"]
                    nonstrike_bowl_wkts = data_2["bowlerNonStriker"]["bowlWkts"]
                    nonstrike_bowl_runs = data_2["bowlerNonStriker"]["bowlRuns"]
                    nonstrike_bowl_ovrs = data_2["bowlerNonStriker"]["bowlOvs"]
                    nonstrike_bowl_eco = data_2["bowlerNonStriker"]["bowlEcon"]

                    timeline = data_2["recentOvsStats"]
                    pship_runs = data_2["partnerShip"]["runs"]
                    pship_balls = data_2["partnerShip"]["balls"]

                    match_state = data['matchHeader']['state']

                    match_info = f"**{series_name}**\n\n**{scard}**\n\n"

                else:
                    await interaction.response.send_message(embed=discord.Embed(title=f"No match found for `{team_short_name}`", description="", color=discord.Color.random()))

            except Exception as e:
                pass

            embd = discord.Embed(
                title=f"LIVE", description=f"{match_info}", color=discord.Color.random())

            match_state = data['matchHeader']['state']

            if match_state == "In Progress":

                embd.add_field(
                    name="Bat Name", value=f"**`{strike_bat_name}*`\n`{nonstrike_bat_name}`**", inline=True)
                embd.add_field(
                    name="Runs", value=f"**`{strike_bat_runs}`\n`{nonstrike_bat_runs}`**", inline=True)
                embd.add_field(
                    name="Balls", value=f"**`{strike_bat_balls}`\n`{nonstrike_bat_balls}`**", inline=True)

                embd.add_field(
                    name="Bowl Name", value=f"**`{strike_bowl_name}*`\n`{nonstrike_bowl_name}`**", inline=True)
                embd.add_field(
                    name="Wkts/Runs", value=f"**`{strike_bowl_wkts}`/`{strike_bowl_runs}`\n`{nonstrike_bowl_wkts}`/`{nonstrike_bowl_runs}`**", inline=True)
                embd.add_field(
                    name="Ovrs/Eco", value=f"**`{strike_bowl_ovrs}`/`{strike_bowl_eco}`\n`{nonstrike_bowl_ovrs}`/`{nonstrike_bowl_eco}`**", inline=True)

                embd.add_field(
                    name=f"P'ship: `{pship_runs}({pship_balls})`", value=f"", inline=False)
                embd.add_field(
                    name=f"Timeline: `{timeline}`", value="", inline=False)

            await interaction.response.send_message(embed=embd)
        else:
            await interaction.response.send_message(embed=discord.Embed(title=f"No match found for `{team_short_name}`", description="", color=discord.Color.random()))

    else:
        await interaction.response.send_message(embed=discord.Embed(title=f"No match found for `{team_short_name}`", description="", color=discord.Color.random()))


# invite

@bot.tree.command(name="invite", description="Invite Cricbot to Your Server")
async def live_score(interaction: discord.Interaction):
    bot_invite_link = "bot_invite_link"
    server_invite_link = "server_invite_link"
    await interaction.response.send_message(
        embed=discord.Embed(
            title="Invite Links", description=f"**[Click here to invite Cricbot to your server]({bot_invite_link})\n\n[Click here to join Official CrikChat server]({server_invite_link})**", color=discord.Color.random())
    )


# vote

@bot.tree.command(name="vote", description="Vote for Cricbot")
async def live_score(interaction: discord.Interaction):
    vote_link_1 = "bot_vote_link"
    vote_link_2 = "bot_vote_link"
    await interaction.response.send_message(
        embed=discord.Embed(title="Help the developer to keep running this bot",
                            description=f"**[Vote on top.gg]({vote_link_1})\n\n[Vote on discordbotlist.com]({vote_link_2})**", color=discord.Color.random())
    )

 # help


@bot.tree.command(name="help", description="Display all Commands")
async def live_score(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=discord.Embed(title="Stay in the game with Cricbot: Your LIVE cricket score companion!",
                            description=f"**Cricbot is used in over `{len(bot.guilds)}` servers, where cricket fans from all over the world always stay in the game.\n\nCommands:\n\n`/live_score` to view LIVE scorecard of an ongoing match.\n\n`/batters_rankings` to get latest ICC rankings of top 10 batters.\n\n`/bowlers_rankings` to get latest ICC rankings of top 10 bowlers.\n\n`/allrounders_rankings` to get latest ICC rankings of top 10 all-rounders.\n\n`/team_rankings` to get top 10 ICC ranked teams.\n\n`/invite` to invite Cricbot to your server.\n\n`/vote` to vote for Cricbot to keep it running.\n\n`/help` to display this message.**", color=discord.Color.random())
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
        response = requests.get(url, headers=headers, params=querystring)

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
        response = requests.get(url, headers=headers, params=querystring)

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
        response = requests.get(url, headers=headers, params=querystring)

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
        response = requests.get(url, headers=headers, params=querystring)

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

async def get_comment_handle(channel_id, comment_id):
    channel = bot.get_channel(channel_id)
    if channel:
        comment = await channel.fetch_message(comment_id)
        return comment
    return None
    
async def subscribe_to_score(match_description, channel_id, comment_id, url):
    try:
        await _subscribe_to_score(match_description, channel_id, comment_id, url)
    except Exception as e:
        print(f"Error in _subscribe_to_score: {e}")
        traceback.print_exc()
        comment = await get_comment_handle(channel_id, comment_id)
        if comment:
            await comment.edit(content=f"¯\_(ツ)_/¯ Fuck: {e}")
        await delete_subscription_inner(match_description)
        raise

async def _subscribe_to_score(match_description, channel_id, comment_id, url):
    comment = await get_comment_handle(channel_id, comment_id)

    if not comment:
        print(f"Comment not found for {match_description}")
        return

    keep_running = True
    while keep_running:
        start_time = datetime.now()
        retry = 5
        while retry > 0:
            try:
                keep_running, is_stumps = await _subscribe_to_score_inner(match_description, url, comment)
                break
            except Exception as e:
                print(f"Error in _subscribe_to_score_inner, attempts left: {retry}")
                print(e)
                comment = await get_comment_handle(channel_id, comment_id)
                if not comment:
                    print(f"Comment not found for {match_description}")
                    raise e

                retry -= 1
                if retry == 0:
                    raise e
                await asyncio.sleep((5 - retry) * 30)
                print("Retrying...")

        elapsed_time = (datetime.now() - start_time).total_seconds()
        if not is_stumps:
            sleep_time = max(REFRESH_INT_S - elapsed_time, 10)
        else:
            sleep_time = max(REFRESH_STUMPS_INT_S - elapsed_time, 10)

        print(f"sleeping for {sleep_time} seconds")
        await asyncio.sleep(sleep_time)

    await delete_subscription_inner(match_description)

async def _subscribe_to_score_inner(match_description, url, comment):
    print(f"in subscribe to score {match_description}: {url}")
    retry = 3
    while retry > 0:
        try:
            image_path, is_finished, is_stumps = await screengrab.get_score_image(url)
            print(f"get score: {image_path}, finished: {is_finished}, is stumps: {is_stumps}")
            break
        except Exception as e:
            retry -= 1
            if retry == 0:
                raise e
            await asyncio.sleep((3 - retry) * 30)

    if not image_path:
        await comment.edit(content=f"No score found for '{match_description}'")
        return False, False

    print("updating with new score")
    pst_time = datetime.now().strftime('%H:%M:%S')
    await comment.edit(content=f"Updated: {pst_time}", attachments=[discord.File(image_path)])

    # try to cleanup image file
    try:
        print(f"deleting image file: {image_path}")
        os.remove(image_path)
    except Exception as e:
        print(f"Error deleting image file: {e}")

    if is_finished:
        await comment.edit(content="Game finished")
        return False, False

    return True, is_stumps

@bot.tree.command(name="subscribe", description="Subscribe to live score updates")
@app_commands.describe(match_description="Match Description (e.g., 'Australia vs India cricket')")
async def subscribe(interaction: discord.Interaction, match_description: str):
    print(f"Subscribe!: {match_description}")
    if match_description in subscribed_tasks:
        await interaction.response.send_message(f"Already subscribed to '{match_description}'")
        return
    await interaction.response.send_message(f"Getting score for '{match_description}'")
    comment = await interaction.original_response()
    print("Checking if match description is valid")
    url = await screengrab.match_description_to_sports_score_url(match_description)

    if not url:
        await comment.edit(content=f"No match found on Google for '{match_description}'???")
        return

    print(f"Found url: {url}")

    await comment.edit(content=f"Found match. Will start updating.")
    await comment.pin()

    await create_subscription(match_description, url, interaction.channel_id, comment.id)
    save_subscriptions()  # Save subscriptions after adding a new one

async def create_subscription(match_description, url, channel_id, comment_id):
    task = bot.loop.create_task(subscribe_to_score(match_description, channel_id, comment_id, url))
    subscribed_tasks[match_description] = {"task": task, "channel_id": channel_id, "comment_id": comment_id, "url": url}
    print(f"{subscribed_tasks}")

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
    try:
        match_description = list(subscribed_tasks.keys())[subscription_number - 1]
        await delete_subscription_inner(match_description)
        save_subscriptions()  # Save subscriptions after removing one
        await interaction.response.send_message(f"Unsubscribed from: {match_description}")
    except Exception as e:
        await interaction.response.send_message(f"Error deleting subscription: {e}")

async def delete_subscription_inner(match_description):
    print(f"Deleting subscription for {match_description}")
    if match_description in subscribed_tasks:
        channel_id = subscribed_tasks[match_description]["channel_id"]
        comment_id = subscribed_tasks[match_description]["comment_id"]
        comment = await get_comment_handle(channel_id, comment_id)
        try:
            await comment.unpin()
        except Exception as e:
            print(f"Error unpinning comment: {e}")

        try:
            subscribed_tasks[match_description]["task"].cancel()
        except Exception as e:
            print(f"Error deleting subscription: {e}")

        del subscribed_tasks[match_description]
        save_subscriptions()  # Save subscriptions after deletion

bot.run(DISCORD_TOKEN)
