import discord
from discord import app_commands, Embed
from discord.ext import commands, tasks
from discord.ui import Button, View
from utils.db import check_blacklisted, check_booster, check_donor, check_owner, check_famous, execute_query, get_db_connection, redis_client
from utils.cd import cooldown
from utils.error import error_handler
from utils.embed import cembed
from utils.cache import get_embed_color
from utils import default, permissions
from dotenv import dotenv_values
from PIL import Image, ImageSequence
from pydub import AudioSegment
from io import BytesIO
import aiohttp, time, json, io, random, os
import urllib
from urllib.parse import urljoin, urlparse
from collections import defaultdict
import asyncpg, asyncio, aiofiles
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import redis.asyncio as redis
import base64

footer = "heist.lol"
config = dotenv_values(".env")
TOKEN = config["DISCORD_TOKEN"]
API_KEY = config["HEIST_API_KEY"]
LURE_KEY = config["LURE_API_KEY"]
LASTFM_KEY = config["LASTFM_API_KEY"]
DATADB = config['DATA_DB']

class AvatarHistoryView(discord.ui.View):
    def __init__(self, interaction, avatar_data, user, interaction_user):
        super().__init__(timeout=240)
        self.interaction = interaction
        self.avatar_history = avatar_data.get('avatars', []) if avatar_data else []
        self.index = 0
        self.user = user
        self.interaction_user = interaction_user
        self.update_buttons()

    @property
    def current_avatar(self):
        if self.avatar_history:
            return self.avatar_history[self.index]
        return None

    def update_buttons(self):
        if not self.avatar_history:
            self.previous_button.disabled = True
            self.next_button.disabled = True
            self.skip_button.disabled = True
            self.delete_button.disabled = True
        else:
            self.previous_button.disabled = self.index <= 0
            self.next_button.disabled = self.index >= len(self.avatar_history) - 1
            self.skip_button.disabled = False
            self.delete_button.disabled = False

    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary, custom_id="avatarleft")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction_user:
            await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
            return

        if self.avatar_history:
            self.index = max(0, self.index - 1)
            self.update_buttons()
            embed = await self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary, custom_id="avatarright")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction_user:
            await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
            return

        if self.avatar_history:
            self.index = min(len(self.avatar_history) - 1, self.index + 1)
            self.update_buttons()
            embed = await self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary, custom_id="avatarskip")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction_user:
            await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
            return

        class GoToPageModal(discord.ui.Modal, title="Go to Page"):
            def __init__(self, view):
                super().__init__()
                self.view = view
                self.page_number = discord.ui.TextInput(
                    label="Navigate to page",
                    placeholder=f"Enter a page number (1-{len(self.view.avatar_history)})",
                    min_length=1,
                    max_length=len(str(len(self.view.avatar_history))))
                self.add_item(self.page_number)

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    page = int(self.page_number.value) - 1
                    if page < 0 or page >= len(self.view.avatar_history):
                        raise ValueError
                    self.view.index = page
                    self.view.update_buttons()
                    embed = await self.view.create_embed()
                    await interaction.response.edit_message(embed=embed, view=self.view)
                except ValueError:
                    await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

        modal = GoToPageModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger, custom_id="avatardelete")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction_user:
            await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
            return

        await interaction.response.defer()
        await interaction.delete_original_response()

    async def create_embed(self):
        if not self.avatar_history:
            return await cembed(
                self.interaction,
                title=f"{self.user.name}'s avatar history",
                description="No avatar history found for user."
            )

        avatar_info = self.current_avatar
        page_number = self.index + 1
        total_pages = len(self.avatar_history)
        
        embed = await cembed(
            self.interaction,
            title=f"{self.user.name}'s avatar history"
        )
        embed.set_image(url=avatar_info)
        embed.set_footer(text=f"Page {page_number}/{total_pages} - powered by lure.rocks", icon_url="https://csyn.me/assets/heist.png?c")

        return embed

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                item.disabled = True

        try:
            await self.interaction.edit_original_response(view=self)
        except discord.NotFound:
            pass

class Discord(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.badge_emojis = {
            "hypesquad_house_1": "<:hypesquad_bravery:1263855923806470144>",
            "hypesquad_house_2": "<:hypesquad_brilliance:1263855913480097822>",
            "hypesquad_house_3": "<:hypesquad_balance:1263855909420138616>",
            "premium": "<:nitro:1263855900846981232>",
            "premium_type_1": "<:bronzen:1293983425828753480>",
            "premium_type_2": "<:silvern:1293983951983083623>",
            "premium_type_3": "<:goldn:1293983938485686475>",
            "premium_type_4": "<:platinumn:1293983921469526137>",
            "premium_type_5": "<:diamondn:1293983900435091566>",
            "premium_type_6": "<:emeraldn:1293983816259731527>",
            "premium_type_7": "<:rubyn:1293983910342164655>",
            "premium_type_8": "<:firen:1293983849264582666>",
            "guild_booster_lvl1": "<:boosts1:1263857045027819560>",
            "guild_booster_lvl2": "<:boosts2:1263857025658388613>",
            "guild_booster_lvl3": "<:boosts:1263856979911245897>",
            "guild_booster_lvl4": "<:boosts4:1263856929835450469>",
            "guild_booster_lvl5": "<:boosts5:1263856884708937739>",
            "guild_booster_lvl6": "<:boosts6:1263856802638860370>",
            "guild_booster_lvl7": "<:boosts7:1263856551555502211>",
            "guild_booster_lvl8": "<:boosts8:1263856534216114298>",
            "guild_booster_lvl9": "<:boosts9:1263856512506400871>",
            "early_supporter": "<:early_supporter:1265425918843814010>",
            "verified_developer": "<:earlybotdev:1265426039509749851>",
            "active_developer": "<:activedeveloper:1265426222444183645>",
            "hypesquad": "<:hypesquad_events:1265426613605240863>",
            "bug_hunter_level_1": "<:bughunter_1:1265426779523252285>",
            "bug_hunter_level_2": "<:bughunter_2:1265426786607562893>",
            "staff": "<:staff:1265426958322241596>",
            "partner": "<:partner:1265426965511536792>",
            "bot_commands": "<:supports_commands:1265427168469712908>",
            "legacy_username": "<:pomelo:1265427449999659061>",
            "quest_completed": "<:quest:1265427335058948247>",
            "bot": "<:bot:1290389425850679388>",
            "heist": "<:heist:1273999266154811392>"
        }
        # self.ctx_guilds2 = app_commands.ContextMenu(
        #     name='User Guilds',
        #     callback=self.guilds2,
        # )
        self.ctx_userinfo2 = app_commands.ContextMenu(
            name='View Profile',
            callback=self.userinfo2,
        )
        self.ctx_userroast = app_commands.ContextMenu(
            name='Roast User',
            callback=self.userroast,
        )
        # self.client.tree.add_command(self.ctx_guilds2)
        self.client.tree.add_command(self.ctx_userinfo2)
        self.client.tree.add_command(self.ctx_userroast)
        self.redis = redis_client
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    #@commands.Cog.listener()
    # async def on_message(self, message):
    #     try:
    #         if message.author.bot:
    #             return

    #         if message.guild:
    #             guild_name = message.guild.name
    #             channel_name = message.channel.name

    #         await update_last_seen(
    #             message.author.id, 
    #             guild_name, 
    #             channel_name
    #         )
    #     except Exception as e:
    #         print(f"Error updating last seen for user {message.author.id}: {e}")

    #@commands.Cog.listener()
    # async def on_voice_state_update(self, member, before, after):
    #     try:
    #         if member.bot:
    #             return
            
    #         guild_id = str(member.guild.id)
    #         guild_name = member.guild.name
            
    #         if after.channel:
    #             vc_data = {
    #                 'guild_name': guild_name,
    #                 'channel_name': after.channel.name,
    #                 'guild_id': guild_id,
    #                 'channel_id': str(after.channel.id),
    #                 'self_mute': after.self_mute,
    #                 'self_deaf': after.self_deaf,
    #                 'mute': after.mute,
    #                 'deaf': after.deaf,
    #                 'timestamp': int(discord.utils.utcnow().timestamp())
    #             }
    #             await redis_client.hset(
    #                 'vc_users',
    #                 str(member.id),
    #                 json.dumps(vc_data)
    #             )
            
    #         elif before.channel:
    #             await redis_client.hdel('vc_users', str(member.id))
            
    #         if before.channel and after.channel:
    #             if (before.self_mute != after.self_mute or 
    #                 before.self_deaf != after.self_deaf or 
    #                 before.mute != after.mute or 
    #                 before.deaf != after.deaf):
                    
    #                 vc_data = {
    #                     'guild_name': guild_name,
    #                     'channel_name': after.channel.name,
    #                     'guild_id': guild_id,
    #                     'channel_id': str(after.channel.id),
    #                     'self_mute': after.self_mute,
    #                     'self_deaf': after.self_deaf,
    #                     'mute': after.mute,
    #                     'deaf': after.deaf,
    #                     'timestamp': int(discord.utils.utcnow().timestamp())
    #                 }
    #                 await redis_client.hset(
    #                     'vc_users',
    #                     str(member.id),
    #                     json.dumps(vc_data)
    #                 )
        
    #     except Exception as e:
    #         print(f"Error updating VC state for user {member.id}: {e}")

    async def get_last_seen(self, user_id):
        try:
            key = f'last_seen_users:{user_id}'
            last_seen_str = await self.redis.get(key)
            if last_seen_str:
                return json.loads(last_seen_str)
            return None
        except Exception as e:
            print(f"Error retrieving last seen for user {user_id}: {e}")
            return None

    async def get_last_seen_info(self, user, limited):
        try:
            async with get_db_connection() as conn:
                result = ""

                if limited:
                    return {}

                last_seen_data = await self.get_last_seen(user.id)
                print(last_seen_data)
                if last_seen_data:
                    guild_name = last_seen_data['guild_name']
                    channel_name = last_seen_data['channel_name']
                    timestamp = int(last_seen_data['timestamp'])
                    time_str = f"<t:{timestamp}:R>"

                    guild_activity_state = await conn.fetchrow(
                        "SELECT guild_activity_state FROM settings WHERE user_id = $1", str(user.id)
                    )
                    
                    if guild_activity_state is None:
                        guild_activity = True
                    else:
                        guild_activity = guild_activity_state['guild_activity_state'] == 'Enabled'

                    if guild_activity:
                        result += f"\n-# <:channel:1319456081528885359> Recently seen in **{guild_name}** {time_str}"

                vc_key = f'vc_state:{user.id}'
                vc_data_str = await self.redis.get(vc_key)
                if vc_data_str:
                    vc_data = json.loads(vc_data_str)
                    guild_name = vc_data.get('guild_name', 'Unknown Guild')
                    channel_name = vc_data.get('channel_name', 'Unknown Channel')
                    guild_id = vc_data.get('guild_id', None)
                    channel_id = vc_data.get('channel_id', None)

                    if not channel_id:
                        await self.redis.delete(vc_key)
                        return ""

                    voice_state_emojis = []
                    if vc_data.get('mute'):
                        voice_state_emojis.append("<:server_mute:1319357944332030043>")
                    elif vc_data.get('self_mute'):
                        voice_state_emojis.append("<:self_mute:1318966624816074782>")

                    if vc_data.get('deaf'):
                        voice_state_emojis.append("<:server_deaf:1319357938074128504>")
                    elif vc_data.get('self_deaf'):
                        voice_state_emojis.append("<:self_deafen:1318966630629511239>")

                    if channel_name == "Unknown Channel":
                        result += f"\n-# <:self_voice:1318730750685741076> {' '.join(voice_state_emojis)} Connected to [a VC](https://discord.com/channels/{guild_id}/{channel_id}) in **{guild_name}**"
                    else:
                        result += f"\n-# <:self_voice:1318730750685741076> {' '.join(voice_state_emojis)} Connected to [{channel_name}](https://discord.com/channels/{guild_id}/{channel_id}) in **{guild_name}**"

                return result

        except Exception as e:
            print(f"Error processing last seen info: {e}")
            return ""

    async def cog_unload(self) -> None:
        # self.client.tree.remove_command(self.ctx_guilds2.name, type=self.ctx_guilds2.type)
        self.client.tree.remove_command(self.ctx_userinfo2.name, type=self.ctx_userinfo2.type)
        self.client.tree.remove_command(self.ctx_userroast.name, type=self.ctx_userroast.type)
        # try:
        #     self.client.remove_listener(self.on_message)
        #     self.client.remove_listener(self.on_voice_state_update)
        # except Exception:
        #     pass

    async def check_user_in_heist_db(self, user_id: str) -> bool:
        conn = await asyncpg.connect(dsn=DATADB)
        try:
            query = "SELECT 1 FROM user_data WHERE user_id = $1 LIMIT 1"
            result = await conn.fetchval(query, str(user_id))
            return result is not None
        except Exception as e:
            print(e)
            return False
        finally:
            await conn.close()

    discordg = app_commands.Group(
        name="discord", 
        description="Discord related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
   )

    # @app_commands.allowed_installs(guilds=True, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    # @app_commands.check(permissions.is_blacklisted)
    # @app_commands.check(permissions.is_donor)
    # async def guilds2(self, interaction: discord.Interaction, user: discord.User) -> None:
    #     await self.skibidisigma(interaction, user)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def userinfo2(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self.evilskibidisigma(interaction, user)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def userroast(self, interaction: discord.Interaction, user: discord.User) -> None:
        await interaction.response.defer(thinking=True)

        if user.id == 1225070865935368265:
            await interaction.followup.send("real funny, buddy.")
            return

        username = user.name
        alpha_chars = [char for char in username if char.isalpha()]

        is_3l = len(alpha_chars) == 3
        is_3c = len(username) == 3 and not is_3l 
        is_4l = len(alpha_chars) == 4
        is_4c = len(username) == 4 and not is_4l

        if is_3c:
            lroast = "his username is 3 characters, so roast em extra hard for being basic af. like 'this ape really thinks his lame ahh 3c is og aint no way 💀.'"
        elif is_3l:
            lroast = "his username is 3 letters, so roast em extra hard for being basic af. like 'this ape really thinks his lame ahh 3l is og aint no way 💀.'"
        elif is_4c:
            lroast = "his username is 4 characters, so roast em extra hard for being basic af. like 'this ape really thinks his lame ahh 4c is og aint no way 💀.'"
        elif is_4l:
            lroast = "his username is 4 letters, so roast em extra hard for being basic af. like 'this ape really thinks his lame ahh 4l is og aint no way 💀.'"
        else:
            lroast = ""

        slang = [
            "wsg", "fr", "no cap", "man's finished", "violated", "ain’t no way", "bro thinks he's", "certi clown", 
            "you mad poor", "broke ass nigga", "ur some sad fuck", "on god", "deadass", "cappin'", "glazin'", 
            "touch grass", "ratio", "L + bozo", "take the L", "you fell off", "weirdo behavior", "goofy ahh", 
            "ur done for", "ur washed", "ur dusted", "ur finished", "ur cooked", "ur zesty", "ur a walking meme", 
            "ur a glizzy gladiator", "ur a benchwarmer", "ur a participation trophy", "ur a background character", 
            "ur a side quest", "ur a loading screen", "ur a placeholder", "ur a beta tester", "ur a debug mode", 
            "ur a glitch", "ur a patch note", "ur a hotfix", "ur a DLC", "ur a loot box", "ur a pay-to-win", 
            "ur a skill issue", "ur a lag spike", "ur a connection timeout", "ur a 404 error"
        ]
        insults = [
            "ur poor asf bruh get some funds", 
            "come depo w me broke ass nigga", 
            "u look like u be begging for $5 on cashapp", 
            "u built like u still owe niggas money from last year", 
            "u look like u be asking for spare change at the gas station", 
            "u broke as hell but still got the nerve to flex fake jewelry", 
            "u look like u be eating ramen noodles with no seasoning", 
            "u built like u be sharing a Netflix account with 10 other niggas", 
            "u look like u be asking for free trials on everything", 
            "u broke ass nigga still using a prepaid phone", 
            "u look like u be walking to the store cuz u can’t afford gas", 
            "u built like u be asking for extra ketchup packets to save for later", 
            "u look like u be stealing Wi-Fi from the neighbors", 
            "u broke ass nigga still using a library card to watch movies", 
            "u look like u be asking for water at restaurants cuz u can’t afford a drink", 
            "u built like u be reusing paper plates to save money", 
            "u look like u be asking for a discount on a $1 item", 
            "u broke ass nigga still using a flip phone in 2023", 
            "u look like u be asking for free refills on a $2 soda", 
            "u built like u be saving napkins from fast food places", 
            "u look like u be asking for extra bread at restaurants", 
            "u broke ass nigga still using a CD player", 
            "u look like u be asking for a ride cuz u can’t afford a car", 
            "u built like u be reusing plastic bags as trash bags", 
            "u look like u be asking for a discount on a $5 item", 
            "u broke ass nigga still using a VCR", 
            "u look like u be asking for free samples at the grocery store", 
            "u built like u be saving condiment packets to use at home", 
            "u look like u be asking for a ride cuz u can’t afford gas", 
            "u broke ass nigga still using a pager", 
            "u look like u be asking for a discount on a $10 item", 
            "u built like u be reusing aluminum foil to save money", 
            "u look like u be asking for free Wi-Fi at McDonald’s", 
            "u broke ass nigga still using a fax machine", 
            "u look like u be asking for a ride cuz u can’t afford a bus pass", 
            "u built like u be saving plastic utensils to use at home", 
            "u look like u be asking for a discount on a $20 item", 
            "u broke ass nigga still using a landline", 
            "u look like u be asking for free parking at the mall", 
            "u built like u be reusing plastic cups to save money", 
            "u look like u be asking for a ride cuz u can’t afford a train ticket", 
            "u broke ass nigga still using a typewriter", 
            "u look like u be asking for a discount on a $50 item", 
            "u built like u be saving straws to use at home", 
            "u look like u be asking for free admission to the movies", 
            "u broke ass nigga still using a rotary phone", 
            "u look like u be asking for a ride cuz u can’t afford a plane ticket", 
            "u built like u be reusing plastic bottles to save money", 
            "u look like u be asking for a discount on a $100 item", 
            "u broke ass nigga still using a cassette player", 
            "u look like u be asking for free entry to the club", 
            "nigga built like a vending machine that only takes exact change", 
            "you look like you got dressed in the dark with your eyes closed", 
            "bro really out here looking like a glitch in the matrix", 
            "you sound like a broken record player stuck on the worst song ever", 
            "nigga built like a fridge but got the personality of a wet sock", 
            "you look like you type with two fingers and still misspell your own name", 
            "bro really out here looking like a default character in a free-to-play game", 
            "you built like a participation trophy but ain’t even show up to the event", 
            "nigga got the energy of a Wi-Fi signal in a concrete basement", 
            "you look like you got your whole personality from a 2013 meme", 
            "bro really out here looking like a loading screen with no progress bar", 
            "you built like a glitchy NPC that keeps walking into walls", 
            "nigga got the swag of a loot box with nothing but commons", 
            "you look like you got your whole vibe from a TikTok trend that died last week", 
            "bro really out here looking like a debug mode with no purpose", 
            "you built like a patch note that just says 'minor bug fixes'", 
            "nigga got the energy of a hotfix that broke the game even more", 
            "you look like you got your whole style from a clearance rack at Walmart", 
            "bro really out here looking like a DLC nobody asked for", 
            "you built like a pay-to-win character but still losing every match", 
            "nigga got the swag of a skill issue but still blaming the game", 
            "you look like you got your whole personality from a lag spike", 
            "bro really out here looking like a connection timeout with no retries", 
            "you built like a 404 error but still trying to load", 
            "nigga got the energy of a broken Snapchat filter that nobody uses", 
            "you look like you got your whole vibe from a canceled Netflix show", 
            "bro really out here looking like a glitchy JPEG that won’t load", 
            "you built like a corrupted file that nobody wants to recover", 
            "nigga got the swag of a failed meme that nobody laughed at", 
            "you look like you got your whole style from a MySpace profile",
            "u look like u been lost since 2007", 
            "u built like u been buffering since dial-up", 
            "u look like u been typing with one finger since 1999", 
            "u built like u been rendering since Windows 95", 
            "u look like u been stuck on the loading screen of life", 
            "u built like u been lagging since AOL", 
            "u look like u been waiting for a text back since flip phones", 
            "u built like u been downloading since DSL", 
            "u look like u been stuck in traffic since the invention of cars", 
            "u built like u been buffering since YouTube was created", 
            "u look like u been waiting for a Wi-Fi connection since 2005", 
            "u built like u been rendering since Minecraft was released", 
            "u look like u been stuck on the loading screen of a PS2 game", 
            "u built like u been lagging since the first online game", 
            "u look like u been waiting for a text back since T9 keyboards", 
            "u built like u been downloading since Napster", 
            "u look like u been stuck in traffic since the invention of highways", 
            "u built like u been buffering since the first streaming service", 
            "u look like u been waiting for a Wi-Fi connection since 2010", 
            "u built like u been rendering since the first 3D game", 
            "u look like u been stuck on the loading screen of a PS3 game", 
            "u built like u been lagging since the first MMORPG", 
            "u look like u been waiting for a text back since BlackBerry phones", 
            "u built like u been downloading since LimeWire", 
            "u look like u been stuck in traffic since the invention of GPS", 
            "u built like u been buffering since the first HD video", 
            "u look like u been waiting for a Wi-Fi connection since 2015", 
            "u built like u been rendering since the first open-world game", 
            "u look like u been stuck on the loading screen of a PS4 game", 
            "u built like u been lagging since the first battle royale game", 
            "u look like u been waiting for a text back since iPhones", 
            "u built like u been downloading since Spotify", 
            "u look like u been stuck in traffic since the invention of Uber"] 
        exaggerations = ["gay ass nigga", "on god ur a fuck ass nigga", "bitch ass nigga", "built like an expired bean", "you weird as fuck", "edgy ass nigga"]
        emojis = ["🔥", "💀", "💯", "🧛‍♀️", "😭", "📉", "🗿"]

        system_prompt = (
            f"yo, u gotta roast {user.name} based on their username. keep it raw af, "
            "forget your default roasts/insults, make new ones up."
            f"super casual, lowercase, and straight to the point. throw in slang like '{random.choice(slang)}' and 'fr' "
            "and don’t hold back—be funny, sarcastic, and mean as hell. exaggerate when shit sucks. "
            "don't use exclamation marks that shit makes you look dumb. press em a lil, act like a roadman. "
            "make your own jokes and phrases, get creative, and come up with fresh, unique roasts every time. "
            "every response should introduce a new, creative insult that hasn’t been used before. reuse = bad roast. "
            "avoid framing anything in quotes, if referring to the username, just bold it instead using **. "
            "do not mention anything about a chocolate teapot, useless teapot, or any variation of that phrase. avoid overused jokes—generate fresh and unique insults every time."
            f"come up with things like '{random.choice(insults)}' or '{random.choice(exaggerations)}', different ones though, these are just examples. "
            f"use emojis like {random.choice(emojis)} {random.choice(emojis)} and keep it under 600 chars. "
            f"{lroast} "
            f"their username is {user.name}."
        )
        user_prompt = f"username: {user.name}, roast them."
        
        system_prompt = urllib.parse.quote(system_prompt)
        user_prompt = urllib.parse.quote(user_prompt)

        api_url = f"https://text.pollinations.ai/{user_prompt}?system={system_prompt}&model=llama&seed=12345"

        async with self.session.get(api_url) as response:
            if response.status == 200:
                roast_text = await response.text()
                await interaction.followup.send(f"{roast_text}")
            else:
                await interaction.followup.send("Failed to generate a roast. Try again later.")

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user to get the avatar of, leave empty to get your own.")
    @app_commands.check(permissions.is_blacklisted)
    async def avatar(self, interaction: discord.Interaction, user: discord.User = None, decoration: bool = False):
        """View a user's avatar."""
        user = user or interaction.user

        try:
            avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
            if decoration and user.avatar_decoration:
                if not interaction.app_permissions.attach_files:
                    await interaction.response.defer(ephemeral=True)
                else:
                    await interaction.response.defer()

                async with self.session.get(avatar_url) as resp:
                    avatar_data = await resp.read()
                async with self.session.get(user.avatar_decoration.url) as resp:
                    deco_data = await resp.read()

                avatar_img = await asyncio.to_thread(Image.open, io.BytesIO(avatar_data))
                deco_img = await asyncio.to_thread(Image.open, io.BytesIO(deco_data))

                avatar_img = avatar_img.convert("RGBA")
                deco_img = deco_img.convert("RGBA")

                deco_img = deco_img.resize(avatar_img.size, Image.LANCZOS)
                combined = Image.alpha_composite(avatar_img, deco_img)

                output = io.BytesIO()
                await asyncio.to_thread(combined.save, output, format="PNG")
                output.seek(0)

                await interaction.followup.send(file=discord.File(output, filename="heist.png"))
            else:
                await interaction.response.send_message(avatar_url)

        except Exception as e:
            await error_handler(interaction, e)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.describe(user="The user to get the server avatar of, leave empty to get your own.")
    async def serveravatar(self, interaction: discord.Interaction, user: discord.Member = None):
        """View a user's server-specific avatar."""
        user = user or interaction.user

        try:
            if interaction.guild and isinstance(user, discord.Member) and user.guild_avatar:
                avatar_url = user.guild_avatar.url
            else:
                avatar_url = user.avatar.url if user.avatar else user.default_avatar.url

            await interaction.response.send_message(avatar_url)
        except Exception as e:
            await error_handler(interaction, e)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user to get the banner of, leave empty to get your own.")
    @app_commands.check(permissions.is_blacklisted)
    async def banner(self, interaction: discord.Interaction, user: discord.User = None):
        """View a user's banner."""
        user = user or interaction.user

        try:
            full_user = await self.client.fetch_user(user.id)

            banner = full_user.banner
            if banner is None:
                return await interaction.response.send_message(f"**{user}** has no banner set.")

            await interaction.response.send_message(banner)

        except Exception as e:
            await error_handler(interaction, e)

    # @discordg.command()
    # @app_commands.allowed_installs(guilds=True, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    # @app_commands.describe(user="The user to get information from, leave empty to get your own.")
    # @app_commands.check(permissions.is_blacklisted)
    # @app_commands.check(permissions.is_donor)
    # @app_commands.check(permissions.is_bloxlink_staff)
    # async def guilds(self, interaction: discord.Interaction, user: discord.User = None):
    #     """Return the guilds a user shares with Heist. (PREMIUM)"""
    #     await self.skibidisigma(interaction, user or interaction.user)

    async def skibidisigma(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(thinking=True, ephemeral=True)
        user = user or interaction.user

        processing_embed = await cembed(description=f"<a:loading:1269644867047260283> {interaction.user.mention}: processing..")
        processing = await interaction.followup.send(embed=processing_embed)

        headers = {"X-API-Key": API_KEY}
        guilds_info = []
        guild_ids = set()

        async with get_db_connection() as conn:
            try:
                create_table_query = """
                CREATE TABLE IF NOT EXISTS settings (
                    user_id BIGINT PRIMARY KEY,
                    guilds_state TEXT DEFAULT 'Show'
                )
                """
                await conn.execute(create_table_query)

                select_query = "SELECT guilds_state FROM settings WHERE user_id = $1"
                result = await conn.fetchrow(select_query, str(user.id))

                if result:
                    guilds_state = result['guilds_state']
                else:
                    insert_query = "INSERT INTO settings (user_id, guilds_state) VALUES ($1, 'Show')"
                    await conn.execute(insert_query, str(user.id))
                    guilds_state = 'Show'

            finally:
                await conn.close()

        if guilds_state == 'Show':
            retries = 0
            max_retries = 5
            backoff_factor = 2
            timeout = aiohttp.ClientTimeout(total=2)

            while retries < max_retries:
                try:
                    async with self.session.get(f"http://127.0.0.1:8002/mutualguilds/{user.id}", headers=headers, timeout=timeout) as resp:
                        if resp.status == 200:
                            guilds_data = await resp.json()
                            for guild_data in guilds_data:
                                guild_id = guild_data.get("id")
                                if guild_id not in guild_ids:
                                    guild_ids.add(guild_id)
                                    guilds_info.append(guild_data)

                            if len(guilds_info) == 0:
                                embed = await cembed(
                                    interaction,
                                    title=f"{user.name}'s guilds shared with Heist (0)",
                                    description="-# No guilds shared with user."
                                )
                                embed.set_footer(text=footer, icon_url="https://csyn.me/assets/heist.png?c")
                                embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
                                await processing.edit(embed=embed)
                                return

                            total_pages = (len(guilds_info) + 4) // 5
                            current_page = 0

                            embed = await cembed(
                                interaction,
                                title=f"{user.name}'s guilds shared with Heist ({len(guilds_info)})",
                                url=f"https://discord.com/users/{user.id}",
                            )

                            if interaction.user.id == user.id:
                                embed.description = "You can hide this with </settings:1278389799681527967>.\n\n"
                            else:
                                embed.description = ""

                            start_idx = current_page * 5
                            end_idx = min(start_idx + 5, len(guilds_info))

                            for guild in guilds_info[start_idx:end_idx]:
                                guild_name = guild.get("name", "Unknown Guild")
                                vanity = guild.get("vanity_url")
                                vanity_text = f"`discord.gg/{vanity}`" if vanity else "`no vanity found`"
                                embed.description += f"**{guild_name}**\n-# {vanity_text}\n\n"

                            embed.set_author(
                                name=f"{interaction.user.name}",
                                icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url
                            )
                            embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
                            embed.set_footer(text=f"Page {current_page + 1}/{total_pages} • {footer}", icon_url="https://csyn.me/assets/heist.png?c")

                            view = discord.ui.View()

                            first_button = discord.ui.Button(
                                emoji=discord.PartialEmoji.from_str("<:lleft:1282403520254836829>"), 
                                style=discord.ButtonStyle.secondary, 
                                disabled=True
                            )
                            view.add_item(first_button)

                            previous_button = discord.ui.Button(
                                emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), 
                                style=discord.ButtonStyle.secondary, 
                                disabled=True
                            )
                            view.add_item(previous_button)

                            next_button = discord.ui.Button(
                                emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), 
                                style=discord.ButtonStyle.secondary, 
                                disabled=total_pages <= 1
                            )
                            view.add_item(next_button)

                            last_button = discord.ui.Button(
                                emoji=discord.PartialEmoji.from_str("<:rright:1282516005385404466>"), 
                                style=discord.ButtonStyle.secondary, 
                                disabled=total_pages <= 1
                            )
                            view.add_item(last_button)

                            json_button = discord.ui.Button(
                                emoji=discord.PartialEmoji.from_str("<:json:1292867766755524689>"),
                                style=discord.ButtonStyle.secondary
                            )
                            view.add_item(json_button)

                            async def button_callback(button_interaction: discord.Interaction):
                                nonlocal current_page
                                if button_interaction.user.id != interaction.user.id:
                                    await button_interaction.response.send_message("You cannot use these buttons.", ephemeral=True)
                                    return

                                if button_interaction.data["custom_id"] == "first":
                                    current_page = 0
                                elif button_interaction.data["custom_id"] == "previous":
                                    current_page = max(0, current_page - 1)
                                elif button_interaction.data["custom_id"] == "next":
                                    current_page = min(total_pages - 1, current_page + 1)
                                elif button_interaction.data["custom_id"] == "last":
                                    current_page = total_pages - 1

                                embed.description = "You can hide this with </settings:1278389799681527967>.\n\n" if interaction.user.id == user.id else ""

                                start_idx = current_page * 5
                                end_idx = min(start_idx + 5, len(guilds_info))

                                for guild in guilds_info[start_idx:end_idx]:
                                    guild_name = guild.get("name", "Unknown Guild")
                                    vanity = guild.get("vanity_url")
                                    vanity_text = f"`discord.gg/{vanity}`" if vanity else "`no vanity found`"
                                    embed.description += f"**{guild_name}**\n-# {vanity_text}\n\n"

                                embed.set_footer(text=f"Page {current_page + 1}/{total_pages} • {footer}", icon_url="https://csyn.me/assets/heist.png?c")

                                view.children[0].disabled = current_page == 0
                                view.children[1].disabled = current_page == 0
                                view.children[2].disabled = current_page == total_pages - 1
                                view.children[3].disabled = current_page == total_pages - 1

                                await button_interaction.response.edit_message(embed=embed, view=view)

                            async def json_button_callback(button_interaction: discord.Interaction):
                                formatjson = json.dumps(guilds_info, indent=4)
                                file = io.BytesIO(formatjson.encode())
                                await button_interaction.response.send_message(file=discord.File(file, filename="guilds.json"), ephemeral=True)

                            first_button.custom_id = "first"
                            previous_button.custom_id = "previous"
                            next_button.custom_id = "next"
                            last_button.custom_id = "last"
                            json_button.custom_id = "json"

                            for button in view.children:
                                button.callback = button_callback

                            json_button.callback = json_button_callback

                            await processing.edit(embed=embed, view=view)
                            break

                except Exception as e:
                    print(f"Error occurred: {e}. Retrying...")
                    retries += 1
                    await asyncio.sleep(backoff_factor * retries)
            else:
                await interaction.followup.send("An error occurred while fetching guilds after multiple attempts. Please try again later.", ephemeral=True)

        else:
            if interaction.user.id == user.id:
                error_message = await interaction.followup.send("This has been manually hidden by you. (</settings:1278389799681527967>)")
                await asyncio.sleep(1)
                await interaction.delete_original_response()
                await asyncio.sleep(5)
                await error_message.delete()
            else:
                error_message = await interaction.followup.send("This has been manually hidden by the user. (</settings:1278389799681527967>)")
                await asyncio.sleep(1)
                await interaction.delete_original_response()
                await asyncio.sleep(5)
                await error_message.delete()

    # emoji_cache = {}

    # async def download_image(self, image_url, file_path):
    #     async with aiohttp.ClientSession() as session:
    #         async with session.get(image_url) as response:
    #             with open(file_path, 'wb') as file:
    #                 file.write(await response.read())

    # async def upload_emoji(self, file_path, emoji_name):
    #     url = f"https://discord.com/api/v10/applications/1225070865935368265/emojis"
    #     headers = {
    #         "Authorization": f"Bot {TOKEN}",
    #         "Content-Type": "application/json"
    #     }

    #     with open(file_path, 'rb') as file:
    #         image_data = base64.b64encode(file.read()).decode('utf-8')

    #     payload = {
    #         "name": emoji_name,
    #         "image": f"data:image/png;base64,{image_data}"
    #     }

    #     async with aiohttp.ClientSession() as session:
    #         async with session.post(url, headers=headers, data=json.dumps(payload)) as response:
    #             if response.status in [200, 201]:
    #                 response_json = await response.json()
    #                 return response_json
    #             else:
    #                 print(f"Failed to upload emoji. Status code: {response.status}")
    #                 error_response = await response.text()
    #                 print(f"Error response: {error_response}")
    #                 return {}

    # async def delete_emoji(self, emoji_id):
    #     url = f"https://discord.com/api/v10/applications/1225070865935368265/emojis/{emoji_id}"
    #     headers = {
    #         "Authorization": f"Bot {TOKEN}"
    #     }
    #     async with aiohttp.ClientSession() as session:
    #         async with session.delete(url, headers=headers) as response:
    #             if response.status == 204:
    #                 return True
    #             else:
    #                 print(f"Failed to delete emoji. Status code: {response.status}")
    #                 error_response = await response.text()
    #                 print(f"Error response: {error_response}")
    #                 return False

    @discordg.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user to view the profile of.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=5, donor=0)
    async def user(self, interaction: discord.Interaction, user: discord.User = None):
        """View a Discord user's profile."""
        await self.evilskibidisigma(interaction, user or interaction.user)

    async def evilskibidisigma(self, interaction: discord.Interaction, user: discord.User):
        user = user or interaction.user
        is_blacklisted = await check_blacklisted(user.id)
        is_booster = await check_booster(user.id)
        is_donor = await check_donor(user.id)
        is_donor_self = await check_donor(interaction.user.id)
        is_owner = await check_owner(user.id)
        is_owner_self = await check_owner(interaction.user.id)
        user_in_db = await self.check_user_in_heist_db(user.id)
        embed_color = await get_embed_color(str(user.id))

        is_founder = user.id == 1363295564133040272

        badges = []
        badge_names = []
        full_user = await interaction.client.fetch_user(user.id)
        use_discord_method = True
        user_data = None

        try:
            url = f"http://127.0.0.1:8002/users/{user.id}"
            headers = {"X-API-Key": API_KEY}
            timeout = aiohttp.ClientTimeout(total=5)
            async with self.session.get(url, headers=headers, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and 'user' in data and 'id' in data['user']:
                        use_discord_method = False
                        user_data = data.get('user', {})
                        if 'badges' in data and data['badges']:
                            for badge in data['badges']:
                                badge_emoji = self.badge_emojis.get(badge['id'])
                                if badge_emoji and badge_emoji not in badges:
                                    badges.append(badge_emoji)
                                    badge_names.append(badge['id'])
                                    
                            if not user.bot and "premium_since" in data:
                                premium_since = datetime.fromisoformat(data["premium_since"].replace("Z", "+00:00"))
                                now = datetime.now(premium_since.tzinfo)
                                months_subscribed = (now - premium_since).days / 30.44
                                
                                nitro_emoji = None
                                nitro_key = None
                                if months_subscribed >= 72:
                                    nitro_emoji = self.badge_emojis.get("premium_type_8")
                                    nitro_key = "premium_type_8"
                                elif months_subscribed >= 60:
                                    nitro_emoji = self.badge_emojis.get("premium_type_7")
                                    nitro_key = "premium_type_7"
                                elif months_subscribed >= 36:
                                    nitro_emoji = self.badge_emojis.get("premium_type_6")
                                    nitro_key = "premium_type_6"
                                elif months_subscribed >= 24:
                                    nitro_emoji = self.badge_emojis.get("premium_type_5")
                                    nitro_key = "premium_type_5"
                                elif months_subscribed >= 12:
                                    nitro_emoji = self.badge_emojis.get("premium_type_4")
                                    nitro_key = "premium_type_4"
                                elif months_subscribed >= 6:
                                    nitro_emoji = self.badge_emojis.get("premium_type_3")
                                    nitro_key = "premium_type_3"
                                elif months_subscribed >= 3:
                                    nitro_emoji = self.badge_emojis.get("premium_type_2")
                                    nitro_key = "premium_type_2"
                                elif months_subscribed >= 1:
                                    nitro_emoji = self.badge_emojis.get("premium_type_1")
                                    nitro_key = "premium_type_1"
                                else:
                                    nitro_emoji = self.badge_emojis.get("premium")
                                    nitro_key = "premium"

                                if nitro_emoji:
                                    nitro_position = None
                                    if "premium" in badge_names:
                                        nitro_position = badge_names.index("premium")
                                    
                                    if nitro_key.startswith("premium_type_"):
                                        if nitro_position is not None:
                                            badges[nitro_position] = nitro_emoji
                                            badge_names[nitro_position] = nitro_key
                                        else:
                                            insert_index = 0
                                            for name in badge_names:
                                                if name > "premium":
                                                    break
                                                insert_index += 1
                                            badges.insert(insert_index, nitro_emoji)
                                            badge_names.insert(insert_index, nitro_key)
                                    elif nitro_key == "premium":
                                        if nitro_position is None:
                                            insert_index = 0
                                            for name in badge_names:
                                                if name > "premium":
                                                    break
                                                insert_index += 1
                                            badges.insert(insert_index, nitro_emoji)
                                            badge_names.insert(insert_index, nitro_key)
        except:
            use_discord_method = True
        
        if use_discord_method and not user.bot:
            user_flags = user.public_flags.all()
            for flag in user_flags:
                badge_emoji = self.badge_emojis.get(flag.name)
                if badge_emoji:
                    badges.append(badge_emoji)
                    badge_names.append(flag.name)

            if full_user.avatar and full_user.avatar.key.startswith('a_') or full_user.banner:
                nitro_emoji = self.badge_emojis.get("premium", "")
                if nitro_emoji:
                    insert_index = 0
                    for name in badge_names:
                        if name > "premium":
                            break
                        insert_index += 1
                    badges.insert(insert_index, nitro_emoji)
                    badge_names.insert(insert_index, "premium")
        elif user.bot:
            badges.append(self.badge_emojis.get("bot", ""))

        badge_string = f"### {' '.join(badges)}" if badges else ""

        async with get_db_connection() as conn:
            fame_status = await check_famous(user.id)

            heist_titles = []
            if user_in_db and not user.bot:
                if not is_blacklisted:
                    if is_owner:
                        if is_founder:
                            heist_titles.append("<a:heistowner:1343768654357205105> **`Heist Owner`**")
                        else:
                            heist_titles.append("<:hstaff:1311070369829883925> **`Heist Admin`**")
                    if fame_status:
                        heist_titles.append("<:famous:1311067416251596870> **`Famous`**")
                    if is_booster:
                        heist_titles.append("<:boosts:1263854701535821855> **`Booster`**")
                    if is_donor:
                        heist_titles.append("<:premium:1311062205650833509> **`Premium`**")
                    if not is_donor:
                        heist_titles.append("<:heist:1273999266154811392> **`Standard`**")
                else:
                    heist_titles.append("❌ **`Blacklisted`** (lol)")

            heist_titles_string = ", ".join(heist_titles)

            description = badge_string
            if heist_titles_string:
                description += f"\n{heist_titles_string}"
                
            user_id_str = str(user.id)
            result = await conn.fetchrow("SELECT lastfm_username FROM lastfm_usernames WHERE user_id = $1", user_id_str)
            lastfm_username = result['lastfm_username'] if result else None

            has_audio = False
            song_name = None
            artist_name = None
            if lastfm_username:
                try:
                    api_key = LASTFM_KEY
                    recent_tracks_url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={lastfm_username}&api_key={api_key}&format=json"

                    async with self.session.get(recent_tracks_url) as recent_tracks_response:
                        if recent_tracks_response.status == 200:
                            tracks = (await recent_tracks_response.json())['recenttracks'].get('track', [])

                            if tracks:
                                now_playing = None
                                for track in tracks:
                                    if '@attr' in track and 'nowplaying' in track['@attr'] and track['@attr']['nowplaying'] == 'true':
                                        now_playing = track
                                        break

                                if now_playing:
                                    artist_name = now_playing['artist']['#text']
                                    song_name = now_playing['name']

                                    trackenc = urllib.parse.quote_plus(song_name)
                                    artistenc = urllib.parse.quote_plus(artist_name)
                                    artist_url = f"https://www.last.fm/music/{artistenc}"
                                    api_url = f"http://127.0.0.1:2053/api/search?lastfm_username={lastfm_username}&track_name={trackenc}&artist_name={artistenc}"
                                    headers = {"X-API-Key": f"{API_KEY}"}
                                    
                                    async with self.session.get(api_url, headers=headers) as spotify_response:
                                        if spotify_response.status == 200:
                                            spotify_data = await spotify_response.json()
                                            song_url = spotify_data.get('spotify_link')
                                            description += f"\n-# <:lastfm:1275185763574874134> [**{song_name}**]({song_url}) by [{artist_name}]({artist_url})"
                                        else:
                                            description += f"\n-# <:lastfm:1275185763574874134> **{song_name}** by {artist_name}"
                                else:
                                    last_played = tracks[-1]
                                    artist_name = last_played['artist']['#text']
                                    song_name = last_played['name']

                                    trackenc = urllib.parse.quote_plus(song_name)
                                    artistenc = urllib.parse.quote_plus(artist_name)
                                    artist_url = f"https://www.last.fm/music/{artistenc}"
                                    api_url = f"http://127.0.0.1:2053/api/search?lastfm_username={lastfm_username}&track_name={trackenc}&artist_name={artistenc}"
                                    headers = {"X-API-Key": f"{API_KEY}"}

                                    async with self.session.get(api_url, headers=headers) as spotify_response:
                                        if spotify_response.status == 200:
                                            spotify_data = await spotify_response.json()
                                            song_url = spotify_data.get('spotify_link')
                                            description += f"\n-# <:lastfm:1275185763574874134> Last listened to [**{song_name}**]({song_url}) by [{artist_name}]({artist_url})"
                                        else:
                                            description += f"\n-# <:lastfm:1275185763574874134> Last listened to **{song_name}** by {artist_name}"

                                query = f"{song_name} {artist_name}"
                                headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                                }
                                async with self.session.get(f"https://api.stats.fm/api/v1/search/elastic?query={query}%20{artist_name}&type=track&limit=1", headers=headers) as response:
                                    if response.status == 200:
                                        data = await response.json()
                                        tracks = data.get("items", {}).get("tracks", [])

                                        if tracks:
                                            genius_title = song_name.lower().strip()
                                            genius_artist = artist_name.lower().strip()

                                            for track in tracks:
                                                track_title = track.get("name", "").lower().strip()
                                                track_artists = [artist.get("name", "").lower().strip() for artist in track.get("artists", [])]
                                                spotify_preview = track.get("spotifyPreview")
                                                apple_preview = track.get("appleMusicPreview")

                                                title_match = genius_title in track_title or track_title in genius_title
                                                artist_match = any(genius_artist in artist_name or artist_name in genius_artist for artist_name in track_artists)

                                                if title_match and artist_match and (spotify_preview or apple_preview):
                                                    has_audio = True
                                                    break
                except Exception as e:
                    print(e)
                    pass

            limited_key = f"user:{interaction.user.id}:limited"
            untrusted_key = f"user:{interaction.user.id}:untrusted"
            limited = await self.redis.exists(limited_key)
            untrusted = await self.redis.exists(untrusted_key)

            if not untrusted:
                last_seen_info = await self.get_last_seen_info(user, limited)
                if last_seen_info:
                    description += last_seen_info

            if not limited and user_data and "bio" in user_data and user_data["bio"]:
                description += f"\n{user_data['bio']}"
                
            description += f"\n\n-# **Created on** <t:{int(user.created_at.timestamp())}:f> (<t:{int(user.created_at.timestamp())}:R>)"

            embed = Embed(
                description=description,
                color=embed_color
            )

            if user_data and 'clan' in user_data and user_data.get('clan') and isinstance(user_data['clan'], dict):
                clan = user_data['clan']
                clan_tag = clan.get('tag')
                clan_badge = clan.get('badge')
                identity_guild_id = clan.get('identity_guild_id')
                if clan_tag and clan_badge and identity_guild_id:
                    clan_badge_url = f"https://cdn.discordapp.com/clan-badges/{identity_guild_id}/{clan_badge}.png?size=16"
                    embed.set_author(name=f"{clan_tag}", icon_url=clan_badge_url)
                    embed.description = f"**{user.display_name} (@{user.name})**\n{description}"
                else:
                    embed.set_author(name=f"{user.display_name} (@{user.name})", icon_url=user.display_avatar.url)
                    embed.description = description
            else:
                embed.set_author(name=f"{user.display_name} (@{user.name})", icon_url=user.display_avatar.url)
                embed.description = description

            embed.set_thumbnail(url=user.display_avatar.url)

            banner_url = full_user.banner.url if full_user.banner else None
            if banner_url:
                embed.set_image(url=banner_url)
            
            embed.set_footer(text=f"{footer} • {user.id}", icon_url="https://csyn.me/assets/heist.png?c") 

            view = View(timeout=300)

            async def on_timeout():
                for item in view.children:
                    if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                        item.disabled = True
                try:
                    await interaction.edit_original_response(view=view)
                except discord.NotFound:
                    pass

            view.on_timeout = on_timeout

            profile_button = Button(label="View Profile", emoji=discord.PartialEmoji.from_str("<:person:1295440206706511995>"), style=discord.ButtonStyle.link, url=f"discord://-/users/{user.id}")
            view.add_item(profile_button)

            avatar_history_button = Button(
                label="Avatar History",
                emoji=discord.PartialEmoji.from_str("<:unlock:1295440365226037340>"),
                style=discord.ButtonStyle.secondary,
                custom_id=f"avatar_history_{user.id}_{interaction.user.id}"
            )
            view.add_item(avatar_history_button)

            if has_audio and song_name and artist_name:
                audio_button = Button(
                    emoji=discord.PartialEmoji.from_str("<:audio:1345517095101923439>"),
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"audio_{user.id}_{interaction.user.id}"
                )

                async def audio_button_callback(button_interaction: discord.Interaction):

                    await button_interaction.response.defer(ephemeral=True)
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    }
                    query = f"{song_name} {artist_name}"
                    async with self.session.get(f"https://api.stats.fm/api/v1/search/elastic?query={query}%20{artist_name}&type=track&limit=1", headers=headers) as response:
                        if response.status != 200:
                            await button_interaction.followup.send("Failed to fetch track data.", ephemeral=True)
                            return
                        
                        data = await response.json()
                        tracks = data.get("items", {}).get("tracks", [])

                        if not tracks:
                            await button_interaction.followup.send("No tracks found.", ephemeral=True)
                            return

                        genius_title = song_name.lower().strip()
                        genius_artist = artist_name.lower().strip()

                        best_match = None
                        for track in tracks:
                            track_title = track.get("name", "").lower().strip()
                            track_artists = [artist.get("name", "").lower().strip() for artist in track.get("artists", [])]
                            spotify_preview = track.get("spotifyPreview")
                            apple_preview = track.get("appleMusicPreview")

                            title_match = genius_title in track_title or track_title in genius_title
                            artist_match = any(genius_artist in artist_name or artist_name in genius_artist for artist_name in track_artists)

                            if title_match and artist_match:
                                if spotify_preview or apple_preview:
                                    best_match = track
                                    break
                                else:
                                    best_match = best_match or track

                        if not best_match:
                            await button_interaction.followup.send("No matching track found.", ephemeral=True)
                            return

                        preview_url = best_match.get("spotifyPreview") or best_match.get("appleMusicPreview")

                        if preview_url:
                            async with self.session.get(preview_url) as audio_response:
                                if audio_response.status == 200:
                                    audio_data = await audio_response.read()

                                    try:
                                        def process_audio(data):
                                            audio = AudioSegment.from_file(io.BytesIO(data))
                                            opus_io = io.BytesIO()
                                            audio.export(opus_io, format="opus", parameters=["-b:a", "128k", "-application", "voip"])
                                            opus_io.seek(0)
                                            return opus_io

                                        opus_io = await asyncio.to_thread(process_audio, audio_data)
                                        
                                        audio_file = discord.File(opus_io, filename="audio.opus")
                                        
                                        await interaction.followup.send(file=audio_file, voice_message=True, ephemeral=True)
                                        
                                    except Exception as e:
                                        if 'opus_io' in locals():
                                            opus_io.close()
                                        await interaction.followup.send(f"Error converting audio: {str(e)}", ephemeral=True)
                                else:
                                    await interaction.followup.send("Failed to fetch audio preview.", ephemeral=True)
                        else:
                            await interaction.followup.send("No audio preview available.", ephemeral=True)

                audio_button.callback = audio_button_callback
                view.add_item(audio_button)

            guilds_button = None
            if is_owner_self:
                guilds_button = Button(
                    label="Guilds",
                    emoji=discord.PartialEmoji.from_str("<:group:1343755056536621066>"),
                    style=discord.ButtonStyle.green,
                    custom_id=f"guilds_{user.id}_{interaction.user.id}"
                )
                if guilds_button:
                    view.add_item(guilds_button)

            await interaction.followup.send(embed=embed, view=view)

            guilds_button_callback = None
            if guilds_button:
                async def guilds_button_callback(button_interaction: discord.Interaction):
                    if button_interaction.user.id != interaction.user.id:
                        await button_interaction.response.send_message("You cannot use this button.", ephemeral=True)
                        return

                    await button_interaction.response.defer(thinking=True, ephemeral=True)

                    target_user = await interaction.client.fetch_user(user.id)

                    processing_embed = await cembed(interaction, description=f"<a:loading:1269644867047260283> {interaction.user.mention}: processing..")
                    processing = await button_interaction.followup.send(embed=processing_embed)

                    headers = {"X-API-Key": API_KEY}
                    guilds_info = []
                    guild_ids = set()

                    retries = 0
                    max_retries = 5
                    backoff_factor = 2
                    timeout = aiohttp.ClientTimeout(total=2)

                    while retries < max_retries:
                        try:
                            async with self.session.get(f"http://127.0.0.1:8002/mutualguilds/{user.id}", headers=headers, timeout=timeout) as resp:
                                if resp.status == 200:
                                    guilds_data = await resp.json()
                                    for guild_data in guilds_data:
                                        guild_id = guild_data.get("id")
                                        if guild_id not in guild_ids:
                                            guild_ids.add(guild_id)
                                            guilds_info.append(guild_data)

                                    if len(guilds_info) == 0:
                                        embed = await cembed(
                                            interaction,
                                            title=f"{target_user.name}'s guilds shared with Heist (0)",
                                            description="-# No guilds shared with user."
                                        )
                                        embed.set_footer(text=footer, icon_url="https://csyn.me/assets/heist.png?c")
                                        embed.set_thumbnail(url=target_user.avatar.url if target_user.avatar else target_user.default_avatar.url)
                                        await processing.edit(embed=embed)
                                        return

                                    total_pages = (len(guilds_info) + 4) // 5
                                    current_page = 0

                                    embed = await cembed(
                                        interaction,
                                        title=f"{target_user.name}'s guilds shared with Heist ({len(guilds_info)})",
                                        url=f"https://discord.com/users/{target_user.id}"
                                    )

                                    embed.description = ""

                                    start_idx = current_page * 5
                                    end_idx = min(start_idx + 5, len(guilds_info))

                                    for guild in guilds_info[start_idx:end_idx]:
                                        guild_name = guild.get("name", "Unknown Guild")
                                        vanity = guild.get("vanity_url")
                                        vanity_text = f"`discord.gg/{vanity}`" if vanity else "`no vanity found`"
                                        embed.description += f"**{guild_name}**\n-# {vanity_text}\n\n"

                                    embed.set_author(
                                        name=f"{target_user.name}",
                                        icon_url=target_user.avatar.url if target_user.avatar else target_user.default_avatar.url
                                    )
                                    embed.set_thumbnail(url=target_user.avatar.url if target_user.avatar else target_user.default_avatar.url)
                                    embed.set_footer(text=f"Page {current_page + 1}/{total_pages} • {footer}", icon_url="https://csyn.me/assets/heist.png?c")

                                    view = discord.ui.View()

                                    previous_button = discord.ui.Button(
                                        emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), 
                                        style=discord.ButtonStyle.primary, 
                                        disabled=True,
                                        custom_id="previous"
                                    )
                                    view.add_item(previous_button)

                                    next_button = discord.ui.Button(
                                        emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), 
                                        style=discord.ButtonStyle.primary, 
                                        disabled=total_pages <= 1,
                                        custom_id="next"
                                    )
                                    view.add_item(next_button)

                                    skip_button = discord.ui.Button(
                                        emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"),
                                        style=discord.ButtonStyle.secondary,
                                        custom_id="skip"
                                    )
                                    view.add_item(skip_button)

                                    json_button = discord.ui.Button(
                                        emoji=discord.PartialEmoji.from_str("<:json:1292867766755524689>"),
                                        style=discord.ButtonStyle.secondary,
                                        custom_id="json"
                                    )
                                    view.add_item(json_button)

                                    delete_button = discord.ui.Button(
                                        emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"),
                                        style=discord.ButtonStyle.danger,
                                        custom_id="delete"
                                    )
                                    view.add_item(delete_button)

                                    async def button_callback(button_interaction: discord.Interaction):
                                        nonlocal current_page
                                        if button_interaction.user.id != interaction.user.id:
                                            await button_interaction.response.send_message("You cannot use these buttons.", ephemeral=True)
                                            return

                                        if button_interaction.data["custom_id"] == "delete":
                                            await button_interaction.response.defer()
                                            await button_interaction.delete_original_response()
                                            return

                                        if button_interaction.data["custom_id"] == "skip":
                                            class GoToPageModal(discord.ui.Modal, title="Go to Page"):
                                                page_number = discord.ui.TextInput(label="Navigate to page", placeholder=f"Enter a page number (1-{total_pages})", min_length=1, max_length=len(str(total_pages)))

                                                async def on_submit(self, interaction: discord.Interaction):
                                                    try:
                                                        page = int(self.page_number.value) - 1
                                                        if page < 0 or page >= total_pages:
                                                            raise ValueError
                                                        nonlocal current_page
                                                        current_page = page
                                                        await update_message()
                                                        await interaction.response.defer()
                                                    except ValueError:
                                                        await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

                                            modal = GoToPageModal()
                                            await button_interaction.response.send_modal(modal)
                                            return

                                        if button_interaction.data["custom_id"] == "previous":
                                            current_page = max(0, current_page - 1)
                                        elif button_interaction.data["custom_id"] == "next":
                                            current_page = min(total_pages - 1, current_page + 1)

                                        await button_interaction.response.defer()
                                        await update_message()

                                    async def update_message():
                                        embed.description = ""
                                        start_idx = current_page * 5
                                        end_idx = min(start_idx + 5, len(guilds_info))

                                        for guild in guilds_info[start_idx:end_idx]:
                                            guild_name = guild.get("name", "Unknown Guild")
                                            vanity = guild.get("vanity_url")
                                            vanity_text = f"`discord.gg/{vanity}`" if vanity else "`no vanity found`"
                                            embed.description += f"**{guild_name}**\n-# {vanity_text}\n\n"

                                        embed.set_footer(text=f"Page {current_page + 1}/{total_pages} • {footer}", icon_url="https://csyn.me/assets/heist.png?c")

                                        view.children[0].disabled = current_page == 0
                                        view.children[1].disabled = current_page == total_pages - 1

                                        await processing.edit(embed=embed, view=view)

                                    async def json_button_callback(button_interaction: discord.Interaction):
                                        formatjson = json.dumps(guilds_info, indent=4)
                                        file = io.BytesIO(formatjson.encode())
                                        await button_interaction.response.send_message(file=discord.File(file, filename="guilds.json"), ephemeral=True)

                                    for button in view.children[:-2]:
                                        button.callback = button_callback

                                    json_button.callback = json_button_callback
                                    delete_button.callback = button_callback

                                    await processing.edit(embed=embed, view=view)
                                    break

                        except Exception as e:
                            print(f"Error occurred: {e}. Retrying...")
                            retries += 1
                            await asyncio.sleep(backoff_factor * retries)
                    else:
                        await button_interaction.followup.send("An error occurred while fetching guilds after multiple attempts.", ephemeral=True)

                guilds_button.callback = guilds_button_callback

            async def avatar_history_button_callback(button_interaction: discord.Interaction):
                await self.handle_avatar_history(button_interaction)

            avatar_history_button.callback = avatar_history_button_callback

    async def handle_avatar_history(self, interaction: discord.Interaction):
        custom_id = interaction.data['custom_id']
        parts = custom_id.split('_')
        target_user_id, author_id = parts[2], parts[3]
        target_user = await interaction.client.fetch_user(int(target_user_id))
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        url = f"https://api.lure.rocks/avatars/{target_user.id}"
        headers = {"X-API-Key": LURE_KEY}
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    response_text = await response.text()
                    await interaction.followup.send("No avatar history found for user.", ephemeral=True)
                    return
                    
                avatar_data = await response.json()

                avatar_data = await response.json()
                if not avatar_data or not avatar_data.get('avatars'):
                    await interaction.followup.send("No avatar history found for user.", ephemeral=True)
                    return
                    
                view = AvatarHistoryView(interaction, avatar_data, target_user, interaction.user)
                embed = await view.create_embed()
                view.update_buttons()
                await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await error_handler(interaction, e)

    def format_timestamp(self, timestamp: str) -> str:
        tz = ZoneInfo('Europe/Bucharest')
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        dt = dt.astimezone(tz)
        offset = dt.strftime('%z')
        offset_formatted = f"GMT{offset[:3]}:{offset[3:]}"
        return dt.strftime(f'%B %d, %I:%M %p {offset_formatted}')

    @discordg.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user to get avatar history of, leave empty to get your own.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def avatarhistory(self, interaction: discord.Interaction, user: discord.User = None):
        """View the avatar history of a Discord user."""
        user = user or interaction.user
        interaction_user = interaction.user

        url = f"https://api.lure.rocks/avatars/{user.id}"
        headers = {"X-API-Key": LURE_KEY}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        await interaction.followup.send("No avatar history found for user.", ephemeral=True)
                        return

                    avatar_data = await response.json()
                    if not avatar_data or not avatar_data.get('avatars'):
                        await interaction.followup.send("No avatar history found for user.", ephemeral=True)
                        return

                    view = AvatarHistoryView(interaction, avatar_data, user, interaction_user)
                    embed = await view.create_embed()
                    view.update_buttons()

                    await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            await error_handler(interaction, e)

    @discordg.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.check(permissions.is_donor)
    async def randomserver(self, interaction: discord.Interaction):
        """✨ Get a random Discord invite."""
        try:
            async with aiofiles.open("vanities.txt", "r") as file:
                content = await file.read()
                vanities = content.splitlines()
            
            if not vanities:
                return await interaction.response.send_message("No vanity servers found.")
            
            random_invite = random.choice(vanities)
            
            if interaction.guild:
                await interaction.response.send_message(random_invite, ephemeral=True)
            else:
                await interaction.response.send_message(random_invite)
        except Exception as e:
            await error_handler(interaction, e)

async def setup(client):
    await client.add_cog(Discord(client))
