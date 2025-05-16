import asyncio
import discord
from discord.ext import commands
from discord.ext.commands import CheckFailure
from utils.db import get_db_connection, redis_client
import redis
import functools, logging

footer = "heist.lol"

async def is_owner(cti):
    user = cti.user if isinstance(cti, discord.Interaction) else cti.author
    user_id = str(user.id)

    cached_result = await redis_client.get(f"owner:{user_id}")
    if cached_result is not None:
        if cached_result == "False":
            await _send_response(cti, f"<:warning:1350239604925530192> {user.mention}: You are not Heist staff.")
            return False
        return True

    async with get_db_connection() as conn:
        is_owner = bool(await conn.fetchval('SELECT user_id FROM owners WHERE user_id = $1', user_id))
        await redis_client.setex(f"owner:{user_id}", 300, str(is_owner))

        if not is_owner:
            await _send_response(cti, f"<:warning:1350239604925530192> {user.mention}: You are not Heist staff.")
        return is_owner

async def _send_response(cti, message):
    if isinstance(cti, discord.Interaction):
        if cti.response.is_done():
            await cti.followup.send(message, ephemeral=True)
        else:
            await cti.response.send_message(message, ephemeral=True)
    else:
        pass

async def is_blacklisted(ctx):
    if isinstance(ctx, discord.Interaction):
        user_id = str(ctx.user.id)
        cached_result = await redis_client.get(f"blacklist:{user_id}")
        
        if cached_result is not None:
            is_blacklisted = cached_result == "True"
            if is_blacklisted:
                reason = await redis_client.get(f"blacklist_reason:{user_id}")
                await ctx.response.send_message(
                    f"You are blacklisted from using [Heist](<https://{footer}>) for **\"{reason}\"**.\n-# Wrongfully blacklisted? You may appeal [**here**](<https://discord.gg/6ScZFN3wPA>).", 
                    ephemeral=True
                )
            return not is_blacklisted

        async with get_db_connection() as conn:
            result = await conn.fetchrow('SELECT user_id, reason FROM blacklisted WHERE user_id = $1', user_id)
            is_blacklisted = bool(result)
            await redis_client.setex(f"blacklist:{user_id}", 300, str(is_blacklisted))
            if is_blacklisted:
                await redis_client.setex(f"blacklist_reason:{user_id}", 300, result['reason'])
                await ctx.response.send_message(
                    f"You are blacklisted from using [Heist](<https://{footer}>) for **\"{result['reason']}\"**.\n-# Wrongfully blacklisted? You may appeal [**here**](<https://discord.gg/6ScZFN3wPA>).", 
                    ephemeral=True
                )
            return not is_blacklisted
    
    elif isinstance(ctx, commands.Context):
        user_id = str(ctx.author.id)
        cached_result = await redis_client.get(f"blacklist:{user_id}")
        
        if cached_result is not None:
            is_blacklisted = cached_result == "True"
            if is_blacklisted:
                reason = await redis_client.get(f"blacklist_reason:{user_id}")
                await ctx.send(
                    f"You are blacklisted from using [Heist](<https://{footer}>) for **\"{reason}\"**.\n-# Wrongfully blacklisted? You may appeal [**here**](<https://discord.gg/6ScZFN3wPA>)."
                )
            return not is_blacklisted

        async with get_db_connection() as conn:
            result = await conn.fetchrow('SELECT user_id, reason FROM blacklisted WHERE user_id = $1', user_id)
            is_blacklisted = bool(result)
            await redis_client.setex(f"blacklist:{user_id}", 300, str(is_blacklisted))
            if is_blacklisted:
                await redis_client.setex(f"blacklist_reason:{user_id}", 300, result['reason'])
                await ctx.send(
                    f"You are blacklisted from using [Heist](<https://{footer}>) for **\"{result['reason']}\"**.\n-# Wrongfully blacklisted? You may appeal [**here**](<https://discord.gg/6ScZFN3wPA>)."
                )
            return not is_blacklisted
    
    else:
        raise ValueError("Invalid context type. Expected Interaction or commands.Context.")

async def is_donor(interaction):
    user_id = str(interaction.user.id)
    cached_result = await redis_client.get(f"donor:{user_id}")
    if cached_result is not None:
        is_donor = cached_result == "True"
        if not is_donor:
            await interaction.response.send_message("<:premium:1311062205650833509> This is a premium-only command. Run </premium buy:1278389799857946700> to learn more.", ephemeral=True)
        return is_donor

    async with get_db_connection() as conn:
        result = await conn.fetchval('SELECT user_id FROM donors WHERE user_id = $1', user_id)
        is_donor = bool(result)
        await redis_client.setex(f"donor:{user_id}", 300, str(is_donor))

        if not is_donor:
            await interaction.response.send_message("<:premium:1311062205650833509> This is a premium-only command. Run </premium perks:1278389799857946700> to learn more.", ephemeral=True)
        return is_donor

async def is_booster(interaction):
    user_id = str(interaction.user.id)
    cached_result = await redis_client.get(f"booster:{user_id}")
    if cached_result is not None:
        is_booster = cached_result == "True"
        if not is_booster:
            await interaction.response.send_message(
                "<:boosts:1263854701535821855> This is a booster-only command. Boost the server to access this feature!",
                ephemeral=True
            )
        return is_booster
    
    async with get_db_connection() as conn:
        result = await conn.fetchval('SELECT booster FROM user_data WHERE user_id = $1', user_id)
        is_booster = bool(result)
        
        await redis_client.setex(f"booster:{user_id}", 300, str(is_booster))
        
        if not is_booster:
            await interaction.response.send_message(
                "<:boosts:1263854701535821855> This is a booster-only command. Boost the server to access this feature!",
                ephemeral=True
            )
        return is_booster

async def invalidate_cache(user_id: str):
    user_id = str(user_id)
    await redis_client.delete(f"owner:{user_id}", f"blacklist:{user_id}", f"donor:{user_id}")

async def is_disabled(interaction):
    creator_ids = ["123"]
    if str(interaction.user.id) not in creator_ids:
        await interaction.response.send_message("This command is temporarily disabled.", ephemeral=True)
        return False
    return True

async def is_creator(interaction):
    creator_ids = ["1326213864391442504", "935448935777050645", "1363295564133040272"]
    if str(interaction.user.id) not in creator_ids:
        await interaction.response.send_message("This command is not available to you.", ephemeral=True)
        return False
    return True

async def is_bloxlink_staff(interaction):
    bstaff_ids = ["84117866944663552"]
    if str(interaction.user.id) in bstaff_ids:
        await interaction.response.send_message("This command is disabled.", ephemeral=True)
        return False
    return True

async def is_tester(interaction):
    tester_ids = ["1326213864391442504", "249837467128037376"]
    if str(interaction.user.id) not in tester_ids:
        await interaction.response.send_message("This command is still in testing.", ephemeral=True)
        return False
    return True

async def is_ecorework(interaction):
    user_id = str(interaction.user.id)
    cached_result = await redis_client.get(f"owner:{user_id}")
    if cached_result is not None:
        is_owner = cached_result == "True"
        if not is_owner:
            await interaction.response.send_message("This will be available next economy reset.", ephemeral=True)
        return is_owner

    async with get_db_connection() as conn:
        result = await conn.fetchval('SELECT user_id FROM owners WHERE user_id = $1', user_id)
        is_owner = bool(result)
        await redis_client.setex(f"owner:{user_id}", 300, str(is_owner))

        if not is_owner:
            await interaction.response.send_message("This will be available next economy reset.", ephemeral=True)
        return is_owner

def requires_perms(**perms_required):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cti = args[1] if len(args) > 1 else kwargs.get('ctx', kwargs.get('interaction', None))
            
            if isinstance(cti, commands.Context):
                ctx = cti
                if not ctx.guild:
                    return await func(*args, **kwargs)
                
                permissions = ctx.channel.permissions_for(ctx.guild.me)
                missing = [perm for perm, value in perms_required.items() if getattr(permissions, perm, None) != value]
                
                if missing:
                    missing_permissions_str = "`" + "` & `".join(missing) + "`"
                    if ctx.channel.permissions_for(ctx.guild.me).embed_links:
                        embed = discord.Embed(
                            description=f"<:warning:1350239604925530192> {ctx.author.mention}: Bot is missing the required {missing_permissions_str} permissions.",
                            color=0xf9a719
                        )
                        await ctx.send(embed=embed)
                    else:
                        await ctx.send(f"<:warning:1350239604925530192> {ctx.author.mention}: Bot is missing the required {missing_permissions_str} permissions.")
                    return
            
            elif isinstance(cti, discord.Interaction):
                interaction = cti
                ephemeral = False
                
                if interaction.guild:
                    app_permissions = interaction.app_permissions
                    
                    has_all_perms = True
                    for perm_name, required in perms_required.items():
                        if required and not getattr(app_permissions, perm_name, False):
                            has_all_perms = False
                            break
                    
                    ephemeral = not has_all_perms
                
                try:
                    await interaction.response.defer(thinking=True, ephemeral=ephemeral)
                    
                    return await func(*args, **kwargs)
                    
                except discord.Forbidden as e:
                    if e.code == 50013:
                        try:
                            await interaction.followup.send(
                                "I don't have permission to perform this action in this channel. Please check my channel permissions and try again.",
                                ephemeral=True
                            )
                        except Exception:
                            pass
                    else:
                        raise e
                except Exception as e:
                    logging.error(f"Error in {func.__name__}: {str(e)}")
                    try:
                        await interaction.followup.send(
                            f"{e}",
                            ephemeral=True
                        )
                    except Exception:
                        pass
                    raise e
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

async def handle_command_error(ctx, error):
    if ctx is None:
        return

    if isinstance(error, commands.CommandNotFound):
        return

    elif isinstance(error, commands.MissingPermissions):
        missing_permissions = error.missing_permissions
        missing_permissions_str = "`" + "` & `".join(missing_permissions) + "`"
    
        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            embed = discord.Embed(
                description=f"<:warning:1350239604925530192> {ctx.author.mention}: You are missing the {missing_permissions_str} permissions.",
                color=0xf9a719
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"<:warning:1350239604925530192> {ctx.author.mention}: You are missing the {missing_permissions_str} permissions.")
    
    elif isinstance(error, commands.BotMissingPermissions):
        missing_permissions = error.missing_permissions
        missing_permissions_str = "`" + "` & `".join(missing_permissions) + "`"
        
        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            embed = discord.Embed(
                description=f"<:warning:1350239604925530192> {ctx.author.mention}: Bot is missing the required {missing_permissions_str} permissions.",
                color=0xf9a719
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"<:warning:1350239604925530192> {ctx.author.mention}: Bot is missing the required {missing_permissions_str} permissions.")
    else:
        raise error
