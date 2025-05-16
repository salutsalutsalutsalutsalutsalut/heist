import discord
from discord import app_commands, Interaction, User, Embed
from discord.ext import commands
import requests
from utils import permissions
from utils.error import error_handler
from utils.cache import get_embed_color
from datetime import datetime
import os, asyncio, json, time, psutil

class Info(commands.Cog):
    def __init__(self, client):
        self.client = client

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def plus(self, interaction: Interaction):
        "Get information about Heist+"

        process = psutil.Process(os.getpid())
        ram_usage = process.memory_info().rss / 1024 ** 2 
        ping = interaction.client.latency * 1000

        embed_color = await get_embed_color(str(interaction.user.id))
        embed = discord.Embed(
            title="RAM Usage",
            description=f"The bot is currently using **{ram_usage:.2f} MB** of RAM\n-# & {ping:.2f}ms",
            color=embed_color
        )
        await interaction.followup.send(embed=embed)

async def setup(client):
    await client.add_cog(Info(client))
