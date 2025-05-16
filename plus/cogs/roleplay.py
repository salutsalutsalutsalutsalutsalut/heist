import discord
import aiohttp
from discord import app_commands, Interaction, User, Embed
from discord.ext import commands
from utils import permissions
from utils.error import error_handler
from utils.cache import get_embed_color
from utils.db import get_db_connection, redis_client
import os

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

    roleplay = app_commands.Group(
        name="roleplay", 
        description="Roleplay related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    nsfwroleplay = app_commands.Group(
        name="nsfw", 
        description="NSFW roleplay related commands",
        parent=roleplay
    )

    async def _fetch_gif(self, url):
        """Helper method to fetch GIF from an API"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('url') or data.get('link')
                return None

    @nsfwroleplay.command(nsfw=True)
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to creampie.")
    async def creampie(self, interaction: Interaction, user: User = None):
        """Creampie someone."""
        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "creampie")

        gif_url = await self._fetch_gif("https://hmtai.hatsunia.cfd/v2/creampie")
        if not gif_url:
            return await interaction.followup.send("Failed to fetch creampie GIF.")

        embed_color = await get_embed_color(str(interaction.user.id))
        embed = Embed(
            description=f"**{interaction.user.mention}** **creampies** **{user.mention}** for the **{ordinal_count}** time!",
            color=embed_color
        )
        embed.set_image(url=gif_url)

        await interaction.followup.send(embed=embed)

    @nsfwroleplay.command(nsfw=True)
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to give a blowjob to.")
    async def blowjob(self, interaction: Interaction, user: User = None):
        """Suck someone's cock."""
        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "blowjob")

        gif_url = await self._fetch_gif("https://purrbot.site/api/img/nsfw/blowjob/gif")
        if not gif_url:
            return await interaction.followup.send("Failed to fetch blowjob GIF.")

        embed_color = await get_embed_color(str(interaction.user.id))
        embed = Embed(
            description=f"**{interaction.user.mention}** **sucks** **{user.mention}**'s dick for the **{ordinal_count}** time!",
            color=embed_color
        )
        embed.set_image(url=gif_url)

        await interaction.followup.send(embed=embed)

    @nsfwroleplay.command(nsfw=True)
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to eat the pussy of.")
    async def eatpussy(self, interaction: Interaction, user: User = None):
        """Eat someone's pussy."""
        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "pussyeat")

        gif_url = await self._fetch_gif("https://purrbot.site/api/img/nsfw/pussylick/gif")
        if not gif_url:
            return await interaction.followup.send("Failed to fetch pussylick GIF.")

        embed_color = await get_embed_color(str(interaction.user.id))
        embed = Embed(
            description=f"**{interaction.user.mention}** **eats** **{user.mention}**'s pussy for the **{ordinal_count}** time!",
            color=embed_color
        )
        embed.set_image(url=gif_url)

        await interaction.followup.send(embed=embed)

    @nsfwroleplay.command(nsfw=True)
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to have fun with.")
    async def yaoi(self, interaction: Interaction, user: User = None):
        """Have some yaoi fun with someone."""
        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "yaoi")

        gif_url = await self._fetch_gif("https://purrbot.site/api/img/nsfw/yaoi/gif")
        if not gif_url:
            return await interaction.followup.send("Failed to fetch yaoi GIF.")

        embed_color = await get_embed_color(str(interaction.user.id))
        embed = Embed(
            description=f"**{interaction.user.mention}** **has yaoi fun with** **{user.mention}** for the **{ordinal_count}** time!",
            color=embed_color
        )
        embed.set_image(url=gif_url)

        await interaction.followup.send(embed=embed)

    @nsfwroleplay.command(nsfw=True)
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to have fun with.")
    async def yuri(self, interaction: Interaction, user: User = None):
        """Have some yuri fun with someone."""
        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "yuri")

        gif_url = await self._fetch_gif("https://purrbot.site/api/img/nsfw/yuri/gif")
        if not gif_url:
            return await interaction.followup.send("Failed to fetch yuri GIF.")

        embed_color = await get_embed_color(str(interaction.user.id))
        embed = Embed(
            description=f"**{interaction.user.mention}** **has yuri fun with** **{user.mention}** for the **{ordinal_count}** time!",
            color=embed_color
        )
        embed.set_image(url=gif_url)

        await interaction.followup.send(embed=embed)

    @nsfwroleplay.command(nsfw=True)
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to fuck.")
    async def fuck(self, interaction: Interaction, user: User = None):
        """Fuck someone."""
        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "fuck")

        gif_url = await self._fetch_gif("https://purrbot.site/api/img/nsfw/fuck/gif")
        if not gif_url:
            return await interaction.followup.send("Failed to fetch fuck GIF.")

        embed_color = await get_embed_color(str(interaction.user.id))
        embed = Embed(
            description=f"**{interaction.user.mention}** **fucks** **{user.mention}** for the **{ordinal_count}** time!",
            color=embed_color
        )
        embed.set_image(url=gif_url)

        await interaction.followup.send(embed=embed)

    @nsfwroleplay.command(nsfw=True)
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @app_commands.describe(user="The user to fuck in the ass.")
    async def anal(self, interaction: Interaction, user: User = None):
        """Fuck someone in the ass."""
        user = user or interaction.user

        ordinal_count = await update_count(interaction.user.id, user.id, "anal")

        gif_url = await self._fetch_gif("https://purrbot.site/api/img/nsfw/anal/gif")
        if not gif_url:
            return await interaction.followup.send("Failed to fetch anal GIF.")

        embed_color = await get_embed_color(str(interaction.user.id))
        embed = Embed(
            description=f"**{interaction.user.mention}** **fucks** **{user.mention}** **in the ass** for the **{ordinal_count}** time!",
            color=embed_color
        )
        embed.set_image(url=gif_url)

        await interaction.followup.send(embed=embed)

    @nsfwroleplay.command(nsfw=True)
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.choices(gender=[
        app_commands.Choice(name="Female", value="female"),
        app_commands.Choice(name="Male", value="male")
    ])
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def masturbate(self, interaction: Interaction, gender: str = "female"):
        """Please yourself a little."""
        ordinal_count = await update_count(interaction.user.id, interaction.user.id, "masturbate")
        
        endpoint = "https://purrbot.site/api/img/nsfw/solo/gif" if gender == "female" else "https://purrbot.site/api/img/nsfw/solo_male/gif"
        gif_url = await self._fetch_gif(endpoint)
        if not gif_url:
            return await interaction.followup.send("Failed to fetch masturbate GIF.")
        
        embed_color = await get_embed_color(str(interaction.user.id))
        embed = Embed(
            description=f"**{interaction.user.mention}** **masturbates** for the **{ordinal_count}** time!",
            color=embed_color
        )
        embed.set_image(url=gif_url)
        
        await interaction.followup.send(embed=embed)

async def setup(client):
    await client.add_cog(Roleplay(client))