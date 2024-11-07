import os
import re
import discord
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

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

bot.run(DISCORD_TOKEN)
