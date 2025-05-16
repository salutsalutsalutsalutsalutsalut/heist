from discord import app_commands, Interaction, User, Embed
from discord.ext import commands, tasks
import re, random, json, datetime, asyncio
from utils.db import check_blacklisted, check_booster, check_donor, check_owner, get_db_connection
from utils.error import error_handler
from utils import default, permissions
from dotenv import dotenv_values
import asyncpg, asyncio, string, redis, psutil, os, gc, sys
from typing import Dict
import objgraph

class Manage(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

    @commands.command()
    @commands.check(permissions.is_blacklisted)
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx, new_prefix: str = None):
        if not new_prefix:
            return await ctx.send(f"<:warning:1350239604925530192> {ctx.author.mention}: You must provide a new prefix.")
        if len(new_prefix) > 3:
            return await ctx.send(f"<:warning:1350239604925530192> {ctx.author.mention}: The new prefix must be 3 characters or less.")
        self.redis_client.set(f"prefix:{ctx.guild.id}", new_prefix)
        await ctx.send(f"<a:vericheckg:1301736918794371094> {ctx.author.mention}: Prefix set to `{new_prefix}`.")

    @commands.command()
    @commands.check(permissions.is_blacklisted)
    @commands.has_permissions(manage_messages=True)
    @permissions.bot_requires(manage_messages=True)
    async def purge(self, ctx, amount: int = None, mode: str = None):
        try:
            await ctx.message.delete(delay=3)
        except:
            pass
        if amount is None:
            await ctx.send(
                f"<:warning:1350239604925530192> {ctx.author.mention}:\nUsage\n[] = required, () = optional:\n`purge [amount] (invites/links)`",
                delete_after=10
            )
            return

        if amount < 1 or amount > 100:
            return await ctx.send(f"<:warning:1350239604925530192> {ctx.author.mention}: Amount must be between 1 and 100.")

        valid_modes = ["invites", "links"]

        if mode and mode.lower() not in valid_modes:
            await ctx.send(
                f"<:warning:1350239604925530192> {ctx.author.mention}:\nUsage\n[] = required, () = optional:\n`purge [amount] (invites/links)`",
                delete_after=10
            )
            return

        if mode and mode.lower() == "invites":
            def is_invite(m):
                return "discord.gg/" in m.content or "discord.com/invite/" in m.content or "discordapp.com/invite/" in m.content
            deleted = await ctx.channel.purge(limit=amount, check=is_invite)
            if len(deleted) == 0:
                return await ctx.send(f"<:denied:1301737566264889364> {ctx.author.mention}: Could not find any messages containing Discord invites.", delete_after=5)
            return await ctx.send(f"<a:vericheckg:1301736918794371094> {ctx.author.mention}: Deleted {len(deleted)} messages containing Discord invites.", delete_after=5)
        elif mode and mode.lower() == "links":
            def is_link(m):
                return "http" in m.content or "www" in m.content
            deleted = await ctx.channel.purge(limit=amount, check=is_link)
            if len(deleted) == 0:
                return await ctx.send(f"<:denied:1301737566264889364> {ctx.author.mention}: Could not find any messages containing links.", delete_after=5)
            return await ctx.send(f"<a:vericheckg:1301736918794371094> {ctx.author.mention}: Deleted {len(deleted)} messages containing links.", delete_after=5)
        else:
            deleted = await ctx.channel.purge(limit=amount)
            if len(deleted) == 0:
                return await ctx.send(f"<:denied:1301737566264889364> {ctx.author.mention}: Could not find any messages to delete.", delete_after=5)
            return await ctx.send(f"<a:vericheckg:1301736918794371094> {ctx.author.mention}: Deleted {len(deleted)} messages.", delete_after=5)

def get_command_info(command, group=None):
    info = {
        "name": command.name,
        "description": command.description,
        "usage": f"/{command.name} {' '.join([f'<{param.name}>' for param in command.parameters])}",
        "example": f"/{command.name} {' '.join([f'<{param.name}>' for param in command.parameters])}",
        "category": group.name if group else "Default",
        "premium": any(isinstance(check, app_commands.check) and check.__name__ == "is_donor" for check in command.checks)
    }
    return info

def dump_commands(bot):
    commands_list = []
    for command in bot.tree.walk_commands():
        if isinstance(command, app_commands.Group):
            for subcommand in command.walk_commands():
                commands_list.append(get_command_info(subcommand, group=command))
        else:
            commands_list.append(get_command_info(command))
    return json.dumps(commands_list, indent=4)

async def setup(client):
    await client.add_cog(Manage(client))