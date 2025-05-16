import discord_ios
import discord
from discord.ext import commands, tasks
from dotenv import dotenv_values
import psutil
import gc, os, logging, tracemalloc
import aiohttp
import aiofiles
import asyncio
import uvloop
import asyncpg
from utils import permissions
from utils.db import Database, get_db_connection, redis_client
from utils.permissions import handle_command_error
from utils.socialmanager import SocialsManager
from logging.handlers import RotatingFileHandler
import datetime

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

config = dotenv_values(".env")
DATA_DB = config['DATA_DB']
TOKEN = config["DISCORD_TOKEN"]

WEBHOOKS = [
    "https://discord.com/api/webhooks/1336543720627240970/9aepqBVvv9SUhsgID_BgqS4XqSNKSjX4jWN_t0W6jwJLmSZRlfktTcljreehJjk8_-MB",
    "https://discord.com/api/webhooks/1336543729049407553/aOnFFAYtzeddLwQZTvf2NzDC6LmgFIaTMqZx0eRFUPqJC4OaTaPAiERWusQYAoyWm2LC",
    "https://discord.com/api/webhooks/1336543731645419520/Nsvhy9h7vWSbim-GSC5ZPkHhp2SrafvmEO19oZ4sGxo1HTkoKjz8z_u_hFCPGGQiqWrg"
]

request_counts = [0] * len(WEBHOOKS)
current_webhook_index = 0
reset_timer = None

async def send_log_to_webhook(embed):
    global current_webhook_index, reset_timer
    async with aiohttp.ClientSession() as session:
        data = {"embeds": [embed.to_dict()]}
        try:
            async with session.post(WEBHOOKS[current_webhook_index], json=data) as response:
                if response.status == 429:
                    retry_after = await response.json()
                    await asyncio.sleep(retry_after['retry_after'] / 1000)
                    current_webhook_index = (current_webhook_index + 1) % len(WEBHOOKS)
                    request_counts[current_webhook_index] = 0
                elif response.status != 204:
                    print(f"Failed to send log: {response.status}")
                    current_webhook_index = (current_webhook_index + 1) % len(WEBHOOKS)
                    request_counts[current_webhook_index] = 0
                else:
                    request_counts[current_webhook_index] += 1
                    if request_counts[current_webhook_index] >= 25:
                        current_webhook_index = (current_webhook_index + 1) % len(WEBHOOKS)
                        if reset_timer is None:
                            reset_timer = asyncio.get_event_loop().call_later(10, reset_webhook)
        except Exception as e:
            print(f"Failed to send logs: {e}")

def reset_webhook():
    global current_webhook_index, reset_timer
    current_webhook_index = 0
    request_counts[:] = [0] * len(WEBHOOKS)
    reset_timer = None

async def pendinges():
    async with aiohttp.ClientSession() as session:
        url = "https://discord.com/api/v9/applications/1225070865935368265/entitlements"
        headers = {"Authorization": f"Bot {TOKEN}"}
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                entitlements = await response.json()
                for entitlement in entitlements:
                    user_id = entitlement.get("user_id")
                    status = entitlement.get("status")
                    if entitlement["status"] == 1:
                        await grantprem(user_id, 'add')
                    elif entitlement["status"] in [2, 3]:
                        await grantprem(user_id, 'remove')
            else:
                print(f"Failed to fetch entitlements: {response.status}")

class Heist(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True 
        intents.message_content = True
        intents.presences = False
        super().__init__(
            command_prefix=self.get_prefix,
            intents=intents, 
            help_command=None,
            chunk_guilds_at_startup=False,
            max_messages=0,
            case_insensitive=True
        )
        self.start_time = None
        self.session = None
        self.socials = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.socials = SocialsManager(self.session)
        await Database.init_pool()
        for cog in ["cogs.utils", "cogs.socials", "cogs.owner", "cogs.economy", "cogs.fun", "cogs.info", "cogs.music", "cogs.roleplay", "cogs.discord", "cogs.games", "cogs.settings"]:
            await self.load_extension(cog)
        await self.leave_small_servers()

    async def get_prefix(self, message: discord.Message):
        return commands.when_mentioned_or('@Heist', '@heist', '<@1225070865935368265>')(self, message)

    async def leave_small_servers(self):
        for guild in self.guilds:
            if guild.member_count < 100:
                await self.send_leave_message(guild)
                await guild.leave()
                print(f"Left guild {guild.name} (ID: {guild.id}) due to low member count.")

    async def send_leave_message(self, guild):
        embed = discord.Embed(
            title="Sorry! Not quite there yet.",
            description="Your server needs to have at least **100 members** for you to be able to add Heist.\n-# You can still **add it to your apps** [here](https://discord.com/oauth2/authorize?client_id=1225070865935368265) so you can use it anywhere.",
            color=0x000f
        )

        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            try:
                await guild.system_channel.send(embed=embed)
            except discord.Forbidden:
                await guild.system_channel.send(
                    "Sorry! Not quite there yet.\n\n"
                    "Your server needs to have at least **100 members** for you to be able to add Heist.\n"
                    "-# You can still **add it to your apps** [here](https://discord.com/oauth2/authorize?client_id=1225070865935368265) so you can use it anywhere."
                )
        else:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    try:
                        await channel.send(embed=embed)
                        break
                    except discord.Forbidden:
                        await channel.send(
                            "Sorry! Not quite there yet.\n\n"
                            "Your server needs to have at least **100 members** for you to be able to add Heist.\n"
                            "-# You can still **add it to your apps** [here](https://discord.com/oauth2/authorize?client_id=1225070865935368265) so you can use it anywhere."
                        )
                        break

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print(f'Using {self.shard_count} shards')
        self.start_time = discord.utils.utcnow()
        await self.tree.sync()
        await pendinges()

    async def on_guild_join(self, guild):
        if guild.member_count < 100:
            await self.send_leave_message(guild)
            await guild.leave()
            print(f"Left guild {guild.name} (ID: {guild.id}) due to low member count.")

    async def close(self):
        pool = await Database.init_pool()
        if pool:
            await pool.close()
        if self.socials:
            await self.socials.close()
        if self.session:
            await self.session.close()
        await super().close()
        print('closed both conns')

    async def on_interaction(self, interaction: discord.Interaction):
        uid = interaction.user.id
        user = interaction.user.name

        custom_id = interaction.data.get('custom_id')
        if custom_id:
            return

        redis_key = f"user:{uid}:exists"
        user_exists_in_cache = await redis_client.get(redis_key)

        if not user_exists_in_cache:
            async with Database.get_connection() as conn:
                user_exists = await conn.fetchval("SELECT 1 FROM user_data WHERE user_id = $1", str(uid))

                if not user_exists:
                    await conn.execute("INSERT INTO user_data (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING", str(uid))
                    redis_key_limited = f"user:{uid}:limited"
                    await redis_client.setex(redis_key_limited, 7 * 24 * 60 * 60, '')

                    redis_key_untrusted = f"user:{uid}:untrusted"
                    await redis_client.setex(redis_key_untrusted, 60 * 24 * 60 * 60, '')

                    await redis_client.setex(redis_key, 600, '1')

        interaction_type = interaction.data.get('type')

        if interaction_type == 1:
            if 'options' in interaction.data and interaction.data['options'] and interaction.data['options'][0].get('type') == 1:
                cmd = f"{interaction.data['name']} {interaction.data['options'][0]['name']}"
                options = interaction.data['options'][0].get('options', [])
            else:
                cmd = interaction.data['name']
                options = interaction.data.get('options', [])
                
            if 'options' in interaction.data:
                for option in interaction.data['options']:
                    if option.get('type') == 2:
                        subcommand = option.get('options', [{}])[0]
                        cmd = f"{interaction.data['name']} {option['name']} {subcommand.get('name', '')}"
                        options = subcommand.get('options', [])
                        break
                        
        elif interaction_type == 2:
            cmd = f"Context Menu: {interaction.data['name']}"
            options = []
            
            if 'target_id' in interaction.data:
                options.append({
                    'name': 'target',
                    'value': interaction.data['target_id']
                })
        else:
            return

        options_str = "\n".join([f"* {opt['name']}: `{opt['value']}`" for opt in options])
        embed = discord.Embed(description=f"* **{cmd}**\n{options_str}", color=0x000f)
        embed.set_author(name=f"{user} ({uid})")

        if interaction.type == discord.InteractionType.application_command:
            await send_log_to_webhook(embed)

    async def on_application_command_error(self, interaction: discord.Interaction, error):
        embed = discord.Embed(description=f"```yaml\n{error}```", color=0x000f)
        await send_log_to_webhook(embed)

client = Heist()

@client.event
async def on_entitlement_create(entitlement):
    await grantprem(entitlement.user_id, 'add')
    print(f"Entitlement object: {entitlement}")

    user = await client.fetch_user(entitlement.user_id)
    username = user.name
    user_id = entitlement.user_id

    webhook_url = "https://discord.com/api/webhooks/1336551280050569236/xReLELP3KZIV1p9WDePAkO2MwjpFICSqF_gJ8NZ1NqBf2V3U_6GL0uUlR_f8VSlKfRxG"
    message_content = f"@{username} ({user_id}) just bought Premium."

    async with aiohttp.ClientSession() as session:
        payload = {"content": message_content}
        async with session.post(webhook_url, json=payload) as response:
            if response.status != 204:
                print(f"Failed to send message to webhook: {response.status}")

@client.event
async def on_entitlement_remove(entitlement):
    await grantprem(entitlement.user_id, 'remove')

async def grantprem(user_id, action):
    async with Database.get_connection() as conn:
        try:
            user_id_str = str(user_id)
            if action == 'add':
                await conn.execute(
                    'INSERT INTO donors (user_id, donor_status) VALUES ($1, 1) ON CONFLICT (user_id) DO NOTHING', 
                    user_id_str
                )
                await permissions.invalidate_cache(user_id_str)
                embed = discord.Embed(
                    title="✅ Notice",
                    description=f"You have been given **Premium** status on Heist.\nThank you for your purchase!\n\nMake sure to join our [**Discord server**](https://discord.gg/gVarzmGAJC) to claim more perks.",
                    color=0x000f
                )
                embed.set_footer(text="heist.lol", icon_url="https://csyn.me/assets/heist.png")
                message = embed
            elif action == 'remove':
                await conn.execute(
                    'DELETE FROM donors WHERE user_id = $1', 
                    user_id_str
                )
                await permissions.invalidate_cache(user_id_str)
                embed = discord.Embed(
                    title="❌ Notice",
                    description=f"Your **Premium** status has been removed on Heist.\n\nThis was unexpected? Make a ticket [**here**](https://discord.gg/gVarzmGAJC).",
                    color=0x000f
                )
                embed.set_footer(text="heist.lol", icon_url="https://csyn.me/assets/heist.png")
                message = embed
        finally:
            pass

    user = await client.fetch_user(user_id)
    try:
        await user.send(embed=message)
    except Exception as e:
        print(f"Failed to send message to user {user_id}: {e}")

@client.event
async def on_command_error(ctx, error):
    await handle_command_error(ctx, error)

client.run(TOKEN)
