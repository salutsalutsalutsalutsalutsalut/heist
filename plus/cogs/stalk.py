import discord
from discord import app_commands, Interaction, User, Embed
from discord.ext import commands
import requests
from utils import permissions
from utils.error import error_handler
from utils.cache import get_embed_color
from utils.db import get_db_connection, redis_client
from datetime import datetime
import os, asyncio, json, time
import redis.asyncio as redis

class Stalk(commands.Cog):
    def __init__(self, client):
        self.client = client

        # Separate Redis pool for the Stalk cog
        self.stalk_redis_pool = redis.ConnectionPool(
            host='localhost',
            port=6379,
            db=1,
            decode_responses=True,
            max_connections=50
        )
        self.stalk_redis = redis.Redis(connection_pool=self.stalk_redis_pool)

        self.pubsub = self.stalk_redis.pubsub()
        asyncio.create_task(self.initialize_pubsub())

    discordg = app_commands.Group(
        name="discord", 
        description="Discord related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    userg = app_commands.Group(
        name="user",
        description="User related Discord commands",
        parent=discordg 
    )

    followg = app_commands.Group(
        name="follow",
        description="Follow related Discord commands",
        parent=discordg 
    )

    async def initialize_pubsub(self):
        await self.pubsub.subscribe('user_activity')
        asyncio.create_task(self.handle_pubsub_messages())

    async def handle_pubsub_messages(self):
        while True:
            message = await self.pubsub.get_message()
            if message and message['type'] == 'message':
                data = json.loads(message['data'])
                await self.process_activity(data)

    async def process_activity(self, data):
        activity_type = data['type']
        user_id = data['user_id']

        stalkers = await self.stalk_redis.smembers(f"stalker:{user_id}:stalkers")
        if not stalkers:
            return

        user = await self.client.fetch_user(int(user_id))
        username = user.name if user else "Unknown User"
        user_pfp = str(user.display_avatar.url) if user and user.display_avatar else None

        channel_name = data.get('channel_name', 'unknown channel')
        channel_id = data.get('channel_id', '123')
        guild_name = data.get('guild_name', 'unknown server')

        tasks = []

        for stalker_id in stalkers:
            try:
                activity_key = f"activity:{user_id}:{guild_name}:{channel_name}:{activity_type}"

                last_activity = await self.stalk_redis.get(activity_key)

                if activity_type == 'message':
                    if not last_activity or (time.time() - float(last_activity)) > 600:
                        description = f"**{username}** sent a message in **#{channel_name}** (<#{channel_id}>) in **{guild_name}**"
                        title = f"{username} - message"
                        tasks.append(self.send_stalker_dm(stalker_id, title, description, user_pfp))
                        await self.stalk_redis.set(activity_key, time.time())

                elif activity_type == 'voice_join':
                    description = f"**{username}** joined the voice channel **#{channel_name}** (<#{channel_id}>) in **{guild_name}**"
                    title = f"{username} - joined vc"
                    tasks.append(self.send_stalker_dm(stalker_id, title, description, user_pfp))

                elif activity_type == 'voice_leave':
                    description = f"**{username}** left the voice channel in **{guild_name}**"
                    title = f"{username} - left vc"
                    tasks.append(self.send_stalker_dm(stalker_id, title, description, user_pfp))

                elif activity_type == 'voice_switch':
                    previous_channel = data.get('previous_channel', 'unknown channel')
                    description = f"**{username}** switched from **#{previous_channel}** to **#{channel_name}** (<#{channel_id}>) in **{guild_name}**"
                    title = f"{username} - switched vc"
                    tasks.append(self.send_stalker_dm(stalker_id, title, description, user_pfp))

                if activity_type in ['voice_join', 'voice_leave', 'voice_switch']:
                    await self.stalk_redis.set(activity_key, time.time())

            except discord.Forbidden:
                print(f"Can't send DM to stalker {stalker_id}.")
            except Exception as e:
                print(f"Error processing activity: {e}")

        if tasks:
            await asyncio.gather(*tasks)

    async def send_stalker_dm(self, stalker_id, title, description, user_pfp):
        try:
            stalker = await self.client.fetch_user(int(stalker_id))
            if stalker:
                embed_color = await get_embed_color(str(stalker_id))
                embed = discord.Embed(
                    title=title,
                    description=description,
                    color=embed_color
                )
                if user_pfp:
                    embed.set_thumbnail(url=user_pfp)
                await stalker.send(embed=embed)
        except Exception as e:
            print(f"Error sending DM to stalker {stalker_id}: {e}")

    async def remove_stalker(self, stalker_id):
        targets = await self.stalk_redis.smembers(f"stalker:{stalker_id}:targets")
        for target_id in targets:
            await self.stalk_redis.srem(f"stalker:{target_id}:stalkers", stalker_id)
        await self.stalk_redis.delete(f"stalker:{stalker_id}:targets")

        async with get_db_connection() as conn:
            await conn.execute("DELETE FROM stalking WHERE stalker_id = $1", stalker_id)

    @userg.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.describe(user="The user to add to your follow list.")
    @app_commands.check(permissions.is_blacklisted)
    async def follow(self, interaction: Interaction, user: discord.User):
        """Follow a Discord user."""

        async with get_db_connection() as conn:
            hid_row = await conn.fetchrow(
                "SELECT hid FROM user_data WHERE user_id = $1", str(interaction.user.id)
            )

        if not hid_row:
            await interaction.response.send_message("User data not found.", ephemeral=True)
            return

        hid = hid_row['hid']

        if await redis_client.exists(f"user:{hid}:untrusted"):
            await interaction.response.send_message("You are not eligible to use this command.", ephemeral=True)
            return

        stalker_id = str(interaction.user.id)
        target_id = str(user.id)

        if stalker_id == target_id:
            await interaction.response.send_message("You can't stalk yourself!", ephemeral=True)
            return

        following_count = await self.stalk_redis.scard(f"stalker:{stalker_id}:targets")
        if following_count >= 5:
            await interaction.response.send_message("You can only follow a maximum of 5 users.", ephemeral=True)
            return

        try:
            stalker = await self.client.fetch_user(str(stalker_id))
            try:
                await stalker.send(f"You're now following {user.display_name} (@{user.name}) - {user.id}")
            except discord.Forbidden:
                await interaction.response.send_message("Could not DM you, action cancelled.", ephemeral=True)
                return

            async with get_db_connection() as conn:
                await conn.execute(
                    "INSERT INTO stalking (stalker_id, target_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    stalker_id, target_id
                )
            await self.stalk_redis.sadd(f"stalker:{stalker_id}:targets", target_id)
            await self.stalk_redis.sadd(f"stalker:{target_id}:stalkers", stalker_id)
            await interaction.response.send_message(f"Now following {user.name}!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to follow {user.name}: {e}", ephemeral=True)

    async def user_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        stalker_id = str(interaction.user.id)
        targets = await self.stalk_redis.smembers(f"stalker:{stalker_id}:targets")
        
        choices = []
        for target_id in targets:
            try:
                user = await self.client.fetch_user(int(target_id))
                if current.lower() in user.name.lower():
                    choices.append(app_commands.Choice(name=user.name, value=str(user.id)))
            except discord.NotFound:
                continue
        
        return choices[:25]

    @userg.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.describe(user="The user to remove from your follow list.")
    @app_commands.autocomplete(user=user_autocomplete)
    @app_commands.check(permissions.is_blacklisted)
    async def unfollow(self, interaction: Interaction, user: str):
        """Unfollow a Discord user."""
        stalker_id = str(interaction.user.id)
        target_id = user

        try:
            target_user = await self.client.fetch_user(int(target_id))
            stalker = await self.client.fetch_user(int(stalker_id))
            
            try:
                await stalker.send(f"You're no longer following {target_user.display_name} (@{target_user.name}) - {target_user.id}")
            except discord.Forbidden:
                await interaction.response.send_message("Could not DM you, action cancelled.", ephemeral=True)
                return

            async with get_db_connection() as conn:
                await conn.execute(
                    "DELETE FROM stalking WHERE stalker_id = $1 AND target_id = $2",
                    stalker_id, target_id
                )

            await self.stalk_redis.srem(f"stalker:{stalker_id}:targets", target_id)
            await self.stalk_redis.srem(f"stalker:{target_id}:stalkers", stalker_id)

            await self.stalk_redis.delete(f"activity:{stalker_id}:{target_id}")

            await self.stalk_redis.delete(f"notifications:{stalker_id}:{target_id}")

            await interaction.response.send_message(f"No longer following {target_user.name}!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to unfollow {target_id}: {e}", ephemeral=True)

    @followg.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def list(self, interaction: Interaction):
        """List the users you're following."""

        stalker_id = str(interaction.user.id)

        targets = await self.stalk_redis.smembers(f"stalker:{stalker_id}:targets")
        if not targets:
            await interaction.response.send_message("You're not following anyone.", ephemeral=True)
            return

        targets = list(targets)[:5]

        user_info = []
        for target_id in targets:
            try:
                user = await self.client.fetch_user(int(target_id))
                user_info.append(f"{user.name} ({user.id})")
            except discord.NotFound:
                continue

        if not user_info:
            await interaction.response.send_message("You are not following any active users.", ephemeral=True)
        else:
            await interaction.response.send_message("\n".join(user_info), ephemeral=True)

    async def cog_unload(self):
        await self.stalk_redis_pool.disconnect()

async def setup(client):
    await client.add_cog(Stalk(client))