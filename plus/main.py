import discord_ios
import discord
from discord.ext import commands, tasks
from dotenv import dotenv_values
import os
import redis
import asyncpg
import aiohttp
import asyncio
from utils.db import redis_client, get_db_connection

config = dotenv_values(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
DATA_DB = config['DATA_DB']
TOKEN = config["HEIST_PLUS_TOKEN"]

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
        data = {
            "embeds": [embed.to_dict()]
        }

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

class HeistPlus(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(
            command_prefix="+",
            intents=intents,
            help_command=None)
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        self.db_pool = None

    async def setup_hook(self):
        self.db_pool = await asyncpg.create_pool(dsn=DATA_DB)
        for cog in ["plus.cogs.roleplay", "plus.cogs.stalk", "plus.cogs.info"]:
            await self.load_extension(cog)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print(f'Using {self.shard_count} shards')
        await self.tree.sync()
        await self.preload_stalk()

    async def preload_stalk(self):
        async with get_db_connection() as conn:
            stalk_lists = await conn.fetch("SELECT stalker_id, target_id FROM stalking")

        for stalk_list in stalk_lists:
            stalker_id = stalk_list["stalker_id"]
            target_id = stalk_list["target_id"]
            await redis_client.sadd(f"stalker:{target_id}:stalkers", stalker_id)
            await redis_client.sadd(f"stalker:{stalker_id}:targets", target_id)

    async def on_interaction(self, interaction: discord.Interaction):
        uid = interaction.user.id
        user = interaction.user.name
        redis_key = f"user:{uid}:exists"
        user_exists_in_cache = self.redis_client.get(redis_key)

        if user_exists_in_cache:
            user_exists = True
        else:
            if self.db_pool is None:
                self.db_pool = await asyncpg.create_pool(dsn=DATA_DB)

            user_exists = await self.db_pool.fetchval("SELECT 1 FROM user_data WHERE user_id = $1", str(uid))

            if not user_exists:
                embed = discord.Embed(
                    description="You must authorize & use [Heist](https://discord.com/oauth2/authorize?client_id=1225070865935368265) once in order to use Heist+.",
                    color=0x000f
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            self.redis_client.set(redis_key, '1', ex=1200)

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
        embed.set_footer(text="part of heist+")

        if interaction.type == discord.InteractionType.application_command:
            await send_log_to_webhook(embed)

client = HeistPlus()

client.run(f"{TOKEN}")