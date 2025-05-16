import discord
from discord import app_commands, Interaction, User, Embed, Attachment, File, Forbidden
from discord.ui import Button, View, Modal, TextInput
from discord.ext import commands, tasks
import re, random, json, datetime, asyncio, os, tempfile, aiofiles, io
from utils.cd import cooldown
from utils.db import check_blacklisted, check_booster, check_donor, check_owner, get_db_connection, redis_client
from utils.cache import get_embed_color
from utils.error import error_handler
from utils.embed import cembed
from utils import default, permissions, messages
from dotenv import dotenv_values
from typing import Optional, List
import aiohttp, textwrap, aiofiles
import asyncpg, asyncio, string, redis
import importlib
import psutil, subprocess, gc
import aiofiles.os

footer = "heist.lol"

packages = [
    "cogs.discord", "cogs.fun", "cogs.games", "cogs.economy", "cogs.info", "cogs.music", "cogs.owner", "cogs.roleplay", "cogs.settings", "cogs.socials", "cogs.utils", "cogs.voice"]

config = dotenv_values(".env")
CLOUDFLARE_KEY = config["CLOUDFLARE_API_KEY"]
CLOUDFLARE_HEISTLOL_ID = config["CLOUDFLARE_HEISTLOL_ID"]
CLOUDFLARE_LURING_ID = config["CLOUDFLARE_LURING_ID"]
CLOUDFLARE_CURSING_ID = config["CLOUDFLARE_CURSING_ID"]

class Owner(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.redis = redis_client
        self.redis_client = redis_client
        self.status_rotation = False
        self.status_list = []
        self.custom_status = None
        self.current_list = "status/status.txt"
        self.status_index = 0
        self.current_status = None
        self.client.loop.create_task(self.initialize())
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    async def ensure_session(self):
        if not hasattr(self, "session") or self.session is None:
            print("Session does not exist, creating new one")
            self.session = aiohttp.ClientSession()
        elif self.session.closed:
            print("Session is closed, recreating")
            self.session = aiohttp.ClientSession()

    async def initialize(self):
        await self.load_status_list()
        if self.status_list:
            self.current_status = self.status_list[0]
            await self.set_initial_status()
        self.update_status.start()

    admin = app_commands.Group(
        name="o", 
        description="Staff only commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    item = app_commands.Group(
        name="item", 
        description="Item-related Heist Staff only commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        parent=admin
    )

    async def load_status_list(self):
        try:
            async with aiofiles.open(self.current_list, mode='r') as file:
                self.status_list = [line.strip() for line in await file.readlines() if line.strip()]
        except Exception as e:
            print(f"Error loading status list: {e}")
            self.status_list = ["🔗 heist.lol"]
            self.current_status = self.status_list[0]

    async def set_initial_status(self):
        try:
            user_count = await self.fetch_count()
            if self.custom_status:
                status = self.custom_status.format(user_count=user_count) if user_count is not None else self.custom_status.format(user_count="N/A")
            else:
                status = self.current_status.format(user_count=user_count) if user_count is not None else self.current_status
            
            await self.client.change_presence(activity=discord.CustomActivity(name=status))
        except Exception as e:
            print(f"Error setting initial status: {e}")

    @tasks.loop(minutes=1)
    async def update_status(self):
        try:
            user_count = await self.fetch_count()
            
            if self.status_rotation and self.status_list:
                self.status_index = (self.status_index + 1) % len(self.status_list)
                status = self.status_list[self.status_index]
                status = status.format(user_count=user_count) if user_count is not None else status.format(user_count="N/A")
                self.current_status = status
                await self.client.change_presence(activity=discord.CustomActivity(name=status))
            elif self.custom_status:
                status = self.custom_status.format(user_count=user_count) if user_count is not None else self.custom_status.format(user_count="N/A")
                await self.client.change_presence(activity=discord.CustomActivity(name=status))
        except Exception as e:
            print(f"Error updating status: {e}")

    async def fetch_count(self):
        try:
            url = "http://127.0.0.1:5002/getcount"
            await self.ensure_session()
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["user_count"]
                else:
                    print(f"Failed to fetch user count: {response.status}")
                    return None
        except Exception as e:
            print(f"Error fetching user count: {e}")
            return None

    class SetStatusModal(Modal, title="Set Custom Status"):
        def __init__(self, client):
            super().__init__()
            self.client = client
            self.status_input = TextInput(
                label="Enter Custom Status",
                placeholder="e.g., 🔗 heist.lol - {user_count:,} kittens",
                style=discord.TextStyle.short,
                required=True
            )
            self.add_item(self.status_input)

        async def on_submit(self, interaction: discord.Interaction):
            status = self.status_input.value
            owner_cog = self.client.get_cog("Owner")
            owner_cog.custom_status = status
            owner_cog.status_rotation = False
            user_count = await owner_cog.fetch_count()
            formatted_status = status.format(user_count=user_count) if user_count is not None else status.format(user_count="N/A")
            await self.client.change_presence(activity=discord.CustomActivity(name=formatted_status))
            await interaction.response.send_message(f"Custom status set to: {formatted_status}", ephemeral=True)

    class UseNewListModal(Modal, title="Use New List"):
        def __init__(self, client):
            super().__init__()
            self.client = client
            self.list_input = TextInput(
                label="Enter List Name",
                placeholder="e.g., status.txt or pbc.txt",
                style=discord.TextStyle.short,
                required=True
            )
            self.add_item(self.list_input)

        async def on_submit(self, interaction: discord.Interaction):
            list_name = self.list_input.value
            cog = self.client.get_cog("Owner")
            new_list_path = f"status/{list_name}"
            if os.path.exists(new_list_path):
                cog.current_list = new_list_path
                await cog.load_status_list()
                cog.status_index = 0
                if cog.status_rotation:
                    user_count = await cog.fetch_count()
                    first_status = cog.status_list[0]
                    formatted_status = first_status.format(user_count=user_count) if user_count is not None else first_status.format(user_count="N/A")
                    await cog.client.change_presence(activity=discord.CustomActivity(name=formatted_status))
                await interaction.response.send_message(f"Now using list: **{list_name}**", ephemeral=True)
            else:
                available_lists = [f for f in os.listdir("status") if f.endswith(".txt")]
                await interaction.response.send_message(
                    f"List **{list_name}** not found. Available lists: **{', '.join(available_lists)}**",
                    ephemeral=True
                )

    @admin.command()
    @app_commands.describe(action="Choose an action to control the bot's status.")
    @app_commands.choices(action=[
        app_commands.Choice(name="Set Custom Status", value="custom"),
        app_commands.Choice(name="Resume Auto Rotation", value="resume"),
        app_commands.Choice(name="Pause Auto Rotation", value="pause"),
        app_commands.Choice(name="Use New List", value="newlist")
    ])
    @app_commands.check(permissions.is_owner)
    async def setstatus(self, interaction: discord.Interaction, action: str, status: str = None):
        """Control the bot's status."""
        if action == "custom":
            if status:
                self.custom_status = status
                self.status_rotation = False
                user_count = await self.fetch_count()
                formatted_status = status.format(user_count=user_count) if user_count is not None else status.format(user_count="N/A")
                await self.client.change_presence(activity=discord.CustomActivity(name=formatted_status))
                await interaction.response.send_message(f"Custom status set to: {formatted_status}", ephemeral=True)
            else:
                await interaction.response.send_modal(self.SetStatusModal(self.client))
        elif action == "resume":
            self.status_rotation = True
            await self.load_status_list()
            self.status_index = 0
            user_count = await self.fetch_count()
            if self.status_list:
                first_status = self.status_list[0]
                formatted_status = first_status.format(user_count=user_count) if user_count is not None else first_status.format(user_count="N/A")
                await self.client.change_presence(activity=discord.CustomActivity(name=formatted_status))
            await interaction.response.send_message("Auto rotation resumed.", ephemeral=True)
        elif action == "pause":
            self.status_rotation = False
            current_status = self.client.activity.name if self.client.activity else "No activity set"
            await interaction.response.send_message(f"Auto rotation paused. Current status will remain: {current_status}", ephemeral=True)
        elif action == "newlist":
            await interaction.response.send_modal(self.UseNewListModal(self.client))
        else:
            await interaction.response.send_message("Invalid action.", ephemeral=True)

    @admin.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.describe(user="The user to send the message to.", message="The message to send to the user.", vm="Voice message to be sent.")
    @app_commands.check(permissions.is_owner)
    async def dm(self, interaction: Interaction, user: User, message: str, vm: Attachment = None):
        """DMs a discord user."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if vm:
                if not vm.content_type.startswith("audio/"):
                    await interaction.followup.send("❌ The provided file is not a valid audio file.", ephemeral=True)
                    return
                
                tempp = os.path.join(tempfile.gettempdir(), vm.filename)
                await vm.save(tempp)

                opus_path = tempp.rsplit('.', 1)[0] + ".opus"

                try:
                    if not tempp.endswith(".opus"):
                        process = await asyncio.create_subprocess_exec(
                            "ffmpeg", "-i", tempp, "-c:a", "libopus", "-b:a", "192k", opus_path,
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                        )
                        await process.communicate()
                    else:
                        opus_path = tempp

                    async with aiofiles.open(opus_path, 'rb') as audio_file:
                        await user.send(file=File(audio_file.name, filename=os.path.basename(opus_path)), voice_message=True)
                    
                    await interaction.followup.send("✉️ Voice message sent.", ephemeral=True)
                except Exception as conversion_error:
                    await interaction.followup.send(f"❌ Failed to process voice message: {conversion_error}", ephemeral=True)
                finally:
                    for file in [tempp, opus_path]:
                        if os.path.exists(file):
                            await aiofiles.os.remove(file)
            else:
                await user.send(message)
                await interaction.followup.send("✉️ Message sent.", ephemeral=True)
        
        except Forbidden:
            await interaction.followup.send("❌ I cannot send messages to this user. They may have DMs disabled or blocked the bot.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to send message.\n> {e}", ephemeral=True)

    async def get_blacklisted_users(self):
        async with get_db_connection() as conn:
            result = await conn.fetch('SELECT user_id FROM blacklisted')
            return [user['user_id'] for user in result]

    async def update_blacklist(self, user_id, action, reason=None):
        async with get_db_connection() as conn:
            user_id_str = str(user_id)
            if action == "add":
                await conn.execute('INSERT INTO blacklisted (user_id, reason) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET reason = EXCLUDED.reason', user_id_str, reason)
                await self.redis_client.setex(f"blacklisted:{user_id_str}", 300, "True")
            elif action == "remove":
                await conn.execute('DELETE FROM blacklisted WHERE user_id = $1', user_id_str)
                await self.redis_client.setex(f"blacklisted:{user_id_str}", 300, "False")

    async def update_user_status(self, user_id, status_type, action):
        async with get_db_connection() as conn:
            user_id_str = str(user_id)
            if status_type == "premium":
                if action == "add":
                    await conn.execute(
                        'INSERT INTO donors (user_id, donor_status) VALUES ($1, 1) ON CONFLICT (user_id) DO NOTHING', 
                        user_id_str
                    )
                    await self.redis_client.setex(f"donor:{user_id_str}", 300, "True")
                elif action == "remove":
                    await conn.execute(
                        'DELETE FROM donors WHERE user_id = $1', 
                        user_id_str
                    )
                    await self.redis_client.setex(f"donor:{user_id_str}", 300, "False")
            elif status_type == "famous":
                if action == "add":
                    await conn.execute(
                        'UPDATE user_data SET fame = TRUE WHERE user_id = $1 AND fame IS FALSE', 
                        user_id_str
                    )
                    await self.redis_client.setex(f"famous:{user_id_str}", 300, "True")
                elif action == "remove":
                    await conn.execute(
                        'UPDATE user_data SET fame = FALSE WHERE user_id = $1 AND fame IS TRUE', 
                        user_id_str
                    )
                    await self.redis_client.setex(f"famous:{user_id_str}", 300, "False")

    async def update_admin(self, user_id, action):
        async with get_db_connection() as conn:
            user_id_str = str(user_id)
            if action == "add":
                await conn.execute('INSERT INTO owners (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING', user_id_str)
                await self.redis_client.setex(f"owner:{user_id_str}", 300, "True")
            elif action == "remove":
                await conn.execute('DELETE FROM owners WHERE user_id = $1', user_id_str)
                await self.redis_client.setex(f"owner:{user_id_str}", 300, "False")

    @admin.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(action="Either add or remove a user from the blacklist.", user="The user to apply the action to.", reason="Optional reason of the action.")
    @app_commands.check(permissions.is_owner)
    async def blacklist(self, interaction: Interaction, action: str, user: User = None, reason: str = f"Breaking [Heist's Terms of Service](<https://{footer}/terms>)."):
        """Add or remove a user from the blacklist."""
        await interaction.response.defer(thinking=True)
        user = user or interaction.user
        user_id = str(user.id)

        if action == "add":
            await self.update_blacklist(user_id, "add", reason)
            await permissions.invalidate_cache(user_id)

            embed = Embed(
                title="<:warning:1350239604925530192> Notice",
                description=f"You have been **blacklisted** from using [**Heist**](<https://{footer}>).\nReason: **{reason}**\n\nIf you think this decision is wrong, you may appeal [**here**](https://discord.gg/gVarzmGAJC).",
                color=0x3b3b3b
            )
            embed.set_footer(text="heist.lol", icon_url="https://git.cursi.ng/heist.png?c")

            try:
                await user.send(embed=embed)
            except Exception as e:
                pass

            await interaction.followup.send(f"{user} has been blacklisted.", ephemeral=False)
        
        elif action == "remove":
            await self.update_blacklist(user_id, "remove")
            await permissions.invalidate_cache(user_id)

            embed = Embed(
                title="<:warning:1350239604925530192> Notice",
                description=f"You have been **unblacklisted** from using [**Heist**](<https://{footer}>).",
                color=0x3b3b3b
            )
            embed.set_footer(text="heist.lol", icon_url="https://git.cursi.ng/heist.png?c")

            try:
                await user.send(embed=embed)
            except Exception as e:
                pass

            await interaction.followup.send(f"{user} has been unblacklisted.", ephemeral=False)
        
        elif action == "removeall":
            blacklisted_users = await self.get_blacklisted_users()

            for blacklisted_user_id in blacklisted_users:
                await self.update_blacklist(blacklisted_user_id, "remove")

                try:
                    user = await self.client.fetch_user(blacklisted_user_id)
                    embed = Embed(
                        title="<:warning:1350239604925530192> Notice",
                        description=f"You have been **unblacklisted** from using Heist.\nReason: **Everyone has been unblacklisted.**\n-# Allow up to 5 minutes for this to process.",
                        color=0x3b3b3b
                    )
                    embed.set_footer(text="heist.lol", icon_url="https://git.cursi.ng/heist.png?c")
                    await user.send(embed=embed)
                except Exception as e:
                    print(e)

            await interaction.followup.send("All users have been unblacklisted.", ephemeral=False)

        else:
            await interaction.followup.send("Invalid action. Use `add`, `remove`, or `removeall`.", ephemeral=True)

    @admin.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_owner)
    @app_commands.describe(action="Either add or remove status.", status="The status to apply.", user="The user to apply the action to.")
    @app_commands.choices(status=[
        app_commands.Choice(name="Premium", value="premium"),
        app_commands.Choice(name="Famous", value="famous"),
        app_commands.Choice(name="Trusted", value="trusted")
    ])
    async def grant(self, interaction: Interaction, action: str, status: str, user: User = None):
        """Grant or remove status from someone."""
        await interaction.response.defer(thinking=True)
        user = user or interaction.user
        user_id = str(user.id)

        loading_message = await interaction.followup.send(f"<a:loading:1269644867047260283> {interaction.user.mention}: please wait, this might take a while..", ephemeral=True)

        if action == "add":
            await self.update_user_status(user_id, status, "add")
            await permissions.invalidate_cache(user_id)

            if status == "premium":
                embed = Embed(
                    title="<:warning:1350239604925530192> Notice",
                    description=f"You have been given **Premium** status on Heist.\nThank you for your donation!\n\nMake sure to join our [**Discord server**](https://discord.gg/gVarzmGAJC) to claim more perks.",
                    color=0x3b3b3b
                )
                embed.set_footer(text="heist.lol", icon_url="https://git.cursi.ng/heist.png?c")

                try:
                    await user.send(embed=embed)
                except Exception as e:
                    pass

                await loading_message.edit(content=f"<:premium:1311062205650833509> {user} has been given premium status.")

            elif status == "famous":
                try:
                    await user.send("You have been granted <:famous:1311067416251596870> **`Famous`** on Heist.")
                except Exception as e:
                    pass

                await loading_message.edit(content=f"<:famous:1311067416251596870> {user} has been given famous status.")

            elif status == "trusted":
                limited_key = f"user:{user_id}:limited"
                untrusted_key = f"user:{user_id}:untrusted"
                await self.redis.delete(limited_key)
                await self.redis.delete(untrusted_key)

                await loading_message.edit(content=f"<:trusted:1311067416251596870> {user} is now trusted.")

        elif action == "remove":
            await self.update_user_status(user_id, status, "remove")
            await permissions.invalidate_cache(user_id)

            if status == "premium":
                embed = Embed(
                    title="<:warning:1350239604925530192> Notice",
                    description=f"Your **Premium** status has been removed on Heist.\n\nThis was unexpected? Make a ticket [**here**](https://discord.gg/gVarzmGAJC).",
                    color=0x3b3b3b
                )
                embed.set_footer(text="heist.lol", icon_url="https://git.cursi.ng/heist.png?c")

                try:
                    await user.send(embed=embed)
                except Exception as e:
                    pass

                await loading_message.edit(content=f"<:premium:1311062205650833509> {user} no longer has premium status.")

            elif status == "famous":
                try:
                    await user.send("Your <:famous:1311067416251596870> **`Famous`** has been removed on Heist.")
                except Exception as e:
                    pass

                await loading_message.edit(content=f"<:famous:1311067416251596870> {user} no longer has famous status.")

            elif status == "trusted":
                limited_key = f"user:{user_id}:limited"
                untrusted_key = f"user:{user_id}:untrusted"
                await self.redis.setex(limited_key, 7 * 24 * 60 * 60, '')
                await self.redis.setex(untrusted_key, 60 * 24 * 60 * 60, '')
                await loading_message.edit(content=f"<:trusted:1311067416251596870> {user} is no longer trusted.")

        else:
            await interaction.followup.send("Invalid action. Use `add` or `remove`.", ephemeral=True)

    @admin.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    @app_commands.check(permissions.is_creator)
    @app_commands.describe(action="Either add or remove a user as admin.", user="The user to apply the action to.")
    async def staff(self, interaction: Interaction, action: str, user: User = None):
        """Add or remove a user as Heist staff."""
        user = user or interaction.user
        user_id = str(user.id)

        if action == "add":
            await self.update_admin(user_id, "add")
            await permissions.invalidate_cache(user_id)
            await interaction.response.send_message(f"{user} is now admin.", ephemeral=True)
        elif action == "remove":
            await self.update_admin(user_id, "remove")
            await permissions.invalidate_cache(user_id)
            await interaction.response.send_message(f"{user} is no longer admin.", ephemeral=True)
        else:
            await interaction.response.send_message("Invalid action. Use `add` or `remove`.", ephemeral=True)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.check(permissions.is_creator)
    async def reseteco(self, interaction: Interaction, user: User = None):
        """Reset economy data."""
        await interaction.response.defer(thinking=True)

        cache_key = f"resetecoconf:{interaction.user.id}"
        cached_confirmation = await self.redis.get(cache_key)

        if not cached_confirmation:
            await self.redis.set(cache_key, "pending", ex=20)
            await interaction.followup.send("Run the command again within 20 seconds to initiate reset.", ephemeral=True)
            return

        if user:
            await self.reset_user_economy(user.id)
            await interaction.followup.send(messages.success(interaction.user, f"Successfully reset {user.name}'s economy data."), ephemeral=True)
        else:
            await self.reset_all_economy()
            await interaction.followup.send(messages.success(interaction.user, "✅ Successfully reset everyone's economy data."), ephemeral=True)

        await self.redis.delete(cache_key)

    async def reset_user_economy(self, user_id: int):
        cache_key = f"economy:{user_id}"
        async with get_db_connection() as conn:
            await conn.execute(
                """
                INSERT INTO economy (user_id, cash, bank, bank_limit)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) 
                DO UPDATE SET cash = EXCLUDED.cash, bank = EXCLUDED.bank, bank_limit = EXCLUDED.bank_limit
                """,
                str(user_id), 5000, 0, 50000
            )
        await self.redis.delete(cache_key)

    async def reset_all_economy(self):
        async with get_db_connection() as conn:
            await conn.execute(
                """
                INSERT INTO economy (user_id, cash, bank, bank_limit)
                SELECT user_id, 5000, 0, 50000 FROM economy
                ON CONFLICT (user_id) 
                DO UPDATE SET cash = EXCLUDED.cash, bank = EXCLUDED.bank, bank_limit = EXCLUDED.bank_limit
                """
            )
        await self.redis.flushdb()

    async def generate_api_key(self):
        prefix = "Heist-"
        key_length = 20
        random_characters = string.ascii_letters + string.digits
        random_key = ''.join(random.choice(random_characters) for _ in range(key_length))
        return f"{prefix}{random_key}"

    async def save_api_key(self, api_key):
        async with get_db_connection() as conn:
            try:
                await conn.execute('INSERT INTO api_keys (api_key) VALUES ($1) ON CONFLICT (api_key) DO NOTHING', api_key)
                return True
            except Exception as e:
                print(f"Failed to save API key: {e}")
                return False

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.check(permissions.is_owner)
    async def generateapikey(self, interaction: Interaction):
        """Generate a new API key."""
        api_key = await self.generate_api_key()
        if await self.save_api_key(api_key):
            await interaction.response.send_message(
                f"""New API key generated: {api_key}\n\n```/embed title: Your Heist Bot API Key description: Your API key is `{api_key}`\nEndpoints: https://api.csyn.me/docs\nAPI Key Usage: `headers = {{"X-API-Key": API_KEY}}`\n  **DO NOT SHARE THIS WITH ANYBODY.**```""",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("Failed to generate API key.", ephemeral=True)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.check(permissions.is_owner)
    async def listapikeys(self, interaction: Interaction):
        """List all API keys."""
        try:
            async with get_db_connection() as conn:
                rows = await conn.fetch('SELECT api_key FROM api_keys')
                api_keys_str = "\n".join([row['api_key'] for row in rows])

                await interaction.response.send_message(
                    f"API Keys:\n```\n{api_keys_str}\n```", 
                    ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to list API keys: {e}", 
                ephemeral=True
            )

    async def delete_api_key(self, api_key):
        async with get_db_connection() as conn:
            try:
                result = await conn.execute('DELETE FROM api_keys WHERE api_key = $1', api_key)
                return result == "DELETE 1"
            except Exception as e:
                print(f"Failed to delete API key: {e}")
                return False

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.check(permissions.is_owner)
    @app_commands.describe(api_key="The API key to delete.")
    async def deleteapikey(self, interaction: Interaction, api_key: str):
        """Delete an API key."""
        if await self.delete_api_key(api_key):
            await interaction.response.send_message(f"API key `{api_key}` has been deleted.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Failed to delete API key `{api_key}`. It may not exist.", ephemeral=True)

    @admin.command()
    @app_commands.describe(
        description="Update description.",
        added="What was added.",
        removed="What was removed."
    )
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.check(permissions.is_owner)
    async def update(self, interaction: Interaction, description: str, added: str = None, removed: str = None):
        """Post update changelogs."""
        
        if description is None and added is None and removed is None:
            await interaction.response.send_message("What did you add? What did you remove? C'mon, mate.", ephemeral=True)
            return

        guild = self.client.get_guild(1336528911756165172)
        channel = guild.get_channel(1362175307896979516) if guild else None

        if not channel:
            await interaction.response.send_message("Couldn't find announcements channel.", ephemeral=True)
            return

        embed = await cembed(
            interaction,
            title="Heist - Changelogs",
            description=description.replace('\\n', '\n')
        )

        if added:
            added_lines = added.replace('\\n', '\n').split('\n')
            added_text = '\n'.join(f"+ {line}" for line in added_lines)
            embed.add_field(
                name="Added",
                value=f"```diff\n{added_text}\n```",
                inline=False
            )

        if removed:
            removed_lines = removed.replace('\\n', '\n').split('\n')
            removed_text = '\n'.join(f"- {line}" for line in removed_lines)
            embed.add_field(
                name="Removed",
                value=f"```diff\n{removed_text}\n```",
                inline=False
            )

        await channel.send(embed=embed)
        
        success_embed = await cembed(
            interaction,
            description=messages.success(interaction.user, "Update log has been sent.")
        )
        await interaction.response.send_message(embed=success_embed)

    # @app_commands.command() 
    # @app_commands.allowed_installs(guilds=False, users=True)
    # @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    # @app_commands.check(permissions.is_owner)
    # async def collect(self, interaction: Interaction):
    #     """Collect garbage stored in RAM."""
    #     await interaction.response.defer(thinking=True)
    #     process = psutil.Process()

    #     memory_changes = []

    #     def get_memory_diff():
    #         nonlocal before
    #         after = process.memory_info().rss / (1024 * 1024)
    #         diff = before - after
    #         before = after
    #         return diff

    #     before = process.memory_info().rss / (1024 * 1024)

    #     if hasattr(self, '_audio_segments'):
    #         for segment in self._audio_segments:
    #             del segment
    #         self._audio_segments = []
    #         diff = get_memory_diff()
    #         memory_changes.append(f"-# {diff:.2f} MB decrease from cleaning audio segments")

    #     if hasattr(self, '_audio_buffers'):
    #         for buffer in self._audio_buffers:
    #             buffer.close()
    #         self._audio_buffers = []
    #         diff = get_memory_diff()
    #         memory_changes.append(f"- {diff:.2f} MB decrease from cleaning audio buffers")

    #     for proc in psutil.process_iter(['pid', 'name']):
    #         try:
    #             if 'ffmpeg' in proc.name().lower():
    #                 proc.kill()
    #         except (psutil.NoSuchProcess, psutil.AccessDenied):
    #             pass
    #     diff = get_memory_diff()
    #     memory_changes.append(f"-# {diff:.2f} MB decrease from killing ffmpeg processes")

    #     if hasattr(self, '_sessions'):
    #         for session in self._sessions:
    #             if not session.closed:
    #                 await session.close()
    #         self._sessions = []
    #         diff = get_memory_diff()
    #         memory_changes.append(f"-# {diff:.2f} MB decrease from cleaning sessions")

    #     async with aiohttp.ClientSession() as session:
    #         session.cookie_jar.clear()
    #     diff = get_memory_diff()
    #     memory_changes.append(f"-# {diff:.2f} MB decrease from clearing cookies")

    #     gc.collect()
    #     diff = get_memory_diff()
    #     memory_changes.append(f"-# {diff:.2f} MB decrease from garbage collection")

    #     import ctypes
    #     ctypes.CDLL("libc.so.6").malloc_trim(0)
    #     diff = get_memory_diff()
    #     memory_changes.append(f"-# {diff:.2f} MB decrease from malloc_trim")

    #     after = process.memory_info().rss / (1024 * 1024)
    #     total_diff = before - after

    #     response_message = (
    #         f"Feels like a breeze.. From **{before:.2f} MB** to **{after:.2f} MB**, "
    #         f"that's a **{(total_diff / before) * 100:.2f}%** decrease!\n\n"
    #         + "\n".join(memory_changes)
    #     )

    #     await interaction.followup.send(response_message, ephemeral=False)

    @admin.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(code="The Python code to execute.")
    @app_commands.check(permissions.is_owner)
    async def py(self, interaction: Interaction, *, code: str):
        """Execute Python code on the bot's instance."""
        env = {
            'self': self,
            'bot': self.client,
            'interaction': interaction,
            'discord': discord,
            '__import__': __import__
        }
        
        if code.startswith('```'):
            code = code.split('\n', 1)[1] if '\n' in code else ''
        if code.endswith('```'):
            code = code[:-3]
        
        code = f'async def _eval():\n{textwrap.indent(code, "    ")}'
        
        try:
            exec_namespace = {}
            exec(code, env, exec_namespace)
            
            _eval = exec_namespace["_eval"]
            result = await _eval()
            
            if not interaction.response.is_done():
                output = str(result)
                if len(output) > 1990:
                    file = discord.File(io.StringIO(output), filename='output.py')
                    await interaction.response.send_message("Output was too long, sent as file:", file=file, ephemeral=True)
                else:
                    await interaction.response.send_message(f"```py\n{output}\n```", ephemeral=True)
            else:
                print(result)
        
        except Exception as e:
            await error_handler(interaction, e)

    @admin.command() 
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_owner)
    async def sync(self, interaction: Interaction):
        """Sync application commands."""
        await interaction.response.defer(thinking=True)
        synced = await self.client.tree.sync()
        gc.collect()
        await interaction.followup.send(f"Resynced {len(synced)} commands with Discord.", ephemeral=True)

    @admin.command() 
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(package="The cog to reload.")
    @app_commands.check(permissions.is_owner)
    async def reload(self, interaction: Interaction, package: str):
        """Reloads a cog."""
        if package.strip().lower() == "scanservers":
            await interaction.response.defer(thinking=True)
            count = 0
            total = len(self.client.guilds)
            
            await interaction.followup.send(f"Scanning {total} servers for those with less than 100 members...", ephemeral=True)
            
            for guild in self.client.guilds:
                if guild.member_count < 100:
                    try:
                        await self.client.send_leave_message(guild)
                        await guild.leave()
                        count += 1
                        print(f"Left guild {guild.name} (ID: {guild.id}) due to low member count.")
                    except Exception as e:
                        print(f"Error leaving guild {guild.id}: {e}")
            
            await interaction.followup.send(f"Scan complete. Left {count} small servers out of {total} total servers.", ephemeral=True)
            return

        try:
            await interaction.response.defer(thinking=True)

            if package.strip().lower() == "all":
                success_count = 0
                failed_count = 0
                failed_cogs = []

                for cog_name in list(self.client.extensions.keys()):
                    try:
                        await self.client.unload_extension(cog_name)
                        await self.client.load_extension(cog_name)
                        success_count += 1
                    except Exception as e:
                        failed_count += 1
                        failed_cogs.append((cog_name, str(e)))

                if failed_count == 0:
                    await interaction.followup.send(messages.success(interaction.user, f"Successfully reloaded all {success_count} cogs."), ephemeral=True)
                else:
                    failed_messages = "\n".join([f"- {name}: {error}" for name, error in failed_cogs])
                    await interaction.followup.send(
                        messages.warn(interaction.user, f"Reloaded {success_count} cogs successfully. Failed to reload {failed_count} cogs:\n{failed_messages}"),
                        ephemeral=True
                    )
                return

            if package.startswith("utils."):
                module_name = package
                try:
                    module = importlib.import_module(module_name)
                    importlib.reload(module)
                    await interaction.followup.send(messages.success(interaction.user, f"Reloaded module '{module_name}' successfully."), ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(messages.warn(interaction.user, f"Failed to reload module '{module_name}': {e}"), ephemeral=True)
                return

            if package in self.client.extensions:
                print(f"Unloading extension '{package}'...")
                await self.client.unload_extension(package)
            else:
                print(f"Extension '{package}' is not loaded, skipping unload.")

            print(f"Loading extension '{package}'...")
            await self.client.load_extension(package)
            await interaction.followup.send(messages.success(interaction.user, f"Reloaded extension '{package}' successfully."), ephemeral=True)

        except Exception as e:
            await interaction.followup.send(messages.warn(interaction.user, f"Failed to reload extension '{package}'."), ephemeral=True)
            
            try:
                module = importlib.import_module(package)
                importlib.reload(module)
                
                await module.setup(self.client)
                
                await interaction.followup.send(messages.success(interaction.user, f"Successfully re-imported and reloaded '{package}' manually."), ephemeral=True)
            except Exception as manual_error:
                await interaction.followup.send(messages.warn(interaction.user, f"Failed to re-import and reload '{package}' manually: {manual_error}"), ephemeral=True)

    @reload.autocomplete("package")
    async def reload_autocomplete(self, interaction: Interaction, current: str):
        filtered_packages = [app_commands.Choice(name=package, value=package) for package in packages if current.lower() in package.lower()]
        return filtered_packages

    async def allow_connect_logic(self, cti, user):
        gyat = str(user.id)
        async with get_db_connection() as conn:
            result = await conn.fetchrow("SELECT allowed, connected_domain FROM allowed_users WHERE user_id = $1", gyat)
            if result and result["allowed"]:
                await conn.execute(
                    "UPDATE allowed_users SET allowed = FALSE, connected_domain = NULL WHERE user_id = $1",
                    gyat
                )
                response_message = messages.success(user, f"{user.mention} has been disallowed from connecting domains.")
            else:
                await conn.execute(
                    "INSERT INTO allowed_users (user_id, allowed) VALUES ($1, TRUE) ON CONFLICT (user_id) DO UPDATE SET allowed = TRUE",
                    gyat
                )
                response_message = messages.success(user, f"{user.mention} has been allowed to connect domains.")

            if isinstance(cti, discord.Interaction):
                await cti.followup.send(response_message, ephemeral=True)
            else:
                await cti.send(response_message)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.check(permissions.is_owner)
    async def allowconnect(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(ephemeral=True)
        await self.allow_connect_logic(interaction, user)

    @commands.command(name="allowconnect", aliases=["ac"])
    @commands.check(permissions.is_owner)
    async def allowconnect_prefix(self, ctx, user: discord.User):
        await self.allow_connect_logic(ctx, user)

    async def domain_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        domains = ["heist.lol", "luri.ng", "cursi.ng"]
        return [
            app_commands.Choice(name=domain, value=domain)
            for domain in domains if current.lower() in domain.lower()
        ]

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.autocomplete(domain=domain_autocomplete)
    @app_commands.check(permissions.is_blacklisted)
    async def connect(self, interaction: discord.Interaction, domain: str, verification: str):
        allowed_domains = {
            "heist.lol": CLOUDFLARE_HEISTLOL_ID,
            "luri.ng": CLOUDFLARE_LURING_ID,
            "cursi.ng": CLOUDFLARE_CURSING_ID
        }
        
        if domain not in allowed_domains:
            await interaction.response.send_message(
                messages.warn(interaction.user, f"**{domain}** is not a supported domain."),
                ephemeral=True
            )
            return
        
        zone_id = allowed_domains[domain]
        gyat = str(interaction.user.id)
        await interaction.response.defer(ephemeral=True)
        
        async with get_db_connection() as conn:
            result = await conn.fetchrow("SELECT allowed, verification_key FROM allowed_users WHERE user_id = $1", gyat)
            if not result or not result["allowed"]:
                await interaction.followup.send(
                    messages.warn(interaction.user, f"You don't have permission to connect: **{domain}**"),
                    ephemeral=True
                )
                return

        loop = asyncio.get_event_loop()
        try:
            is_valid = await loop.run_in_executor(
                None, 
                lambda: re.match(r"^dh=[a-zA-Z0-9]+$", verification) is not None
            )
            if not is_valid:
                await interaction.followup.send(
                    "The verification code you have entered is invalid, please use </connectguide:1351708285404713035>.",
                    ephemeral=True
                )
                return
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error validating verification code: {str(e)}",
                ephemeral=True
            )
            return

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {CLOUDFLARE_KEY}",
                "Content-Type": "application/json"
            }

            async with get_db_connection() as conn:
                old_verification_key = await conn.fetchval("SELECT verification_key FROM allowed_users WHERE user_id = $1", gyat)

            if old_verification_key:
                async with session.get(
                    f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?type=TXT&name=_discord.{domain}&content={old_verification_key}",
                    headers=headers
                ) as check_response:
                    check_result = await check_response.json()
                    if check_response.status == 200 and check_result["result"]:
                        record_id = check_result["result"][0]["id"]
                        async with session.delete(
                            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}",
                            headers=headers
                        ) as delete_response:
                            if delete_response.status != 200:
                                await interaction.followup.send(
                                    messages.warn(interaction.user, f"Failed to clean up old TXT record for **{domain}**."),
                                    ephemeral=True
                                )
                                return

            data = {
                "type": "TXT",
                "name": f"_discord.{domain}",
                "content": verification,
                "ttl": 120
            }
            async with session.post(
                f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    async with get_db_connection() as conn:
                        await conn.execute(
                            "UPDATE allowed_users SET connected_domain = $1, verification_key = $2 WHERE user_id = $3",
                            domain, verification, gyat
                        )
                    await interaction.followup.send(
                        messages.success(interaction.user, f"Successfully connected **{domain}**!\n"
                        "**Please allow __2 minutes__ before attempting to link it.**"),
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        messages.success(interaction.user, f"Failed to verify **{domain}**. Please try again."),
                        ephemeral=True
                    )

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.check(permissions.is_blacklisted)
    async def connectguide(self, interaction: discord.Interaction):
        await interaction.response.send_message("settings -> connections -> add domain -> **heist.lol/luri.ng** -> copy **content** value\n\nuse </connect:1351708285404713033> (domain: heist.lol/luri.ng), paste content's value in the **verification** parameter.", ephemeral=True)

    # @item.command()
    # @app_commands.allowed_installs(guilds=False, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    # @app_commands.check(permissions.is_owner)
    # @permissions.requires_perms(embed_links=True)
    # @cooldown(default=3)
    # async def editor(self, interaction: discord.Interaction, item: str):
    #     """Edit an existing item or create a new one."""
    #     async def get_item_emoji(item_name: str) -> str:
    #         async with get_db_connection() as conn:
    #             emoji = await conn.fetchval("SELECT emoji FROM items WHERE item = $1", item_name)
    #             return emoji if emoji else "❓"

    #     class RewardsModal(Modal, title="Set Rewards"):
    #         def __init__(self, item_name: str, message: discord.Message, view: 'EditItemView'):
    #             super().__init__()
    #             self.item_name = item_name
    #             self.message = message
    #             self.view = view
    #             self.rewards_input = TextInput(
    #                 label="Rewards",
    #                 placeholder="e.g., 250-1000+2-5xbasic_crate,10%+salmon,5%",
    #                 default="",
    #                 required=False
    #             )
    #             self.add_item(self.rewards_input)

    #         async def on_submit(self, interaction: discord.Interaction):
    #             rewards_str = self.rewards_input.value.strip()
    #             rewards = {}
    #             parts = rewards_str.split("+")
                
    #             if parts[0]:
    #                 if "-" in parts[0]:
    #                     cash_min, cash_max = map(int, parts[0].split("-"))
    #                     rewards["cash"] = [cash_min, cash_max]
    #                 else:
    #                     cash_amount = int(parts[0])
    #                     rewards["cash"] = [cash_amount, cash_amount]
                
    #             rewards["items"] = []
    #             for part in parts[1:]:
    #                 if not part:
    #                     continue
                        
    #                 if "," in part:
    #                     item_data, chance = part.split(",")
    #                     chance = float(chance.replace("%", "")) / 100
    #                 else:
    #                     item_data, chance = part, 1.0

    #                 quantity_min = quantity_max = 1
    #                 if "x" in item_data:
    #                     quantity_str, item_name = item_data.split("x")
    #                     if "-" in quantity_str:
    #                         quantity_min, quantity_max = map(int, quantity_str.split("-"))
    #                     else:
    #                         quantity_min = quantity_max = int(quantity_str)
    #                 else:
    #                     item_name = item_data

    #                 rewards["items"].append({
    #                     "item": item_name,
    #                     "chance": chance,
    #                     "quantity_min": quantity_min,
    #                     "quantity_max": quantity_max
    #                 })

    #             async with get_db_connection() as conn:
    #                 await conn.execute(
    #                     "UPDATE items SET rewards = $1 WHERE item = $2",
    #                     json.dumps(rewards), self.item_name
    #                 )
    #                 item_data = await conn.fetchrow("SELECT emoji FROM items WHERE item = $1", self.item_name)

    #                 description = f"**{self.item_name.replace('_', ' ').title()}** {item_data['emoji']}"
    #                 if rewards:
    #                     description += "\n\n**Rewards:**"
    #                     if "cash" in rewards:
    #                         cash_min, cash_max = rewards["cash"]
    #                         if cash_min == cash_max:
    #                             description += f"\n{cash_min} 💵 (100% chance)"
    #                         else:
    #                             description += f"\n{cash_min}-{cash_max} 💵 (100% chance)"
    #                     if "items" in rewards:
    #                         for item_reward in rewards["items"]:
    #                             item_name = item_reward["item"]
    #                             chance = item_reward["chance"]
    #                             q_min = item_reward["quantity_min"]
    #                             q_max = item_reward["quantity_max"]
    #                             item_emoji = await get_item_emoji(item_name)
                                
    #                             if q_min == q_max:
    #                                 description += f"\n{q_min}x **{item_name.replace('_', ' ').title()}** {item_emoji} ({int(chance * 100)}% chance)"
    #                             else:
    #                                 description += f"\n{q_min}-{q_max}x **{item_name.replace('_', ' ').title()}** {item_emoji} ({int(chance * 100)}% chance)"

    #             embed = discord.Embed(description=description.strip(), color=0xa4ec7c)
    #             await self.message.edit(embed=embed, view=self.view)
    #             await interaction.response.send_message("Rewards updated successfully!", ephemeral=True)

    #     class EmojiModal(Modal, title="Set Emoji"):
    #         def __init__(self, item_name: str):
    #             super().__init__()
    #             self.item_name = item_name
    #             self.emoji_input = TextInput(
    #                 label="Emoji",
    #                 placeholder="Enter the new emoji (e.g., 📦)",
    #                 default="",
    #                 required=True
    #             )
    #             self.add_item(self.emoji_input)

    #         async def on_submit(self, interaction: discord.Interaction):
    #             new_emoji = self.emoji_input.value.strip()
    #             async with get_db_connection() as conn:
    #                 await conn.execute(
    #                     "UPDATE items SET emoji = $1 WHERE item = $2",
    #                     new_emoji, self.item_name
    #                 )

    #                 embed = discord.Embed(
    #                     description=f"**{self.item_name.replace('_', ' ').title()}** {new_emoji}",
    #                     color=0xa4ec7c
    #                 )
    #                 view = EditItemView(self.item_name, interaction.user.id, interaction.message)
                    
    #                 try:
    #                     await interaction.response.edit_message(embed=embed, view=view)
    #                 except:
    #                     try:
    #                         await interaction.message.edit(embed=embed, view=view)
    #                     except:
    #                         await interaction.response.send_message("Successfully updated the emoji, but couldn't update the message. Please run the command again to see the changes.", ephemeral=True)

    #     class EditItemView(View):
    #         def __init__(self, item_name: str, user_id: int, original_message: Optional[discord.Message] = None):
    #             super().__init__()
    #             self.item_name = item_name
    #             self.user_id = user_id
    #             self.original_message = original_message

    #         @discord.ui.button(label="Rewards", style=discord.ButtonStyle.blurple)
    #         async def rewards_button(self, interaction: discord.Interaction, button: Button):
    #             if interaction.user.id != self.user_id:
    #                 await interaction.response.send_message("You are not allowed to use this button.", ephemeral=True)
    #                 return
    #             modal = RewardsModal(self.item_name, self.original_message, self)
    #             await interaction.response.send_modal(modal)

    #         @discord.ui.button(label="Emoji", style=discord.ButtonStyle.blurple)
    #         async def emoji_button(self, interaction: discord.Interaction, button: Button):
    #             if interaction.user.id != self.user_id:
    #                 await interaction.response.send_message("You are not allowed to use this button.", ephemeral=True)
    #                 return
    #             modal = EmojiModal(self.item_name)
    #             await interaction.response.send_modal(modal)

    #         @discord.ui.button(label="Delete", style=discord.ButtonStyle.red)
    #         async def delete_button(self, interaction: discord.Interaction, button: Button):
    #             if interaction.user.id != self.user_id:
    #                 await interaction.response.send_message("You are not allowed to use this button.", ephemeral=True)
    #                 return
    #             embed_color = await get_embed_color(str(interaction.user.id))
    #             embed = discord.Embed(
    #                 description=f"<:question:1323072605489467402> {interaction.user.mention}: Are you sure you want to delete **{self.item_name}**?",
    #                 color=embed_color
    #             )
    #             view = ConfirmDeleteView(self.item_name, self.user_id, self.original_message)
    #             await interaction.response.send_message(embed=embed, view=view)

    #         @discord.ui.button(label="Usable", style=discord.ButtonStyle.green)
    #         async def usable_button(self, interaction: discord.Interaction, button: Button):
    #             if interaction.user.id != self.user_id:
    #                 await interaction.response.send_message("You are not allowed to use this button.", ephemeral=True)
    #                 return
    #             async with get_db_connection() as conn:
    #                 item_data = await conn.fetchrow("SELECT usable FROM items WHERE item = $1", self.item_name)
    #                 if not item_data:
    #                     await interaction.response.send_message("Item not found.", ephemeral=True)
    #                     return
    #                 new_usable = not item_data["usable"]
    #                 await conn.execute(
    #                     "UPDATE items SET usable = $1 WHERE item = $2",
    #                     new_usable, self.item_name
    #                 )
    #                 button.label = "Unusable" if new_usable else "Usable"
    #                 await interaction.response.edit_message(view=self)

    #     class ConfirmDeleteView(View):
    #         def __init__(self, item_name: str, user_id: int, original_message: discord.Message):
    #             super().__init__()
    #             self.item_name = item_name
    #             self.user_id = user_id
    #             self.original_message = original_message

    #         @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    #         async def approve_button(self, interaction: discord.Interaction, button: Button):
    #             if interaction.user.id != self.user_id:
    #                 await interaction.response.send_message("You are not allowed to use this button.", ephemeral=True)
    #                 return

    #             async with get_db_connection() as conn:
    #                 print(f'deleting {item_name}')
    #                 await conn.execute("DELETE FROM items WHERE item = $1", self.item_name)

    #                 await interaction.response.defer()
    #                 await interaction.delete_original_response()

    #         @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    #         async def decline_button(self, interaction: discord.Interaction, button: Button):
    #             if interaction.user.id != self.user_id:
    #                 await interaction.response.send_message("You are not allowed to use this button.", ephemeral=True)
    #                 return
    #             await interaction.response.defer()
    #             await interaction.delete_original_response()

    #     class ConfirmCreateView(View):
    #         def __init__(self, item_name: str, user_id: int):
    #             super().__init__()
    #             self.item_name = item_name
    #             self.user_id = user_id

    #         @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    #         async def approve_button(self, interaction: discord.Interaction, button: Button):
    #             if interaction.user.id != self.user_id:
    #                 await interaction.response.send_message("You are not allowed to use this button.", ephemeral=True)
    #                 return
    #             async with get_db_connection() as conn:
    #                 await conn.execute(
    #                     "INSERT INTO items (item, emoji) VALUES ($1, $2)",
    #                     self.item_name, "❓"
    #                 )
    #                 embed = discord.Embed(
    #                     description=f"**{self.item_name.replace('_', ' ').title()}** ❓",
    #                     color=0xa4ec7c
    #                 )
    #                 view = EditItemView(self.item_name, self.user_id, interaction.message)
    #                 await interaction.response.edit_message(embed=embed, view=view)

    #         @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    #         async def decline_button(self, interaction: discord.Interaction, button: Button):
    #             if interaction.user.id != self.user_id:
    #                 await interaction.response.send_message("You are not allowed to use this button.", ephemeral=True)
    #                 return
    #             await interaction.response.defer()
    #             await interaction.delete_original_response()

    #     async with get_db_connection() as conn:
    #         item_data = await conn.fetchrow("SELECT item, emoji, usable, rewards FROM items WHERE item = $1", item)

    #     if item_data:
    #         item_name = item_data["item"]
    #         emoji = item_data["emoji"] if item_data["emoji"] else "❓"
    #         rewards = json.loads(item_data["rewards"]) if item_data["rewards"] else {}
    #         description = f"**{item_name.replace('_', ' ').title()}** {emoji}"
    #         if rewards:
    #             description += "\n\n**Rewards:**"
    #             if "cash" in rewards:
    #                 cash_min, cash_max = rewards["cash"]
    #                 if cash_min == cash_max:
    #                     description += f"\n{cash_min} 💵 (100% chance)"
    #                 else:
    #                     description += f"\n{cash_min}-{cash_max} 💵 (100% chance)"
    #             if "items" in rewards:
    #                 for item_reward in rewards["items"]:
    #                     item_name = item_reward["item"]
    #                     chance = item_reward["chance"]
    #                     q_min = item_reward.get("quantity_min", 1)
    #                     q_max = item_reward.get("quantity_max", 1)
    #                     item_emoji = await get_item_emoji(item_name)
                        
    #                     if q_min == q_max:
    #                         description += f"\n{q_min}x **{item_name.replace('_', ' ').title()}** {item_emoji} ({int(chance * 100)}% chance)"
    #                     else:
    #                         description += f"\n{q_min}-{q_max}x **{item_name.replace('_', ' ').title()}** {item_emoji} ({int(chance * 100)}% chance)"

    #         embed = discord.Embed(
    #             description=description,
    #             color=0xa4ec7c
    #         )
    #         view = EditItemView(item_name, interaction.user.id, None)
    #         original_message = await interaction.followup.send(embed=embed, view=view)
    #         view.original_message = original_message
    #     else:
    #         embed_color = await get_embed_color(str(interaction.user.id))
    #         embed = discord.Embed(
    #             description=f"<:question:1323072605489467402> {interaction.user.mention}: There is no item called **{item}**, do you want to create it?",
    #             color=embed_color
    #         )
    #         view = ConfirmCreateView(item, interaction.user.id)
    #         await interaction.followup.send(embed=embed, view=view)

    # @editor.autocomplete("item")
    # async def editor_item_autocomplete(self, interaction: discord.Interaction, current: str):
    #     async with get_db_connection() as conn:
    #         items = await conn.fetch("SELECT item FROM items WHERE item ILIKE $1", f"%{current}%")
    #         return [app_commands.Choice(name=item["item"].replace("_", " ").title(), value=item["item"]) for item in items]

    # @item.command()
    # @app_commands.allowed_installs(guilds=False, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    # @app_commands.check(permissions.is_owner)
    # @permissions.requires_perms(embed_links=True)
    # @cooldown(default=3)
    # async def give(self, interaction: discord.Interaction, item: str, amount: int = 1, user: discord.User = None):
    #     "Give an item to a user."
    #     receiver = user or interaction.user
    #     receiver_id = str(receiver.id)

    #     try:
    #         async with get_db_connection() as conn:
    #             await conn.execute(
    #                 "INSERT INTO inventory (user_id, item, quantity) VALUES ($1, $2, $3) "
    #                 "ON CONFLICT (user_id, item) DO UPDATE SET quantity = inventory.quantity + $3",
    #                 receiver_id, item, amount
    #             )

    #             await interaction.followup.send(f"<:vericheck:1301647869505179678> {interaction.user.mention}: Gave **{amount}x {item.replace('_', ' ').title()}** to {receiver.mention}!")

    #     except Exception as e:
    #         await error_handler(interaction, e)

    # @give.autocomplete("item")
    # async def give_item_autocomplete(self, interaction: discord.Interaction, current: str):
    #     async with get_db_connection() as conn:
    #         items = await conn.fetch("SELECT item FROM items WHERE item ILIKE $1", f"%{current}%")
    #         return [app_commands.Choice(name=item["item"].replace("_", " ").title(), value=item["item"]) for item in items]

async def setup(client):
    await client.add_cog(Owner(client))