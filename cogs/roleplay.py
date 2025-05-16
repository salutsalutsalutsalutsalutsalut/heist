import discord
from discord import app_commands, Interaction, User, Embed
from discord.ext import commands
import aiohttp
import random
from utils import permissions
from utils.error import error_handler
from utils.embed import cembed
from utils.db import get_db_connection, redis_client

redis = redis_client

async def update_count(interaction_user_id: int, target_user_id: int, action: str) -> str:
    cache_key = f"{interaction_user_id}_{target_user_id}_{action}"
    cached_count = await redis.get(cache_key)
    
    async with get_db_connection() as conn:
        if cached_count:
            count = int(cached_count) + 1
            query = """
                UPDATE user_actions 
                SET count = $1 
                WHERE user_id = $2 AND target_user_id = $3 AND action = $4
                RETURNING count
            """
            result = await conn.fetchrow(query, count, interaction_user_id, target_user_id, action)
        else:
            query = """
                INSERT INTO user_actions (user_id, target_user_id, action, count)
                VALUES ($1, $2, $3, 1)
                ON CONFLICT (user_id, target_user_id, action)
                DO UPDATE SET count = user_actions.count + 1
                RETURNING count
            """
            result = await conn.fetchrow(query, interaction_user_id, target_user_id, action)
            count = result['count']

    await redis.setex(cache_key, 3600, count)

    if 10 <= count % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(count % 10, 'th')
    return f"{count}{suffix}"

class Roleplay(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    roleplay = app_commands.Group(
        name="roleplay", 
        description="Roleplay related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to slap.")
    async def slap(self, interaction: Interaction, user: User = None):
        """Slap someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "slap")

        async with self.session.get("https://nekos.best/api/v2/slap") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch slap GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **slaps** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to hug.")
    async def hug(self, interaction: Interaction, user: User = None):
        """Hug someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "hug")

        async with self.session.get("https://nekos.best/api/v2/hug") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch hug GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **hugs** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to kiss.")
    async def kiss(self, interaction: Interaction, user: User = None):
        """Kiss someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "kiss")

        async with self.session.get("https://nekos.best/api/v2/kiss") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch kiss GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **kisses** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to bite.")
    async def bite(self, interaction: Interaction, user: User = None):
        """Bite someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "bite")

        async with self.session.get("https://nekos.best/api/v2/bite") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch bite GIF.")

        embed = await cembed(interaction,
            description=f"*Ouch!* **{interaction.user.mention}** **bites** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to call baka.")
    async def baka(self, interaction: Interaction, user: User = None):
        """Call someone baka."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "baka")

        async with self.session.get("https://nekos.best/api/v2/baka") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch baka GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **calls** **{user.mention}** baka for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to cuddle.")
    async def cuddle(self, interaction: Interaction, user: User = None):
        """Cuddle someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "cuddle")

        async with self.session.get("https://nekos.best/api/v2/cuddle") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch cuddle GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **cuddles** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to feed.")
    async def feed(self, interaction: Interaction, user: User = None):
        """Feed someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "feed")

        async with self.session.get("https://nekos.best/api/v2/feed") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch feed GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **feeds** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to hold hands with.")
    async def handhold(self, interaction: Interaction, user: User = None):
        """Hold hands with someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "handhold")

        async with self.session.get("https://nekos.best/api/v2/handhold") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch handhold GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **holds hands with** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to shake hands with.")
    async def handshake(self, interaction: Interaction, user: User = None):
        """Shake hands with someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "handshake")

        async with self.session.get("https://nekos.best/api/v2/handshake") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch handshake GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **shakes hands with** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to high five.")
    async def highfive(self, interaction: Interaction, user: User = None):
        """High five someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "highfive")

        async with self.session.get("https://nekos.best/api/v2/highfive") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch highfive GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **high fives** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to kick.")
    async def kick(self, interaction: Interaction, user: User = None):
        """Kick someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "kick")

        async with self.session.get("https://nekos.best/api/v2/kick") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch kick GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **kicks** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to pat.")
    async def pat(self, interaction: Interaction, user: User = None):
        """Pat someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "pat")

        async with self.session.get("https://nekos.best/api/v2/pat") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch pat GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **pats** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to punch.")
    async def punch(self, interaction: Interaction, user: User = None):
        """Punch someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "punch")

        async with self.session.get("https://nekos.best/api/v2/punch") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch punch GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **punches** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to peck.")
    async def peck(self, interaction: Interaction, user: User = None):
        """Peck someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "peck")

        async with self.session.get("https://nekos.best/api/v2/peck") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch peck GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **pecks** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to poke.")
    async def poke(self, interaction: Interaction, user: User = None):
        """Poke someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "poke")

        async with self.session.get("https://nekos.best/api/v2/poke") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch poke GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **pokes** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to shoot.")
    async def shoot(self, interaction: Interaction, user: User = None):
        """Shoot someone."""

        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "shoot")

        async with self.session.get("https://nekos.best/api/v2/shoot") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch shoot GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **shoots** **{user.mention}** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

    @roleplay.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def cry(self, interaction: Interaction):
        """Let it all out."""

        ordinal_count = await update_count(interaction.user.id, interaction.user.id, "cry")

        async with self.session.get("https://nekos.best/api/v2/cry") as response:
            if response.status == 200:
                data = await response.json()
                gif_url = data['results'][0]['url']
                anime_name = data['results'][0]['anime_name']
            else:
                return await interaction.followup.send("Failed to fetch cry GIF.")

        embed = await cembed(interaction,
            description=f"**{interaction.user.mention}** **cries** for the **{ordinal_count}** time!"
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"From: {anime_name}")

        await interaction.followup.send(embed=embed)

async def setup(client):
    await client.add_cog(Roleplay(client))