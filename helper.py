import discord
from discord.ext import commands, tasks
import logging
from dotenv import dotenv_values
import asyncpg
import asyncio
import aiohttp
from datetime import datetime
from utils.db import Database, get_db_connection

config = dotenv_values(".env")
token = config["HEIST_HELPER_TOKEN"]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='.', intents=intents)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVER_ID = 1336528911756165172
INDIVIDUAL_STAT = 1336529668668657788
TOTAL_STAT = 1345497197386666076
GUILD_STAT = 1345498349775749233
DONOR_ROLE_ID = 1336529652512067684

@tasks.loop(minutes=5)
async def update_channel_name():
    max_retries = 3
    retry_delay = 5
    retries = 0
    async with aiohttp.ClientSession() as session:
        while retries < max_retries:
            try:
                async with session.get('http://127.0.0.1:5002/getcount') as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        discord_user_install_count = data.get('discord_user_install_count', 0)
                        formatted_discord_count = f"{discord_user_install_count:,}"
                        channel1 = bot.get_channel(INDIVIDUAL_STAT)
                        if channel1 and isinstance(channel1, discord.VoiceChannel):
                            new_name1 = f"Individual Users: {formatted_discord_count}"
                            if channel1.name != new_name1:
                                await channel1.edit(name=new_name1)
                        
                        user_count = data.get('user_count', 0)
                        formatted_user_count = f"{user_count:,}"
                        channel2 = bot.get_channel(TOTAL_STAT)
                        if channel2 and isinstance(channel2, discord.VoiceChannel):
                            new_name2 = f"Total Users: {formatted_user_count}"
                            if channel2.name != new_name2:
                                await channel2.edit(name=new_name2)
                        
                        discord_guild_count = data.get('discord_guild_count', 0)
                        formatted_guild_count = f"{discord_guild_count:,}"
                        channel3 = bot.get_channel(GUILD_STAT)
                        if channel3 and isinstance(channel3, discord.VoiceChannel):
                            new_name3 = f"Server Count: {formatted_guild_count}"
                            if channel3.name != new_name3:
                                await channel3.edit(name=new_name3)
                        
                        break
                    else:
                        logger.error(f"Failed to fetch counts: {response.status}")
                        break
            except aiohttp.ClientError as e:
                logger.error(f"HTTP request error: {e}")
                retries += 1
                await asyncio.sleep(retry_delay)
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")
                break

@tasks.loop(minutes=2)
async def check_donors():
    guild = bot.get_guild(SERVER_ID)
    if guild:
        donor_role = guild.get_role(DONOR_ROLE_ID)
        if donor_role:
            async with get_db_connection() as conn:
                try:
                    async with conn.transaction():
                        donors = await conn.fetch("SELECT user_id FROM donors")
                        for row in donors:
                            user_id = row['user_id']
                            try:
                                member = await guild.fetch_member(int(user_id))
                                if member and donor_role not in member.roles:
                                    await member.add_roles(donor_role)
                                    logger.info(f"Added Donor role to user {user_id}")
                            except discord.HTTPException as e:
                                logger.error(f"Failed to add Donor role to user {user_id}: {e}")
                            except discord.NotFound:
                                logger.warning(f"Member with user_id {user_id} not found in guild.")
                except Exception as e:
                    logger.error(f"Error checking donors: {e}")

@tasks.loop(minutes=10)
async def remove_invalid_donors():
    guild = bot.get_guild(SERVER_ID)
    if guild:
        donor_role = guild.get_role(DONOR_ROLE_ID)
        if donor_role:
            async with get_db_connection() as conn:
                try:
                    async with conn.transaction():
                        donors = {str(row['user_id']) for row in await conn.fetch("SELECT user_id FROM donors")}
                        current_donors = {str(member.id) for member in guild.members if donor_role in member.roles}
                        for member in guild.members:
                            if str(member.id) in current_donors and str(member.id) not in donors:
                                await member.remove_roles(donor_role)
                                logger.info(f"Removed Donor role from user {member.id}")
                except Exception as e:
                    logger.error(f"Error removing invalid donors: {e}")

@update_channel_name.before_loop
async def before_update_channel_name():
    await bot.wait_until_ready()

@check_donors.before_loop
async def before_check_donors():
    await bot.wait_until_ready()

@remove_invalid_donors.before_loop
async def before_remove_invalid_donors():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} - {bot.user.id}')
    print('Bot is ready.')
    await bot.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.watching, name="heist.lol"))
    
    if not update_channel_name.is_running():
        update_channel_name.start()
    if not check_donors.is_running():
        check_donors.start()
    if not remove_invalid_donors.is_running():
        remove_invalid_donors.start()
    if not update_boosters.is_running():
        update_boosters.start()

@bot.event
async def on_member_join(member):
    if member.guild.id == SERVER_ID:
        default_role = member.guild.get_role(1336529657222135839)
        donor_role = member.guild.get_role(1336529652512067684)

        if default_role:
            await member.add_roles(default_role)
            print(f"Assigned default role to {member.name}")

        async with get_db_connection() as conn:
            donor = await conn.fetchrow("SELECT user_id FROM donors WHERE user_id = $1", str(member.id))
            if donor and donor_role:
                await member.add_roles(donor_role)
                print(f"Assigned donor role to {member.name}")

@bot.event
async def on_member_update(before, after):
    guild = bot.get_guild(SERVER_ID)

    if before.premium_since is None and after.premium_since is not None:
        async with get_db_connection() as conn:
            await conn.execute("UPDATE user_data SET booster = TRUE WHERE user_id = $1", str(after.id))
            logger.info(f"User {after.id} boosted.")

    elif before.premium_since is not None and after.premium_since is None:
        async with get_db_connection() as conn:
            await conn.execute("UPDATE user_data SET booster = FALSE WHERE user_id = $1", str(after.id))
            logger.info(f"User {after.id} stopped boosting.")

@tasks.loop(hours=2)
async def update_boosters():
    guild = bot.get_guild(SERVER_ID)
    if not guild:
        return

    async with get_db_connection() as conn:
        try:
            async with conn.transaction():
                boosters = {str(member.id) for member in guild.premium_subscribers}
                db_boosters = {str(row['user_id']) for row in await conn.fetch("SELECT user_id FROM user_data WHERE booster = TRUE")}

                new_boosters = boosters - db_boosters
                removed_boosters = db_boosters - boosters

                for user_id in new_boosters:
                    await conn.execute("UPDATE user_data SET booster = TRUE WHERE user_id = $1", user_id)
                    logger.info(f"User {user_id} is now marked as a booster.")

                for user_id in removed_boosters:
                    await conn.execute("UPDATE user_data SET booster = FALSE WHERE user_id = $1", user_id)
                    logger.info(f"User {user_id} is no longer a booster.")

        except Exception as e:
            logger.error(f"Error updating booster status: {e}")

bot.run(token)