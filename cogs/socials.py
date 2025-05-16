import discord
from discord import app_commands, Interaction, InteractionType, Embed, ButtonStyle, ui
from discord.ui import Button, View
from discord.ext import commands, tasks
import aiohttp, asyncio, datetime, time, json, re, io, random, os, base64, subprocess, tempfile, math
from pydub import AudioSegment
from bs4 import BeautifulSoup
import urllib
from urllib.parse import urlparse, quote
from PIL import Image, ImageDraw, ImageFont
from utils.db import check_donor, get_db_connection, redis_client
from utils.error import error_handler
from utils.embed import cembed
from utils.cd import cooldown
from utils import default, permissions
from dotenv import dotenv_values
from typing import Optional, Dict
import asyncpg
import calendar
from collections import Counter
from pytube import Search
import redis.asyncio as redis
import asyncpraw

footer = "heist.lol"
config = dotenv_values(".env")
API_KEY = config["HEIST_API_KEY"]
STEAM_KEY = config["STEAM_API_KEY"]
LASTFM_KEY = config["LASTFM_API_KEY"]
DATAWAVE_KEY = config["DATAWAVE_API_KEY"]
ROSINT_KEY = config["ROSINT_API_KEY"]
REDDIT_ID = config["REDDIT_CLIENT_ID"]
REDDIT_SECRET = config["REDDIT_SECRET"]
OSU_KEY = config["OSU_API_KEY"]
GUNSLOL_KEY = config["GUNSLOL_API_KEY"]
AMMOLOL_KEY = config["AMMOLOL_API_KEY"]
EMOGIRLS_KEY = config["EMOGIRLS_API_KEY"]
ROBLOX_COOKIE = config["ROBLOX_COOKIE"]

reddit_client = asyncpraw.Reddit(
    client_id=REDDIT_ID,
    client_secret=REDDIT_SECRET,
    user_agent="HeistBot/0.1 by Cosmin"
)

class Socials(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.redis = redis_client
        # self.watched_users: Dict[str, Dict] = {}
        # self.check_presence_task.start()
        self.ctx_discord2roblox2 = app_commands.ContextMenu(
            name='✨ Lookup Roblox',
            callback=self.discord2roblox2,
        )
        self.client.tree.add_command(self.ctx_discord2roblox2)
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        self.client.tree.remove_command(self.ctx_discord2roblox2.name, type=self.ctx_discord2roblox2.type)
        await self.session.close()
        # self.check_presence_task.cancel()

    snapchat = app_commands.Group(
        name="snapchat", 
        description="Snapchat related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    youtube = app_commands.Group(
        name="youtube", 
        description="YouTube related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    github = app_commands.Group(
        name="github", 
        description="GitHub related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    instagram = app_commands.Group(
        name="instagram", 
        description="Instagram related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    telegram = app_commands.Group(
        name="telegram", 
        description="Telegram related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    osu = app_commands.Group(
        name="osu", 
        description="osu! related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    tiktok = app_commands.Group(
        name="tiktok", 
        description="TikTok related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    x = app_commands.Group(
        name="x", 
        description="X related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    reddit = app_commands.Group(
        name="reddit", 
        description="Reddit related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    medaltv = app_commands.Group(
        name="medaltv", 
        description="Medal.tv related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    pinterest = app_commands.Group(
        name="pinterest", 
        description="Pinterest related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    pinterestsearch = app_commands.Group(
        name="search", 
        description="Pinterest search related commands",
        parent=pinterest
    )

    roblox = app_commands.Group(
        name="roblox", 
        description="Roblox related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    robloxsearch = app_commands.Group(
        name="search", 
        description="Roblox search related commands",
        parent=roblox
    )

    # watch = app_commands.Group(
    #     name="watch",
    #     description="Watch related Roblox commands",
    #     parent=roblox 
    # )

    minecraft = app_commands.Group(
        name="minecraft", 
        description="Minecraft related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    fortnite = app_commands.Group(
        name="fortnite", 
        description="Fortnite related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    bio = app_commands.Group(
        name="bio", 
        description="Biolink related commands",
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    )

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.check(permissions.is_donor)
    async def discord2roblox2(self, interaction: discord.Interaction, user: discord.User) -> None:
        await interaction.response.defer()
        await self.d2r(interaction, user)

    @instagram.command()
    @app_commands.describe(username="The Instagram username to look up.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def user(self, interaction: discord.Interaction, username: str):
        """Get Instagram user information."""
        def format_number(number_str):
            try:
                number = float(number_str.replace('M', '').replace('K', ''))
                if 'M' in number_str:
                    return f"{number:.1f}m"
                elif 'K' in number_str:
                    return f"{number:.1f}k"
                return number_str
            except:
                return number_str

        try:
            profile = await self.client.socials.get_instagram_user(username)
            
            bio = profile.bio or 'No bio available'
            bio = re.sub(r'@(\w+)', r'[@\1](https://www.instagram.com/\1)', bio)
            followers = format_number(profile.followers)
            following = format_number(profile.following)
            posts = format_number(profile.posts)

            title = f"{profile.username}"
            if profile.verified:
                title += " <:verified_light_blue:1362170749271408911>"

            embed = await cembed(
                interaction,
                title=title,
                url=profile.url,
                description=f"{bio}"
            )

            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            embed.add_field(name='Followers', value=f"**`{followers}`**", inline=True)
            embed.add_field(name='Following', value=f"**`{following}`**", inline=True)
            embed.add_field(name='Posts', value=f"**`{posts}`**", inline=True)
            embed.set_footer(text="instagram.com", icon_url="https://git.cursi.ng/instagram_logo.png?e")

            if profile.avatar_url:
                embed.set_thumbnail(url=profile.avatar_url)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            if "Profile data not found" in str(e):
                await interaction.followup.send("User does not exist.")
            else:
                await error_handler(interaction, e)

    @snapchat.command()
    @app_commands.describe(username="The Snapchat username to look up.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def user(self, interaction: Interaction, username: str):
        """Get Snapchat user information."""
        user_info = await self.get_snapchat_info(username)

        if not user_info:
            await interaction.followup.send("User does not exist.")
            return

        title = f"{user_info['displayName']} (@{user_info['username']})"
        if user_info.get('badge') == 1:
            title += " <:scstar:1294423745997307979>"

        if user_info['type'] == 'publicProfileInfo':
            subscriber_count = format(int(user_info.get('subscribers', 0)), ',') if user_info.get('subscribers') else "0"
            description = user_info.get('bio', '')
            if user_info.get('website'):
                website_url = user_info['website']
                description += f"\n-# [{website_url.replace('https://', '').replace('http://', '')}]({website_url})"
            description += f"\n-# **`{subscriber_count}`** subscribers."

            embed = await cembed(
                interaction,
                title=title,
                description=description,
                url=f"https://www.snapchat.com/add/{username}"
            )
            if user_info.get('profile_picture_url'):
                embed.set_thumbnail(url=user_info['profile_picture_url'])
        else:
            embed = await cembed(
                interaction,
                title=title,
                url=f"https://www.snapchat.com/add/{username}"
            )
            embed.add_field(name="Username", value=user_info['username'], inline=True)
            embed.add_field(name="Display Name", value=user_info.get('displayName', 'N/A'), inline=True)
            if user_info.get('bitmoji_url'):
                embed.set_image(url=user_info['bitmoji_url'])
            if user_info.get('snapcode_url'):
                embed.set_thumbnail(url=user_info['snapcode_url'].replace("&type=SVG", "&type=PNG"))

        embed.set_footer(text="snapchat.com", icon_url="https://git.cursi.ng/snapchat_logo.png")
        await interaction.followup.send(embed=embed)

    async def get_snapchat_info(self, username: str) -> dict:
        url = f"https://www.snapchat.com/add/{username}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        
        async with self.session.get(url, headers=headers) as response:
            if response.status != 200:
                return None
            
            text = await response.text()
            
            def parse_html(html_content):
                soup = BeautifulSoup(html_content, 'html.parser')
                script_tag = soup.find('script', type='application/json')
                if not script_tag:
                    return None
                return script_tag.string
            
            script_content = await asyncio.to_thread(parse_html, text)
            if not script_content:
                return None

            try:
                data = json.loads(script_content)
                user_profile = data['props']['pageProps']['userProfile']
                
                if user_profile['$case'] == 'userInfo':
                    user_info = user_profile.get('userInfo', {})
                    return {
                        'type': 'userInfo',
                        'username': user_info.get('username'),
                        'displayName': user_info.get('displayName'),
                        'snapcode_url': user_info.get('snapcodeImageUrl'),
                        'bitmoji_url': user_info.get('bitmoji3d', {}).get('avatarImage', {}).get('url', None)
                    }
                elif user_profile['$case'] == 'publicProfileInfo':
                    public_profile_info = user_profile.get('publicProfileInfo', {})
                    return {
                        'type': 'publicProfileInfo',
                        'username': public_profile_info.get('username'),
                        'displayName': public_profile_info.get('title'),
                        'snapcode_url': public_profile_info.get('snapcodeImageUrl'),
                        'profile_picture_url': public_profile_info.get('profilePictureUrl'),
                        'bio': public_profile_info.get('bio'),
                        'website': public_profile_info.get('websiteUrl'),
                        'subscribers': public_profile_info.get('subscriberCount'),
                        'badge': public_profile_info.get('badge', 0)
                    }
            except (KeyError, json.JSONDecodeError) as e:
                print(f"Error parsing Snapchat data: {e}")
                return None

    @fortnite.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def shop(self, interaction: discord.Interaction):
        """View today's Fortnite shop."""

        class FortniteShopHandler:
            def __init__(self, session: aiohttp.ClientSession):
                self.session = session
                self.last_updated = 0
                self.shop_path = 'structure/fortnite_shop.png'
                self.api_key = 'eb924f7c-dffb-470a-96c5-180b39bd0f0b'
                os.makedirs('structure', exist_ok=True)

            async def fetch_shop_data(self):
                async with self.session.get('https://fnbr.co/api/shop', headers={'x-api-key': self.api_key}) as response:
                    if response.status != 200:
                        return None
                    return await response.json()

            async def generate_shop_image(self):
                data = await self.fetch_shop_data()
                if not data:
                    return False

                all_items = data['data']['featured'] + data['data']['daily']
                items_with_gallery = [item for item in all_items if item['images']['icon']]

                items_per_row = 15
                item_width = 200
                item_height = 350
                canvas_width = items_per_row * item_width
                canvas_height = ((len(items_with_gallery) - 1) // items_per_row + 1) * item_height

                image = Image.new('RGB', (canvas_width, canvas_height), color='#2C2F33')
                draw = ImageDraw.Draw(image)

                font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
                font_price = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)

                async def process_item(item, x, y):
                    async with self.session.get(item['images']['icon']) as resp:
                        if resp.status == 200:
                            item_data = await resp.read()
                            item_image = Image.open(io.BytesIO(item_data))
                            if item_image.mode in ('RGBA', 'LA') or (item_image.mode == 'P' and 'transparency' in item_image.info):
                                item_image = item_image.convert('RGBA')
                            else:
                                item_image = item_image.convert('RGB')
                            item_image = item_image.resize((item_width, item_width))
                            image.paste(item_image, (x, y), item_image if item_image.mode == 'RGBA' else None)
                            draw.text((x + 10, y + 220), item['name'], font=font_title, fill=(255, 255, 255, 255))
                            draw.text((x + 10, y + 240), f"{item['price']} V-Bucks", font=font_price, fill=(255, 255, 255, 255))

                tasks = [process_item(item, (i % items_per_row) * item_width, (i // items_per_row) * item_height) for i, item in enumerate(items_with_gallery)]
                await asyncio.gather(*tasks)

                image.save(self.shop_path, 'PNG')
                return True

            async def get_shop_image(self):
                current_time = time.time()
                if current_time - self.last_updated > 3600 or not os.path.exists(self.shop_path):
                    success = await self.generate_shop_image()
                    if success:
                        self.last_updated = current_time
                return self.shop_path if os.path.exists(self.shop_path) else None

        try:
            if not hasattr(self, 'fortnite_shop_handler'):
                self.fortnite_shop_handler = FortniteShopHandler(self.session)

            shop_path = await self.fortnite_shop_handler.get_shop_image()
            if shop_path:
                with open(shop_path, 'rb') as f:
                    await interaction.followup.send(file=discord.File(f, filename="fortnite_shop.png"))
            else:
                await interaction.followup.send("Unable to fetch shop data at this time.")
        except Exception as e:
            await error_handler(interaction, e)

    # @robloxsearch.command()
    # @app_commands.allowed_installs(guilds=True, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    # @app_commands.describe(query="The game to search for.")
    # @app_commands.check(permissions.is_blacklisted)
    # @permissions.requires_perms(embed_links=True)
    # async def game(self, interaction: discord.Interaction, query: str):
    #     "Search for a Roblox game."

    #     api_url = f"http://localhost:1118/socials/roblox/gamesearch?query={query}"
    #     headers = {"X-API-Key": API_KEY}

    #     async with self.session.get(api_url, headers=headers) as response:
    #         if response.status != 200:
    #             await interaction.followup.send("Failed to fetch data from the API.")
    #             return

    #         data = await response.json()
    #         results = data.get("results", [])
    #         if not results:
    #             await interaction.followup.send("No results found.")
    #             return

    #         class RobloxSearchView(ui.View):
    #             def __init__(self, interaction: discord.Interaction, results: list):
    #                 super().__init__(timeout=240)
    #                 self.interaction = interaction
    #                 self.results = results
    #                 self.current_page = 0
    #                 self.update_buttons()

    #             def update_buttons(self):
    #                 self.previous_button.disabled = self.current_page == 0
    #                 self.next_button.disabled = self.current_page == len(self.results) - 1

    #             async def update_embed(self):
    #                 result = self.results[self.current_page]
    #                 game_name = result.get("name", "Unknown Game")
    #                 game_url = result.get("game_url", "")
    #                 cover_url = result.get("cover_url", "")
    #                 creator = result.get("creator", "Unknown")
    #                 votes = result.get("votes", "N/A")
    #                 playing = result.get("playing", "N/A")

    #                 embed = await cembed(
    #                     self.interaction,
    #                     title=game_name,
    #                     url=game_url
    #                 )
    #                 embed.set_author(name=self.interaction.user.display_name, icon_url=self.interaction.user.avatar.url)
    #                 embed.set_thumbnail(url=cover_url)

    #                 description = ""
    #                 if creator != "Unknown":
    #                     description += f"> **{creator}**\n"
    #                 if votes != "N/A":
    #                     thumbs_up = "<:thumbs_up:1324814959296643103>"
    #                     thumbs_down = "<:thumbs_down:1324814966712434739>"
    #                     description += f"## {votes} {thumbs_up} {100 - int(votes.strip('%'))}% {thumbs_down}\n"

    #                 description += f"-# <:person:1295440206706511995> **{playing}** online players"

    #                 embed.description = description
    #                 embed.set_footer(text=f"Result {self.current_page + 1}/{len(self.results)} • roblox.com", icon_url="https://git.cursi.ng/roblox_logo.png?v2")

    #                 await self.interaction.edit_original_response(embed=embed, view=self)

    #             @ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary, custom_id="robloxleft")
    #             async def previous_button(self, interaction: discord.Interaction, button: ui.Button):
    #                 if interaction.user.id != self.interaction.user.id:
    #                     await interaction.response.send_message("You cannot interact with someone else's message.", ephemeral=True)
    #                     return

    #                 if self.current_page > 0:
    #                     self.current_page -= 1
    #                     self.update_buttons()
    #                     await self.update_embed()
    #                     await interaction.response.defer()

    #             @ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary, custom_id="robloxright")
    #             async def next_button(self, interaction: discord.Interaction, button: ui.Button):
    #                 if interaction.user.id != self.interaction.user.id:
    #                     await interaction.response.send_message("You cannot interact with someone else's message.", ephemeral=True)
    #                     return

    #                 if self.current_page < len(self.results) - 1:
    #                     self.current_page += 1
    #                     self.update_buttons()
    #                     await self.update_embed()
    #                     await interaction.response.defer()

    #             @ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary, custom_id="robloxsort")
    #             async def sort_button(self, interaction: discord.Interaction, button: ui.Button):
    #                 if interaction.user.id != self.interaction.user.id:
    #                     await interaction.response.send_message("You cannot interact with someone else's message.", ephemeral=True)
    #                     return

    #                 class GoToPageModal(ui.Modal, title="Go to Page"):
    #                     def __init__(self, view):
    #                         super().__init__()
    #                         self.view = view
    #                         self.page_number = ui.TextInput(
    #                             label="Navigate to page",
    #                             placeholder=f"Enter a page number (1-{len(self.view.results)})",
    #                             min_length=1,
    #                             max_length=len(str(len(self.view.results)))
    #                         )
    #                         self.add_item(self.page_number)

    #                     async def on_submit(self, interaction: discord.Interaction):
    #                         try:
    #                             page = int(self.page_number.value) - 1
    #                             if page < 0 or page >= len(self.view.results):
    #                                 raise ValueError
    #                             self.view.current_page = page
    #                             self.view.update_buttons()
    #                             await self.view.update_embed()
    #                             await interaction.response.defer()
    #                         except ValueError:
    #                             await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

    #                 modal = GoToPageModal(self)
    #                 await interaction.response.send_modal(modal)

    #             @ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger, custom_id="robloxdelete")
    #             async def delete_button(self, interaction: discord.Interaction, button: ui.Button):
    #                 if interaction.user.id != self.interaction.user.id:
    #                     await interaction.response.send_message("You cannot interact with someone else's message.", ephemeral=True)
    #                     return

    #                 await interaction.response.defer()
    #                 await interaction.delete_original_response()

    #             async def on_timeout(self):
    #                 for item in view.children:
    #                     if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
    #                         item.disabled = True

    #                 try:
    #                     await interaction.edit_original_response(view=view)
    #                 except discord.NotFound:
    #                     pass

    #         view = RobloxSearchView(interaction, results)
    #         await view.update_embed()

    @roblox.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.describe(username="The Roblox username to look up.")
    @permissions.requires_perms(embed_links=True)
    async def user(self, interaction: Interaction, username: str):
        """Get Roblox user information."""
        async def truncate_text(text: str, max_length: int = 500) -> str:
            cleaned_text = re.sub(r'\n{4,}', '\n\n\n', text)
            return cleaned_text[:max_length] + '...' if len(cleaned_text) > max_length else cleaned_text

        async def format_number(number):
            if number is None: return "0"
            if number >= 1_000_000_000: return f"{number/1_000_000_000:.1f}B"
            elif number >= 1_000_000: return f"{number/1_000_000:.1f}M"
            elif number >= 1_000: return f"{number/1_000:.1f}K"
            return str(number)
            
        async def get_count(session, url):
            try:
                async with session.get(url, headers={'Cookie': ROBLOX_COOKIE}) as response:
                    if response.status == 200:
                        return (await response.json()).get('count', 0)
                    elif response.status == 429:
                        return None
                    return 0
            except Exception:
                return 0

        async def fetch_rolimons(session, user_id):
            try:
                async with session.get(f'https://api.rolimons.com/players/v1/playerinfo/{user_id}') as response:
                    if response.status == 200:
                        return await response.json()
                    return {'value': 0, 'rap': 0, 'premium': False, 'stats_updated': None}
            except Exception:
                return {'value': 0, 'rap': 0, 'premium': False, 'stats_updated': None}

        async def get_user_place_visits(session, user_id):
            try:
                async with session.get(
                    f'https://games.roproxy.com/v2/users/{user_id}/games?accessFilter=Public&sortOrder=Asc',
                    headers={'Cookie': ROBLOX_COOKIE}
                ) as response:
                    if response.status == 200:
                        return sum(game.get('placeVisits', 0) for game in (await response.json()).get('data', []))
                    return 0
            except Exception:
                return 0

        try:
            async with self.session.post(
                'https://users.roproxy.com/v1/usernames/users',
                headers={'accept': 'application/json', 'Content-Type': 'application/json', 'Cookie': ROBLOX_COOKIE},
                json={'usernames': [username], 'excludeBannedUsers': False}
            ) as search_response:
                if search_response.status != 200:
                    await interaction.followup.send("User not found.", ephemeral=True)
                    return
                user_data = await search_response.json()

            if not user_data['data']:
                await interaction.followup.send("The user you looked up is non-existent.", ephemeral=True)
                return
                
            user_id = user_data['data'][0]['id']
            roblox_display_name = user_data['data'][0].get('displayName', username)
            is_banned = user_data['data'][0].get('isBanned', False)
            
            async def get_user_info():
                async with self.session.get(
                    f'https://users.roproxy.com/v1/users/{user_id}',
                    headers={'Cookie': ROBLOX_COOKIE}
                ) as info_response:
                    return await info_response.json() if info_response.status == 200 else {}

            async def get_premium_status():
                async with self.session.get(
                    f'https://premiumfeatures.roproxy.com/v1/users/{user_id}/validate-membership',
                    headers={'Cookie': ROBLOX_COOKIE}
                ) as premium_response:
                    return (await premium_response.text()).lower() == "true"

            async def get_thumbnail():
                async with self.session.get(
                    f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=420x420&format=Png",
                    headers={'Cookie': ROBLOX_COOKIE}
                ) as thumbnail_response:
                    if thumbnail_response.status == 200:
                        return (await thumbnail_response.json())['data'][0]['imageUrl']
                    return 'https://t0.rbxcdn.com/91d977e12525a5ed262cd4dc1c4fd52b?format=png'

            async def get_friends_count():
                cached = await redis_client.get(f"roblox:friends:{user_id}")
                if cached: return int(cached)
                count = await get_count(self.session, f'https://friends.roblox.com/v1/users/{user_id}/friends/count')
                if count is not None: await redis_client.set(f"roblox:friends:{user_id}", str(count), ex=300)
                return count or 0

            async def get_followers_count():
                cached = await redis_client.get(f"roblox:followers:{user_id}")
                if cached: return int(cached)
                count = await get_count(self.session, f'https://friends.roproxy.com/v1/users/{user_id}/followers/count')
                if count is not None: await redis_client.set(f"roblox:followers:{user_id}", str(count), ex=300)
                return count or 0

            async def get_following_count():
                cached = await redis_client.get(f"roblox:following:{user_id}")
                if cached: return int(cached)
                count = await get_count(self.session, f'https://friends.roproxy.com/v1/users/{user_id}/followings/count')
                if count is not None: await redis_client.set(f"roblox:following:{user_id}", str(count), ex=300)
                return count or 0

            async def get_presence():
                async with self.session.post(
                    'https://presence.roproxy.com/v1/presence/users',
                    headers={'Content-Type': 'application/json', 'Cookie': ROBLOX_COOKIE},
                    json={'userIds': [user_id]}
                ) as presence_response:
                    if presence_response.status == 200:
                        presence = (await presence_response.json())['userPresences'][0]
                        status = presence['userPresenceType']
                        last_online = presence.get('lastOnline')
                        last_online_unix = int(datetime.datetime.fromisoformat(last_online.replace('Z', '+00:00').timestamp())) if last_online else None
                        return status, last_online_unix
                    return 0, None

            async def check_verified_hat():
                async with self.session.get(
                    f'https://inventory.roproxy.com/v1/users/{user_id}/items/Asset/102611803',
                    headers={'Cookie': ROBLOX_COOKIE}
                ) as inventory_response:
                    inventory_public = inventory_response.status != 403
                    if inventory_response.status == 200:
                        return len((await inventory_response.json())['data']) > 0, inventory_public
                    return None, inventory_public

            async def get_profile_badges():
                async with self.session.get(
                    f'https://accountinformation.roproxy.com/v1/users/{user_id}/roblox-badges',
                    headers={'Cookie': ROBLOX_COOKIE}
                ) as profile_badges_response:
                    if profile_badges_response.status == 200:
                        return [badge['name'] for badge in await profile_badges_response.json()]
                    return []

            async def get_ropro_info():
                async with self.session.get(f'https://api.ropro.io/getUserInfoTest.php?userid={user_id}') as ropro_response:
                    if ropro_response.status == 200:
                        return (await ropro_response.json()).get('discord')
                    return None

            user_info, is_premium, thumbnail_url, friends_count, followers_count, following_count, (status, last_online_unix), (has_verified_hat, inventory_public), profile_badges, rolimons_data, ropro_discord, place_visits = await asyncio.gather(
                get_user_info(),
                get_premium_status(),
                get_thumbnail(),
                get_friends_count(),
                get_followers_count(),
                get_following_count(),
                get_presence(),
                check_verified_hat(),
                get_profile_badges(),
                fetch_rolimons(self.session, user_id),
                get_ropro_info(),
                get_user_place_visits(self.session, user_id)
            )

            created_unix = None
            if user_info.get('created'):
                try:
                    created_unix = int(datetime.datetime.fromisoformat(user_info['created'].replace('Z', '+00:00')).timestamp())
                except Exception:
                    pass

            if last_online_unix and created_unix and abs(last_online_unix - created_unix) <= 10:
                rolimons_last_online = rolimons_data.get('last_online')
                if rolimons_last_online:
                    last_online_unix = rolimons_last_online

            embed = await cembed(interaction)
            embed.set_author(name=f"{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
            embed.set_thumbnail(url=thumbnail_url)

            title = f"{roblox_display_name}"
            if is_banned: title += " (Banned)"
            if user_info.get('hasVerifiedBadge', False): title += " <:roverified:1343047217899896885>"
            if is_premium: title += " <:ropremium:1299803476506705920>"
            if 'Administrator' in profile_badges: title += " <:roadmin:1344495590834438195>"
            title += f" (@{user_info.get('name', username)})"
            embed.title = title
            embed.url = f"https://roblox.com/users/{user_id}/profile"

            embed.description = f"-# **{await format_number(friends_count)} Friends** | **{await format_number(followers_count)} Followers** | **{await format_number(following_count)} Following**"

            embed.add_field(name="ID", value=f"`{user_id}`", inline=True)
            embed.add_field(name="Verified", value="Hat" if has_verified_hat else "No" if has_verified_hat is not None else "Unknown", inline=True)
            embed.add_field(name="Inventory", value="Public" if inventory_public else "Private", inline=True)
            
            stats_updated = rolimons_data.get('stats_updated')
            embed.add_field(
                name="RAP",
                value=f"[{await format_number(rolimons_data['rap'])}](https://www.rolimons.com/player/{user_id})"
                    + (f"\n-# <t:{stats_updated}:d>" if stats_updated else ""),
                inline=True
            )
            embed.add_field(
                name="Value",
                value=f"[{await format_number(rolimons_data['value'])}](https://www.rolimons.com/player/{user_id})"
                    + (f"\n-# <t:{stats_updated}:d>" if stats_updated else ""),
                inline=True
            )
            embed.add_field(name="Visits", value=f"{await format_number(place_visits)}", inline=True)
            
            if created_unix:
                embed.add_field(name="Created", value=f"<t:{created_unix}:F>", inline=True)
            else:
                embed.add_field(name="Created", value="Unknown", inline=True)
            
            last_online_display = "Right now" if status in [1, 2, 3, 4] else f"<t:{last_online_unix}:R>" if last_online_unix else "Unknown"
            embed.add_field(name="Last Online", value=last_online_display, inline=True)
            
            badge_emojis = {
                "Homestead": "<:HomesteadBadge:1344516320523190273>",
                "Bricksmith": "<:BricksmithBadge:1344516271882113117>",
                "Combat Initiation": "<:CombatInitiationBadge:1344516287472074772>",
                "Veteran": "<:VeteranBadge:1344516347710799872>",
                "Warrior": "<:WarriorBadge:1344516351242534913>",
                "Friendship": "<:FriendshipBadge:1344516296380776530>",
                "Bloxxer": "<:BloxxerBadge:1344516227162443776>",
                "Inviter": "<:InviterBadge:1344516220594032670>",
                "Administrator": "<:AdministratorBadge:1344516214566686770>",
                "Official Model Maker": "<:OfficialModelMakerBadge:1344516334096220293>"
            }
            badges_display = " ".join([badge_emojis.get(badge, "") for badge in profile_badges])
            embed.add_field(name="Badges", value=badges_display if badges_display else "None", inline=True)

            if user_info.get('description'):
                embed.add_field(name="Description", value=await truncate_text(user_info['description']), inline=True)

            if ropro_discord:
                embed.description += f"\nDiscord (RoPro): `{ropro_discord}`"

            footer_icon = {1: "https://git.cursi.ng/roblox_online.png", 2: "https://git.cursi.ng/roblox_ingame.png", 3: "https://git.cursi.ng/roblox_studio.png", 4: "https://git.cursi.ng/roblox_invisible.png"}.get(status, "https://git.cursi.ng/roblox_offline.png")
            footer_text = {1: "Online", 2: "In Game", 3: "In Studio", 4: "Invisible"}.get(status, "Offline")
            embed.set_footer(text=f"{footer_text} • roblox.com", icon_url=footer_icon)

            view = ui.View()
            view.add_item(ui.Button(emoji="<:Roblox:1263205555065983098>", label="Profile", url=f"https://roblox.com/users/{user_id}/profile", style=ButtonStyle.link))
            view.add_item(ui.Button(emoji="<:Rolimons:1263205684921499699>", label="Rolimons", url=f"https://www.rolimons.com/player/{user_id}", style=ButtonStyle.link))

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            await error_handler(interaction, e)

    @minecraft.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.describe(username="The Minecraft username to look up.")
    async def user(self, interaction: discord.Interaction, username: str):
        """Get Minecraft user information."""
        search_url = f"https://laby.net/api/search/names/{username}"
        async with self.session.get(search_url) as resp:
            if resp.status != 200:
                await interaction.response.send_message(f"Failed to fetch data for `{username}`.", ephemeral=True)
                return
            data = await resp.json()
            if not data['results']:
                await interaction.response.send_message(f"No data found for `{username}`.", ephemeral=True)
                return
            
            player_info = data['results'][0]
            player_name = player_info['name']
            player_uuid = player_info['uuid']

        history_url = f"https://laby.net/api/search/get-previous-accounts/{username}"
        async with self.session.get(history_url) as resp:
            if resp.status != 200:
                await interaction.response.send_message(f"Failed to fetch username history for `{username}`.", ephemeral=True)
                return
            history_data = await resp.json()

        if not history_data['users']:
            await interaction.response.send_message(f"No username history found for `{username}`.", ephemeral=True)
            return

        history = history_data['users'][0]['history']
        history_list = []
        if history:
            for entry in history:
                name = entry['name']
                changed_at = entry['changed_at']
                formatted_change = f"**`{name}`**`({changed_at[:10] if changed_at else 'N/A'})`"
                history_list.append(formatted_change)
        else:
            history_list.append("Not available.")

        embed = await cembed(
            interaction,
            title=player_name,
            url=f"https://laby.net/@{player_name}",
        )
        embed.add_field(
            name="Username History",
            value=", ".join(history_list),
            inline=False
        )
        thumbnail_url = f"https://mineskin.eu/avatar/{player_name}"
        embed.set_thumbnail(url=thumbnail_url)
        embed.set_footer(text=footer, icon_url="https://git.cursi.ng/heist.png?c")
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @telegram.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="The Telegram username to look up.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True, attach_files=True)
    async def user(self, interaction: discord.Interaction, username: str): # idk if this works icl - Telegram client not authorized - might be because of ip auth
        """Get Telegram user information."""
        try:
            data = await self.client.socials.get_telegram_user(username)

            display_name = f"{data['first_name']} {data['last_name']}" if data['first_name'] and data['last_name'] else data['first_name']
            title = f"{display_name} (@{username})" if display_name else f"@{username}"
            if data['is_premium']:
                title += " <:teleprem:1345545700489953391>"

            description = ""
            if data['last_seen']:
                description += f"-# Last seen <t:{int(data['last_seen'])}:R>\n"
            else:
                description += "-# Last seen *a long time ago*\n"
            if data['bio']:
                bio = data['bio']
                for word in bio.split():
                    if word.startswith("@"):
                        gyat = word[1:]
                        bio = bio.replace(word, f"[{word}](https://t.me/{gyat})")
                description += bio

            embed = Embed(title=title, description=description, url=f"https://t.me/{username}")
            embed.set_footer(text=f"t.me • {data['id']}", icon_url="https://git.cursi.ng/telegram_logo.png")

            view = View()
            view.add_item(Button(label="View", style=ButtonStyle.link, url=f"https://t.me/{username}"))

            if data['profile_photos']:
                photo_data = base64.b64decode(data['profile_photos'][0])
                file = io.BytesIO(photo_data)
                embed.set_thumbnail(url="attachment://profile.png")
                await interaction.followup.send(embed=embed, file=discord.File(file, filename="profile.png"), view=view)
            else:
                await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await error_handler(interaction, e)

    @reddit.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="The Reddit username to look up.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def user(self, interaction: discord.Interaction, username: str):
        """Get Reddit user information."""

        try:
            redditor = await reddit_client.redditor(username)
            await redditor.load()

            desc_parts = []

            karma = (
                f"🔸 **Karma**\n"
                f"- Post: {redditor.link_karma:,}\n"
                f"- Comment: {redditor.comment_karma:,}\n"
                f"- Total: {redditor.link_karma + redditor.comment_karma:,}"
            )
            desc_parts.append(karma)

            created_at = datetime.datetime.utcfromtimestamp(redditor.created_utc)
            desc_parts.append(f"🔸 **Created**: {discord.utils.format_dt(created_at, style='R')}")

            if getattr(redditor, "is_gold", False):
                desc_parts.append("🔸 **Premium User** 🏆")

            if getattr(redditor, "is_mod", False):
                desc_parts.append("🔸 **Moderator** 🛡️")

            if getattr(redditor, "verified", False):
                desc_parts.append("🔸 **Verified** ✅")

            embed = await cembed(
                interaction,
                title=f"u/{redditor.name}",
                url=f"https://reddit.com/user/{redditor.name}",
                description="\n\n".join(desc_parts),
            )

            if getattr(redditor, "icon_img", None):
                embed.set_thumbnail(url=redditor.icon_img)

            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text="reddit.com", icon_url="https://www.redditstatic.com/desktop2x/img/favicon/android-icon-192x192.png")

            await interaction.followup.send(embed=embed)

        except Exception:
            await interaction.followup.send("User does not exist.")

    @roblox.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="The Roblox username to look up.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def avatar(self, interaction: Interaction, username: str):
        """View a Roblox user's current avatar."""

        try:
            async with self.session.post(
                'https://users.roproxy.com/v1/usernames/users',
                headers={'accept': 'application/json', 'Content-Type': 'application/json'},
                json={'usernames': [username], 'excludeBannedUsers': True}
            ) as search_response:
                if search_response.status == 200:
                    user_data = await search_response.json()
                    if not user_data['data']:
                        await interaction.followup.send("The user you looked up is non-existent.", ephemeral=True)
                        return
                    user_id = user_data['data'][0]['id']
                    roblox_display_name = user_data['data'][0].get('displayName', username)

                    async with self.session.get(f"https://thumbnails.roproxy.com/v1/users/avatar?userIds={user_id}&size=720x720&format=Png&isCircular=false&thumbnailType=3d") as thumbnail_response:
                        if thumbnail_response.status == 200:
                            thumbnail_data = await thumbnail_response.json()
                            thumbnail_url = thumbnail_data['data'][0]['imageUrl']
                            
                            async with self.session.get(thumbnail_url) as img_response:
                                if img_response.status == 200:
                                    image_data = await img_response.read()
                                    file = discord.File(io.BytesIO(image_data), filename="heist.png")
                                else:
                                    return await interaction.followup.send("Failed to fetch avatar image.")
                        else:
                            return await interaction.followup.send("Failed to fetch avatar thumbnail.")

                    embed = await cembed(interaction)
                    embed.set_author(name=f"{interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
                    embed.title = f"{roblox_display_name} (@{user_data['data'][0]['name']})"
                    embed.url = f"https://roblox.com/users/{user_id}/profile"
                    embed.set_image(url="attachment://heist.png")
                    embed.set_footer(text="roblox.com", icon_url="https://git.cursi.ng/roblox_logo.png?v2")

                    await interaction.followup.send(file=file, embed=embed)
                else:
                    await interaction.followup.send("User not found.", ephemeral=True)
                        
        except Exception as e:
            await error_handler(interaction, e)

    @roblox.command()
    @app_commands.describe(username="The Roblox username to look up.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def avatars(self, interaction: Interaction, username: str):
        """View a Roblox user's saved avatars."""

        try:
            async with self.session.post(
                'https://users.roproxy.com/v1/usernames/users',
                headers={'accept': 'application/json', 'Content-Type': 'application/json'},
                json={'usernames': [username], 'excludeBannedUsers': True}
            ) as user_response:
                if user_response.status != 200:
                    return await interaction.followup.send("User not found.", ephemeral=True)
                
                user_data = await user_response.json()
                if not user_data['data']:
                    return await interaction.followup.send("The user you looked up is non-existent.", ephemeral=True)
                
                user_id = user_data['data'][0]['id']
                roblox_display_name = user_data['data'][0].get('displayName', username)

            retry_delays = [1, 2, 3]
            for attempt, delay in enumerate(retry_delays, start=1):
                try:
                    outfits_task = self.session.get(f'https://avatar.roproxy.com/v1/users/{user_id}/outfits?page=1&itemsPerPage=25&isEditable=true')
                    thumbnail_task = self.session.get(f"https://thumbnails.roproxy.com/v1/users/avatar?userIds={user_id}&size=420x420&format=Png&isCircular=false&thumbnailType=3d")

                    outfits_response, thumbnail_response = await asyncio.gather(outfits_task, thumbnail_task)

                    if outfits_response.status == 200:
                        outfits_data = await outfits_response.json()
                        outfits = outfits_data.get('data', [])
                        break
                except Exception as e:
                    if attempt == len(retry_delays):
                        raise e
                    await asyncio.sleep(delay)

            if outfits_response.status != 200:
                return await interaction.followup.send("Failed to fetch avatar data.")
            outfits = outfits_data.get('data', [])
            
            if not outfits:
                return await interaction.followup.send("This user has no saved avatars.")

            thumbnail_url = None
            if thumbnail_response.status == 200:
                thumbnail_data = await thumbnail_response.json()
                thumbnail_url = thumbnail_data['data'][0]['imageUrl']

            class OutfitSelect(ui.Select):
                def __init__(self):
                    options = [
                        discord.SelectOption(
                            label=outfit['name'][:100],
                            value=str(outfit['id']),
                            description=f"avatar #{i+1}"
                        ) for i, outfit in enumerate(outfits)
                    ]
                    super().__init__(placeholder="Select an avatar...", options=options, custom_id="avatar_select")

                async def callback(self, interaction: Interaction):
                    outfit_id = self.values[0]
                    selected_index = next((i for i, outfit in enumerate(outfits) if str(outfit['id']) == outfit_id), 0)
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"https://thumbnails.roproxy.com/v1/users/outfits?userOutfitIds={outfit_id}&size=420x420&format=Png") as response:
                            if response.status == 200:
                                outfit_data = await response.json()
                                outfit_url = outfit_data['data'][0]['imageUrl']
                            else:
                                outfit_url = None
                            
                    embed = await cembed(interaction)
                    embed.set_author(name=f"{interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
                    embed.title = f"{roblox_display_name} (@{user_data['data'][0]['name']})"
                    embed.url = f"https://roblox.com/users/{user_id}/profile"
                    embed.set_footer(text=f"avatar {selected_index + 1} of {len(outfits)} ({outfits[selected_index]['name']})", icon_url="https://git.cursi.ng/roblox_logo.png?v2")

                    if outfit_url:
                        embed.set_image(url=outfit_url)

                    await interaction.response.edit_message(embed=embed, view=self.view)

            embed = await cembed(interaction)
            embed.set_author(name=f"{interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
            embed.title = f"{roblox_display_name} (@{user_data['data'][0]['name']})"
            embed.url = f"https://roblox.com/users/{user_id}/profile"
            embed.set_footer(text="showing current avatar - select a saved avatar", icon_url="https://git.cursi.ng/roblox_logo.png?v2")

            view = ui.View(timeout=300)
            view.add_item(OutfitSelect())

            async def on_timeout():
                for item in view.children:
                    item.disabled = True
                try:
                    await interaction.edit_original_response(view=view)
                except discord.NotFound:
                    pass

            view.on_timeout = on_timeout

            if thumbnail_url:
                embed.set_image(url=thumbnail_url)

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            await error_handler(interaction, e)

    @roblox.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(amount="The amount of Robux, e.g., 100, 1k, 10m.")
    @app_commands.check(permissions.is_blacklisted)
    async def calctax(self, interaction: Interaction, amount: str):
        """Calculate Robux taxes."""
        amount = amount.lower().replace(",", "").strip()
        match = re.match(r"^(\d+)([kmb]?)$", amount)
        
        if not match:
            await interaction.response.send_message(
                "Invalid value entered. Please enter a valid amount like `1k`, `10m`, etc.", 
                ephemeral=True
            )
            return

        amount_value, suffix = match.groups()
        amount_value = int(amount_value)

        if suffix == 'k':
            amount_value *= 1000
        elif suffix == 'm':
            amount_value *= 1_000_000
        elif suffix == 'b':
            amount_value *= 1_000_000_000

        tax_rate = 0.7
        after_tax = math.ceil(amount_value * tax_rate)
        to_send_full = math.ceil(amount_value / tax_rate)

        amount_value_str = f"{amount_value:,}"
        after_tax_str = f"{after_tax:,}"
        to_send_full_str = f"{to_send_full:,}"

        await interaction.response.send_message(
            f"**Initial amount**: **`{amount_value_str}`** <:robux:1296215059600642088>\n"
            f"**After tax**: **`{after_tax_str}`** <:robux:1296215059600642088>\n"
            f"**Total cost for sending sum A/T**: **`{to_send_full_str}`** <:robux:1296215059600642088>"
        )

    @roblox.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(clothingid="The ID/URL of the Roblox clothing.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def template(self, interaction: Interaction, clothingid: str):
        """Grab the template from Roblox clothing."""
        try:
            if clothingid.isdigit():
                clothing_id = clothingid
            else:
                match = await asyncio.to_thread(lambda: re.search(r'/(\d+)/', clothingid))
                if not match:
                    await interaction.followup.send("Invalid Roblox clothing URL or ID.", ephemeral=True)
                    return
                clothing_id = match.group(1)

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0',
                'Cookie': ROBLOX_COOKIE
            }

            xml_url = f'https://assetdelivery.roproxy.com/v1/asset/?id={clothing_id}'
            async with self.session.get(xml_url, headers=headers) as response:
                if response.status != 200:
                    await interaction.followup.send(f"Failed to download XML. Status code: {response.status}", ephemeral=True)
                    return
                xml_content = await response.text()

            match = await asyncio.to_thread(lambda: re.search(r'<url>.*\?id=(\d+)</url>', xml_content))
            if not match:
                await interaction.followup.send("Failed to extract new asset ID from the XML.", ephemeral=True)
                return

            new_id = match.group(1)
            img_url = f'https://assetdelivery.roproxy.com/v1/asset/?id={new_id}'

            async with self.session.get(img_url, headers=headers) as response:
                if response.status != 200:
                    await interaction.followup.send(f"Failed to download clothing image. Status code: {response.status}", ephemeral=True)
                    return

                img_data = await response.read()
                img_byte_arr = await asyncio.to_thread(lambda: io.BytesIO(img_data))
                processed_img = await asyncio.to_thread(lambda: Image.open(img_byte_arr))
                output_buffer = io.BytesIO()
                await asyncio.to_thread(lambda: processed_img.save(output_buffer, format='PNG'))
                output_buffer.seek(0)
                await interaction.followup.send(file=discord.File(output_buffer, filename="heist.png"))

        except Exception as e:
            await error_handler(interaction, e)

    async def dtr_push_redis(self, discord_id: str, roblox_id: int, roblox_name: str, last_updated: str):
        roblox_id = int(roblox_id)
        await self.redis.setex(
            f"dtr:{roblox_id}",
            datetime.timedelta(hours=24),
            f"{discord_id}:{roblox_name}:{last_updated}"
        )

    async def dtr_hit_redis(self, roblox_id: int):
        cached_data = await self.redis.get(f"dtr:{roblox_id}")
        if cached_data:
            parts = cached_data.split(":")
            discord_id, roblox_name, last_updated = parts[0], parts[1], ":".join(parts[2:])
            return discord_id, roblox_name, last_updated
        return None, None, None 

    async def dtr_push_db(self, discord_id: str, roblox_id: int, roblox_name: str):
        roblox_id = int(roblox_id)
        async with get_db_connection() as conn:
            await conn.execute(
                """
                INSERT INTO dtr_mappings (discord_id, roblox_id, roblox_name, last_updated)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                ON CONFLICT (discord_id)
                DO UPDATE SET roblox_id = $2, roblox_name = $3, last_updated = CURRENT_TIMESTAMP
                """,
                discord_id, roblox_id, roblox_name
            )
            await self.dtr_push_redis(discord_id, roblox_id, roblox_name, datetime.datetime.now().isoformat())

    async def dtr_hit_db(self, roblox_id: int):
        async with get_db_connection() as conn:
            row = await conn.fetchrow(
                "SELECT discord_id, roblox_name, last_updated FROM dtr_mappings WHERE roblox_id = $1",
                roblox_id
            )
            if row:
                row = dict(row)
                row["discord_id"] = str(row["discord_id"])
                row["last_updated"] = row["last_updated"].isoformat()
            return row

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="The Roblox username.")
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.check(permissions.is_donor)
    @permissions.requires_perms(embed_links=True)
    async def roblox2discord(self, interaction: Interaction, username: str):
        """✨ Find a Roblox user's linked Discord."""

        async def call_after():
            description = ""
            thumbnail_url = 'https://t0.rbxcdn.com/91d977e12525a5ed262cd4dc1c4fd52b?format=png'

            async def fetch_roblox_id():
                async with self.session.post(
                    'https://users.roproxy.com/v1/usernames/users',
                    headers={'accept': 'application/json', 'Content-Type': 'application/json'},
                    json={'usernames': [username], 'excludeBannedUsers': False}
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return None

            try:
                roblox_data = await fetch_roblox_id()

                if roblox_data and roblox_data.get('data'):
                    roblox_id = int(roblox_data['data'][0]['id'])
                    roblox_name = roblox_data['data'][0]['name']

                    cached_discord_id, cached_name, last_updated = await self.dtr_hit_redis(roblox_id)

                    if not cached_discord_id:
                        row = await self.dtr_hit_db(roblox_id)
                        if row:
                            cached_discord_id = row['discord_id']
                            last_updated = row['last_updated']
                            await self.dtr_push_redis(cached_discord_id, roblox_id, roblox_name, last_updated)

                    discord_av = None
                    if cached_discord_id:
                        discord_user = await self.client.fetch_user(int(cached_discord_id))
                        description += f"Discord: [{discord_user}](discord://-/users/{cached_discord_id}) ({cached_discord_id})\n"
                        description += f"<:pointdrl:1318643571317801040> Updated: <t:{int(datetime.datetime.fromisoformat(last_updated).timestamp())}:R>\n"
                        discord_av = discord_user.display_avatar.url

                    async with self.session.get(f'https://thumbnails.roproxy.com/v1/users/avatar-headshot?userIds={roblox_id}&size=420x420&format=Png&isCircular=false') as thumbnail_response:
                        if thumbnail_response.status == 200:
                            thumbnail_data = await thumbnail_response.json()
                            if thumbnail_data.get('data'):
                                thumbnail_url = thumbnail_data['data'][0].get('imageUrl')

                    async with self.session.get(f'https://api.ropro.io/getUserInfoTest.php?userid={roblox_id}') as ropro_response:
                        if ropro_response.status == 200:
                            ropro_data = await ropro_response.json()
                            ropro_discord = ropro_data.get('discord')

                    if ropro_discord:
                        description += f"RoPro: **{ropro_discord}**"

                    if not description:
                        description = "No linked Discord found for this user."

                    if roblox_id and roblox_name:
                        embed = await cembed(interaction)
                        embed.set_author(name=f"{roblox_name} ({roblox_id})", url=f"https://roblox.com/users/{roblox_id}/profile", icon_url=thumbnail_url)
                        embed.set_thumbnail(url=discord_av if discord_av else thumbnail_url)
                        embed.description = description
                        embed.set_footer(text=f"roblox.com", icon_url="https://git.cursi.ng/roblox_logo.png?v2")

                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("Could not find a linked Discord for this Roblox user.", ephemeral=True)
                else:
                    await interaction.followup.send("Could not find a linked Discord for this Roblox user.", ephemeral=True)

            except Exception as e:
                await error_handler(interaction, e)
            except aiohttp.ClientError as e:
                await interaction.followup.send(f"An error occurred while fetching data: {e}", ephemeral=True)

        await call_after()

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user to get the Roblox of, leave empty to get your own.")
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.check(permissions.is_donor)
    @permissions.requires_perms(embed_links=True)
    async def discord2roblox(self, interaction: Interaction, user: discord.User = None):
        "✨ Find a Discord user's linked Roblox."
        await self.d2r(interaction, user or interaction.user)

    async def d2r(self, interaction: discord.Interaction, user: discord.User):
        user = user or interaction.user
        discord_id = str(user.id)

        async def fetch_thumbnail(roblox_id):
            thumbnail_url = f"https://thumbnails.roproxy.com/v1/users/avatar-headshot?userIds={roblox_id}&size=420x420&format=Png&isCircular=false"
            async with self.session.get(thumbnail_url) as response:
                if response.status == 200:
                    thumbnail_data = await response.json()
                    if thumbnail_data.get('data'):
                        return thumbnail_data['data'][0].get('imageUrl')
                return None

        async def call_after():
            try:
                roblox_id, roblox_name, last_updated = await self.dtr_hit_redis(discord_id)

                if not roblox_name:
                    row = await self.dtr_hit_db(int(discord_id))
                    if row:
                        roblox_id = row['roblox_id']
                        roblox_name = row['roblox_name']
                        last_updated = row.get('last_updated', 'Unknown')
                        await self.dtr_push_redis(discord_id, roblox_id, roblox_name, last_updated)
                    else:
                        url = f"https://api.blox.link/v4/public/discord-to-roblox/{int(discord_id)}"
                        headers = {"Authorization": "23cd07ae-024d-46c6-bb97-ed5d803fff20"}

                        async with self.session.get(url, headers=headers) as response:
                            data = await response.json()

                            if response.status == 200 and 'error' not in data:
                                roblox_id = data.get('robloxID')
                                roblox_data = data.get('resolved', {}).get('roblox', {})
                                roblox_name = roblox_data.get('name')
                                roblox_display_name = roblox_data.get('displayName', roblox_name)

                                if roblox_id and roblox_name:
                                    await self.dtr_push_db(discord_id, roblox_id, roblox_name)
                                    await self.dtr_push_redis(discord_id, roblox_id, roblox_name, datetime.datetime.now().isoformat())
                            else:
                                await interaction.followup.send("Could not find a linked Roblox for this Discord user.", ephemeral=True)
                                return

                if roblox_name:
                    roblox_id = int(roblox_id)
                    headshot_url = await fetch_thumbnail(roblox_id)
                    if not headshot_url:
                        headshot_url = 'https://t0.rbxcdn.com/91d977e12525a5ed262cd4dc1c4fd52b?format=png'

                    embed = await cembed(interaction)
                    embed.set_author(
                        name=f"{roblox_name} ({roblox_id})",
                        url=f"https://roblox.com/users/{roblox_id}/profile",
                        icon_url=headshot_url
                    )
                    embed.set_thumbnail(url=headshot_url)
                    embed.description = f"Username: **{roblox_name}**\n\n[view profile](https://roblox.com/users/{roblox_id}/profile)"
                    embed.set_footer(text=f"roblox.com", icon_url="https://git.cursi.ng/roblox_logo.png?v2")

                    await interaction.followup.send(embed=embed, ephemeral=False)
                else:
                    await interaction.followup.send("Could not find a linked Roblox for this Discord user.", ephemeral=True)

            except Exception as e:
                await error_handler(interaction, e)
                print(f'Error: {e}')
            except aiohttp.ClientError as e:
                await interaction.followup.send(f"An error occurred while fetching data: {e}", ephemeral=True)
                print(f'Error: {e}')

        await call_after()

    @github.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="The GitHub username.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def user(self, interaction: Interaction, username: str):
        """Get GitHub user information."""

        url = f"https://api.github.com/users/{username}"
        headers = {'Accept': 'application/vnd.github.v3+json'}
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                user_data = await response.json()
                name = user_data.get('name')
                bio = user_data.get('bio')
                followers = user_data.get('followers', 0)
                following = user_data.get('following', 0)
                public_repos = user_data.get('public_repos', 0)
                public_gists = user_data.get('public_gists', 0)
                avatar_url = user_data.get('avatar_url', '')
                website = user_data.get('blog')
                created_at = datetime.datetime.strptime(user_data.get('created_at'), "%Y-%m-%dT%H:%M:%SZ")
                
                async with self.session.get(f"https://github-contributions-api.jogruber.de/v4/{username}") as contrib_r:
                    if contrib_r.status == 200:
                        contrib_data = await contrib_r.json()
                        current_year = str(datetime.datetime.now().year)
                        contribs = contrib_data.get('total', {}).get(current_year, 0)
                    else:
                        contribs = 0
                
                title = f"{name} (@{username})" if name else f"@{username}"
                
                embed = await cembed(interaction, title=title, url=f"https://github.com/{username}")
                embed.set_thumbnail(url=avatar_url)
                embed.set_author(name=f"{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
                
                if bio:
                    embed.description = bio
                    
                if website:
                    display_url = website.replace('https://', '').replace('http://', '').rstrip('/')
                    if not bio:
                        embed.description = f"[{display_url}]({website})"
                    else:
                        embed.description = f"{bio}\n[{display_url}]({website})"

                embed.add_field(name="Contributions", value=f"**`{contribs}`** in the last year", inline=True)
                embed.add_field(name="Followers", value=f"**`{followers}`**", inline=True)
                embed.add_field(name="Following", value=f"**`{following}`**", inline=True)
                embed.add_field(name="Public Repos", value=f"**`{public_repos}`**", inline=True)
                embed.add_field(name="Public Gists", value=f"**`{public_gists}`**", inline=True)
                
                joined_date = created_at.strftime("%d/%m/%Y %I:%M %p")
                embed.set_footer(text=f"github.com • Joined {joined_date}", icon_url="https://git.cursi.ng/github_logo.png")
                
                try:
                    await interaction.followup.send(embed=embed)
                except Exception as e:
                    await error_handler(interaction, e)
            elif response.status == 404:
                await interaction.followup.send("User not found.")
            else:
                await interaction.followup.send(f"Failed to fetch data. Status code: {response.status}")

    @osu.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="The osu! username to lookup.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def user(self, interaction: discord.Interaction, username: str = None):
        "Get osu! user information."
        try:
            async def fetch_osu_user_info():
                url = f"https://osu.ppy.sh/api/get_user?k={OSU_KEY}&u={username}"
                async with self.session.get(url) as response:
                    return await response.json() if response.status == 200 else None

            async def fetch_osu_top_scores():
                url = f"https://osu.ppy.sh/api/get_user_best?k={OSU_KEY}&u={username}&limit=5"
                async with self.session.get(url) as response:
                    return await response.json() if response.status == 200 else []

            async def fetch_osu_recent_scores():
                url = f"https://osu.ppy.sh/api/get_user_recent?k={OSU_KEY}&u={username}&limit=1"
                async with self.session.get(url) as response:
                    return await response.json() if response.status == 200 else []

            async def fetch_osu_beatmap(beatmap_id):
                url = f"https://osu.ppy.sh/api/get_beatmaps?k={OSU_KEY}&b={beatmap_id}"
                async with self.session.get(url) as response:
                    return await response.json() if response.status == 200 else None

            def calculate_osu_accuracy(count300, count100, count50, countmiss):
                total_hits = count300 + count100 + count50 + countmiss
                accuracy = (
                    (count50 * 50.0 + count100 * 100.0 + count300 * 300.0) / 
                    (total_hits * 300.0)
                ) * 100
                return accuracy

            def get_country_flag(country_code):
                country_code = country_code.upper()
                base = 0x1F1E6
                return chr(base + country_code.encode()[0]) + chr(base + country_code.encode()[1])

            user_info, top_scores, recent_scores = await asyncio.gather(
                fetch_osu_user_info(),
                fetch_osu_top_scores(),
                fetch_osu_recent_scores()
            )

            if not user_info:
                await interaction.followup.send("Failed to fetch user information.")
                return

            user_info = user_info[0] if isinstance(user_info, list) else user_info

            osu_display = user_info.get('username', username)
            title = f"{osu_display} (@{username})" if osu_display != username else f"@{username}"
            country = user_info.get('country', 'Unknown')
            country_flag = get_country_flag(country)
            pp = int(float(user_info.get('pp_raw', 0))) 
            rank = int(user_info.get('pp_rank', 0))
            country_rank = int(user_info.get('pp_country_rank', 0))
            accuracy = float(user_info.get('accuracy', 0.0))
            playcount = int(user_info.get('playcount', 0))
            level = int(float(user_info.get('level', 0)))
            total_seconds = int(user_info.get('total_seconds_played', 0))
            total_playtime = f"{total_seconds // 3600} hours"
            profile_picture = f"https://a.ppy.sh/{user_info.get('user_id', '')}"

            embed = discord.Embed(title=title, url=f"https://osu.ppy.sh/users/{user_info.get('user_id', '')}")
            embed.description = f"-# **Country:** {country_flag} {country}\n-# **Level:** {level}\n-# **Total Playtime:** {total_playtime}"

            embed.add_field(name="PP", value=f"{pp:,}", inline=True)
            embed.add_field(name="Global Rank", value=f"#{rank:,}", inline=True)
            embed.add_field(name="Country Rank", value=f"#{country_rank:,}", inline=True)
            embed.add_field(name="Accuracy", value=f"{accuracy:.2f}%", inline=True)
            embed.add_field(name="Playcount", value=f"{playcount:,}", inline=True)

            if top_scores:
                top_score = top_scores[0]
                beatmap = await fetch_osu_beatmap(top_score['beatmap_id'])
                
                if beatmap and isinstance(beatmap, list):
                    beatmap = beatmap[0]
                    top_map_title = beatmap.get('title', 'Unknown Beatmap')
                    top_difficulty = beatmap.get('version', 'Unknown Difficulty')
                    top_accuracy = calculate_osu_accuracy(
                        int(top_score.get('count300', 0)),
                        int(top_score.get('count100', 0)),
                        int(top_score.get('count50', 0)),
                        int(top_score.get('countmiss', 0))
                    )
                    embed.add_field(
                        name="Top Play",
                        value=f"[{top_map_title} [{top_difficulty}]](https://osu.ppy.sh/beatmaps/{top_score['beatmap_id']})\n-# **Rank:** {top_score.get('rank', 'N/A')}\n-# **Accuracy:** {top_accuracy:.2f}%\n-# **PP:** {top_score.get('pp', 'N/A')}\n-# **Mods:** {top_score.get('enabled_mods', 'None')}",
                        inline=True
                    )

            if recent_scores:
                recent_score = recent_scores[0]
                beatmap = await fetch_osu_beatmap(recent_score['beatmap_id'])
                
                if beatmap and isinstance(beatmap, list):
                    beatmap = beatmap[0]
                    recent_map_title = beatmap.get('title', 'Unknown Beatmap')
                    recent_difficulty = beatmap.get('version', 'Unknown Difficulty')
                    recent_accuracy = calculate_osu_accuracy(
                        int(recent_score.get('count300', 0)),
                        int(recent_score.get('count100', 0)),
                        int(recent_score.get('count50', 0)),
                        int(recent_score.get('countmiss', 0))
                    )
                    embed.add_field(
                        name="Recent Play",
                        value=f"[{recent_map_title} [{recent_difficulty}]](https://osu.ppy.sh/beatmaps/{recent_score['beatmap_id']})\n-# **Mods:** {recent_score.get('enabled_mods', 'None')}\n-# **Rank:** {recent_score.get('rank', 'N/A')}\n-# **Accuracy:** {recent_accuracy:.2f}%\n-# **PP:** {recent_score.get('pp', 'N/A')}",
                        inline=True
                    )
                else:
                    embed.add_field(name="Recent Play", value="No recent plays found.", inline=True)

            embed.set_thumbnail(url=profile_picture)
            embed.set_footer(text=f"{osu_display} • #{rank:,} globally • #{country_rank:,} in {country}", icon_url="https://git.cursi.ng/osu!_logo.png")

            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label="osu! Profile",
                    style=discord.ButtonStyle.link,
                    url=f"https://osu.ppy.sh/users/{user_info.get('user_id', '')}"
                )
            )

            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await error_handler(interaction, e)

    @tiktok.command()
    @app_commands.describe(username="The TikTok username to look up.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def user(self, interaction: discord.Interaction, username: str):
        """Get TikTok user information."""

        api_url = f"https://tikwm.com/api/user/info?unique_id={username}"

        def format_number(number):
            if number >= 1_000_000_000:
                return f"{number / 1_000_000_000:.1f}b"
            elif number >= 1_000_000:
                return f"{number / 1_000_000:.1f}m"
            elif number >= 1_000:
                return f"{number / 1_000:.1f}k"
            return str(number)

        async with self.session.get(api_url) as response:
            if response.status == 200:
                data = await response.json()

                if data.get('code') == 0:
                    user_data = data.get('data', {})
                    user_info = user_data.get('user', {})
                    bio = user_info.get('signature', 'No bio available')
                    bio = re.sub(r'@(\w+)', r'[@\1](https://www.tiktok.com/@\1)', bio)
                    profile_pic = user_info.get('avatarLarger', None)
                    followers = format_number(user_data.get('stats', {}).get('followerCount', 'N/A'))
                    following = format_number(user_data.get('stats', {}).get('followingCount', 'N/A'))
                    likes = format_number(user_data.get('stats', {}).get('heartCount', 'N/A'))
                    nickname = user_info.get('nickname', 'Unknown')
                    unique_id = user_info.get('uniqueId', '')
                    verified = user_info.get('verified', False)

                    title = f"{nickname} (@{unique_id})"
                    if verified:
                        title += " <:verified_light_blue:1362170749271408911>"

                    embed = await cembed(
                        interaction,
                        title=title,
                        url=f"https://www.tiktok.com/@{unique_id}",
                        description=f"{bio}"
                    )

                    embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)

                    embed.add_field(name='Followers', value=f"**`{followers}`**", inline=True)
                    embed.add_field(name='Following', value=f"**`{following}`**", inline=True)
                    embed.add_field(name='Likes', value=f"**`{likes}`**", inline=True)

                    embed.set_footer(text="tiktok.com", icon_url="https://git.cursi.ng/tiktok_logo.png?2")

                    if profile_pic:
                        embed.set_thumbnail(url=profile_pic)

                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("User does not exist.")
            else:
                await interaction.followup.send("Failed to fetch TikTok data.")

    @x.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="The URL of the X post.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def post(self, interaction: Interaction, url: str):
        """Get information about a X.com (Twitter) post."""

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            parsed_url = await asyncio.to_thread(urlparse, url)
            if parsed_url.netloc not in ["twitter.com", "x.com"]:
                await interaction.followup.send("The provided URL must be from X (formerly known as Twitter).")
                return
            
            encoded_url = quote(url)
            api_url = f"http://127.0.0.1:1118/socials/twitter/{encoded_url}"
            headers = {'X-API-Key': API_KEY}
            
            async with self.session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    tweet_data = data['tweet']
                    
                    created_at = tweet_data['created_at']
                    text = tweet_data['text']
                    text = re.sub(r'@(\w+)', r'[@\1](https://x.com/\1)', text)
                    text = re.sub(r'#(\w+)', r'[#\1](https://x.com/hashtag/\1)', text)
                    
                    timestamp = datetime.datetime.strptime(created_at, "%a %b %d %H:%M:%S +0000 %Y")
                    formatted_time = timestamp.strftime("%m/%d/%Y %I:%M %p")

                    likes = f"{int(tweet_data['likes']/1000)}k" if tweet_data['likes'] >= 1000 and tweet_data['likes'] % 1000 == 0 else f"{tweet_data['likes']/1000:.1f}k" if tweet_data['likes'] >= 1000 else tweet_data['likes']
                    replies = f"{int(tweet_data['replies']/1000)}k" if tweet_data['replies'] >= 1000 and tweet_data['replies'] % 1000 == 0 else f"{tweet_data['replies']/1000:.1f}k" if tweet_data['replies'] >= 1000 else tweet_data['replies']
                    retweets = f"{int(tweet_data['retweets']/1000)}k" if tweet_data['retweets'] >= 1000 and tweet_data['retweets'] % 1000 == 0 else f"{tweet_data['retweets']/1000:.1f}k" if tweet_data['retweets'] >= 1000 else tweet_data['retweets']

                    embed = await cembed(
                        interaction,
                        description=f"{text}\n\n"
                    )
                    
                    embed.set_author(
                        name=f"{tweet_data['author']['name']} (@{tweet_data['author']['screen_name']})",
                        url=url,
                        icon_url=tweet_data['author']['avatar_url']
                    )
                    
                    footer_text = f"{likes} ❤️ • {replies} 💬 • {retweets} 🔁 | {formatted_time}"
                    embed.set_footer(text="x.com", icon_url="https://git.cursi.ng/x_logo.png")
                    
                    files = []
                    has_media = False
                    if tweet_data.get('media') and tweet_data['media'].get('all'):
                        has_media = True
                        for media in tweet_data['media']['all']:
                            if media['type'] == 'photo':
                                async with self.session.get(media['url']) as img_response:
                                    if img_response.status == 200:
                                        img_data = await img_response.read()
                                        file = discord.File(io.BytesIO(img_data), f"heist_{len(files)}.png")
                                        files.append(file)
                                        
                            elif media['type'] == 'video':
                                highest_bitrate = 0
                                video_url = None
                                
                                for variant in media['variants']:
                                    if variant.get('bitrate', 0) > highest_bitrate and variant['content_type'] == 'video/mp4':
                                        highest_bitrate = variant['bitrate']
                                        video_url = variant['url']
                                
                                if video_url:
                                    async with self.session.get(video_url) as vid_response:
                                        if vid_response.status == 200:
                                            vid_data = await vid_response.read()
                                            file = discord.File(io.BytesIO(vid_data), f"heist_{len(files)}.mp4")
                                            files.append(file)
                    
                    if has_media and not interaction.app_permissions.attach_files:
                        try:
                            await interaction.followup.send("-# Missing the `Attach Files` permission, unable to show media.", embed=embed)
                            return
                        except Exception as e:
                            await error_handler(interaction, e)

                    try:
                        if len(files) > 0:
                            await interaction.followup.send(embed=embed, files=files)
                        else:
                            await interaction.followup.send(embed=embed)
                    except discord.HTTPException as http_error:
                        if http_error.code == 40005:
                            await interaction.followup.send("-# Media could not be sent due to size limits.", embed=embed)
                        else:
                            raise
                else:
                    await interaction.followup.send("Failed to fetch tweet data.")

        except Exception as e:
            await error_handler(interaction, e)

    async def search_autocomplete(self, interaction: Interaction, current: str):
        if not current:
            return []
        search_results = await asyncio.to_thread(lambda: Search(current).results[:10])
        return [
            app_commands.Choice(name=video.title, value=video.watch_url)
            for video in search_results
        ]

    @youtube.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(query="The query to search.")
    @app_commands.autocomplete(query=search_autocomplete)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def search(self, interaction: Interaction, query: str):
        """Search for YouTube videos."""

        try:
            search_results = await asyncio.to_thread(lambda: Search(query).results)
            if not search_results:
                await interaction.followup.send("No videos found.")
                return

            video_pages = []
            entries_per_page = 1
            for i in range(0, len(search_results), entries_per_page):
                page = search_results[i:i + entries_per_page]
                video_pages.append(page)

            class YouTubeView(View):
                def __init__(self, interaction: Interaction, video_pages: list):
                    super().__init__(timeout=240)
                    self.interaction = interaction
                    self.video_pages = video_pages
                    self.current_page = 0
                    self.update_button_states()

                def update_button_states(self):
                    self.previous_button.disabled = self.current_page == 0
                    self.next_button.disabled = self.current_page == len(self.video_pages) - 1

                async def update_content(self):
                    page = self.video_pages[self.current_page]
                    video = page[0]
                    url = video.watch_url
                    content = f"({self.current_page + 1}/{len(self.video_pages)}) {url}"
                    await self.interaction.edit_original_response(content=content, view=self)

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary, custom_id="youtubeleft")
                async def previous_button(self, interaction: Interaction, button: Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.followup.send("You cannot interact with someone else's message.", ephemeral=True)
                        return

                    if self.current_page > 0:
                        self.current_page -= 1
                        await interaction.response.defer()
                        self.update_button_states()
                        await self.update_content()

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary, custom_id="youtuberight")
                async def next_button(self, interaction: Interaction, button: Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.followup.send("You cannot interact with someone else's message.", ephemeral=True)
                        return

                    if self.current_page < len(self.video_pages) - 1:
                        self.current_page += 1
                        await interaction.response.defer()
                        self.update_button_states()
                        await self.update_content()

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary, custom_id="youtubeskip")
                async def skip_button(self, interaction: Interaction, button: Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's message.", ephemeral=True)
                        return

                    class GoToPageModal(discord.ui.Modal, title="Go to Page"):
                        def __init__(self, view):
                            super().__init__()
                            self.view = view
                            self.page_number = discord.ui.TextInput(
                                label="Navigate to page",
                                placeholder=f"Enter a page number (1-{len(self.view.video_pages)})",
                                min_length=1,
                                max_length=len(str(len(self.view.video_pages)))
                            )
                            self.add_item(self.page_number)

                        async def on_submit(self, interaction: Interaction):
                            try:
                                page = int(self.page_number.value) - 1
                                if page < 0 or page >= len(self.view.video_pages):
                                    raise ValueError
                                self.view.current_page = page
                                self.view.update_button_states()
                                await self.view.update_content()
                                await interaction.response.defer()
                            except ValueError:
                                await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

                    modal = GoToPageModal(self)
                    await interaction.response.send_modal(modal)

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger, custom_id="youtubedelete")
                async def delete_button(self, interaction: Interaction, button: Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's message.", ephemeral=True)
                        return

                    await interaction.response.defer()
                    await interaction.delete_original_response()

                async def on_timeout(self):
                    for item in self.children:
                        if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                            item.disabled = True

                    try:
                        await self.interaction.edit_original_response(view=self)
                    except discord.NotFound:
                        pass

            view = YouTubeView(interaction, video_pages)
            await view.update_content()
        except Exception as e:
            await error_handler(interaction, e)

    @youtube.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="The URL of the YouTube Short.")
    @commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def short(self, interaction: Interaction, url: str):
        """Repost a YouTube Short."""

        try:
            parsed_url = await asyncio.to_thread(urlparse, url)
            if "youtube.com" not in parsed_url.netloc or "/shorts/" not in parsed_url.path:
                await interaction.followup.send("The provided URL must be a YouTube short.")
                return

            headers = {
                "X-API-Key": API_KEY
            }

            async with self.session.get(f"http://127.0.0.1:1118/socials/youtube/shorts/{url}", headers=headers) as response:
                if response.status == 200:
                    video_content = await response.read()
                    video_file = discord.File(io.BytesIO(video_content), filename="heist.mp4")

                    await interaction.followup.send(
                        content=f"[Original Short](<{url}>)", 
                        files=[video_file]
                    )
                else:
                    await interaction.followup.send(f"Failed to download the video. Status code: {response.status}")
        except Exception as e:
            await error_handler(interaction, e)

    @medaltv.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="The URL of the Medal clip.")
    @commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def repost(self, interaction: Interaction, url: str):
        """Repost a Medal TV clip."""

        async def upload_to_catbox(file_data: io.BytesIO) -> str | None:
            try:
                data = aiohttp.FormData()
                data.add_field('reqtype', 'fileupload')
                data.add_field('fileToUpload', file_data, filename='clip.mp4')
                async with self.session.post('https://catbox.moe/user/api.php', data=data) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        return None
            except Exception:
                return None

        try:
            headers = {"Content-Type": "application/json"}
            payload = {"url": url}

            async with self.session.post("https://medalbypass.vercel.app/api/clip", headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("valid", False):
                        video_url = data["src"]
                        async with self.session.get(video_url) as video_response:
                            if video_response.status == 200:
                                video_content = await video_response.read()
                                video_size = len(video_content)

                                if video_size > 10 * 1024 * 1024:
                                    catbox_url = await upload_to_catbox(io.BytesIO(video_content))
                                    if catbox_url:
                                        await interaction.followup.send(f"-# [**Medal.tv**](<{url}>) • [**Download**]({catbox_url})\n-# This video exceeds the limit of 10MB, hence it was uploaded to [catbox](<https://catbox.moe>).")
                                    else:
                                        await interaction.followup.send("Failed to upload the video to Catbox.")
                                else:
                                    video_file = discord.File(io.BytesIO(video_content), filename="clip.mp4")
                                    await interaction.followup.send(
                                        content=f"[Original Clip](<{url}>)", 
                                        files=[video_file]
                                    )
                            else:
                                await interaction.followup.send(f"Failed to download the video. Status code: {video_response.status}")
                    else:
                        await interaction.followup.send(f"Invalid clip. Reason: {data.get('reasoning', 'Unknown')}")
                else:
                    await interaction.followup.send(f"Failed to fetch clip data. Status code: {response.status}")
        except Exception as e:
            await error_handler(interaction, e)

    @tiktok.command(name="repost", description="Repost a TikTok.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="The URL of the TikTok post.")
    @commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def repost(self, interaction: Interaction, url: str):
        """Repost a TikTok."""

        class SlideshowView(View):
            def __init__(self, images: list, interaction: discord.Interaction, session: aiohttp.ClientSession, music_url: str = None):
                super().__init__(timeout=240)
                self.images = images
                self.current_page = 0
                self.interaction = interaction
                self.message = None
                self.session = session
                self.music_url = music_url
                self.update_button_states()

            def update_button_states(self):
                self.previous_button.disabled = (self.current_page == 0)
                self.next_button.disabled = (self.current_page == (len(self.images) - 1) // 9)

            async def update_embed(self):
                if self.message is None:
                    return

                start_index = self.current_page * 9
                end_index = start_index + 9
                current_images = self.images[start_index:end_index]

                stats = tikwm_data.get("data", {})
                likes = await format_metric(stats.get('digg_count', 0))
                views = await format_metric(stats.get('play_count', 0), use_millions=True)
                comments = await format_metric(stats.get('comment_count', 0))
                shares = await format_metric(stats.get('share_count', 0))
                
                create_time = await asyncio.to_thread(lambda: datetime.datetime.fromtimestamp(stats.get('create_time', 0)).strftime("%m/%d/%Y %I:%M %p"))
                tiktokstats = f"❤️ {likes} • 👁️ {views} • 🗨️ {comments} • 🔄 {shares} | {create_time}"

                description = stats.get("title", "")
                if description:
                    description = await process_description(description)

                embed = await cembed(
                    interaction,
                    description=description
                )
                embed.set_author(name=f"{username} (@{unique_id})", url=tiktok_link, icon_url=avatar_url)
                embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.images) // 9 + 1} - {tiktokstats}", icon_url="https://git.cursi.ng/tiktok_logo.png?2")

                if interaction.app_permissions.attach_files:
                    files = []
                    for i, image_url in enumerate(current_images):
                        image_data = await download_image(image_url)
                        if image_data:
                            file = discord.File(image_data, filename=f"image{i + 1}.png")
                            files.append(file)
                    await self.message.edit(embed=embed, attachments=files, view=self)
                else:
                    for i, image_url in enumerate(current_images):
                        embed.add_field(name=f"Image {i + 1}", value=f"[View Image]({image_url})", inline=False)
                    await self.message.edit(embed=embed, view=self)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary, custom_id="slideshowleft")
            async def previous_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's embed.", ephemeral=True)
                    return

                await interaction.response.defer()
                if self.current_page > 0:
                    self.current_page -= 1
                    self.update_button_states()
                    await self.update_embed()

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary, custom_id="slideshowright")
            async def next_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's embed.", ephemeral=True)
                    return

                await interaction.response.defer()
                if self.current_page < (len(self.images) - 1) // 9:
                    self.current_page += 1
                    self.update_button_states()
                    await self.update_embed()

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary, custom_id="slideshowskip")
            async def skip_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's embed.", ephemeral=True)
                    return

                class GoToPageModal(discord.ui.Modal, title="Go to Page"):
                    page_number = discord.ui.TextInput(label="Navigate to page", placeholder=f"Enter a page number (1-{len(self.images) // 9 + 1})", min_length=1, max_length=len(str(len(self.images) // 9 + 1)))

                    async def on_submit(self, interaction: discord.Interaction):
                        await interaction.response.defer()
                        try:
                            page = int(self.page_number.value) - 1
                            if page < 0 or page >= len(self.view.images) // 9 + 1:
                                raise ValueError
                            self.view.current_page = page
                            self.view.update_button_states()
                            await self.view.update_embed()
                        except ValueError:
                            await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

                modal = GoToPageModal()
                modal.view = self
                await interaction.response.send_modal(modal)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:audio:1345517095101923439>"), style=discord.ButtonStyle.secondary, custom_id="slideshowaudio")
            async def audio_button(self, interaction: discord.Interaction, button: Button):
                if self.music_url:
                    async with self.session.get(self.music_url) as music_response:
                        if music_response.status == 200:
                            await interaction.response.defer(ephemeral=True)
                            audio_content = await music_response.read()
                            audio_file = discord.File(io.BytesIO(audio_content), filename="audio.opus")
                            await interaction.followup.send(file=audio_file, voice_message=True, ephemeral=True)
                        else:
                            await interaction.followup.send("Failed to download the audio.", ephemeral=True)
                else:
                    await interaction.followup.send("No audio available.", ephemeral=True)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger, custom_id="slideshowdelete")
            async def delete_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's embed.", ephemeral=True)
                    return

                await interaction.response.defer()
                await interaction.delete_original_response()

            async def on_timeout(self):
                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                        item.disabled = True

                try:
                    await self.interaction.edit_original_response(view=self)
                except discord.NotFound:
                    pass

        async def download_image(url: str) -> io.BytesIO | None:
            async with self.session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    return io.BytesIO(image_data)
                else:
                    return None

        async def upload_to_catbox(file_data: io.BytesIO) -> str | None:
            try:
                data = aiohttp.FormData()
                data.add_field('reqtype', 'fileupload')
                data.add_field('fileToUpload', file_data, filename='heist.mp4')
                async with self.session.post('https://catbox.moe/user/api.php', data=data) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        return None
            except Exception:
                return None

        async def format_metric(value, use_millions=False):
            if use_millions and value >= 1000000:
                return f"{int(value/1000000)}M" if value % 1000000 == 0 else f"{value/1000000:.1f}M"
            elif value >= 1000:
                return f"{int(value/1000)}k" if value % 1000 == 0 else f"{value/1000:.1f}k"
            return str(value)

        async def process_description(description: str) -> str:
            return await asyncio.to_thread(
                lambda: "> " + re.sub(r"#(\S+)", r"[#\1](<https://tiktok.com/tag/\1>)", description)
            )

        async def handle_small_video(video_content, description, username, unique_id, tiktok_link, avatar_url, tiktokstats):
            video_file = discord.File(io.BytesIO(video_content), filename="heist.mp4")
            if interaction.app_permissions.attach_files:
                processed_desc = await process_description(description) if description else ""
                embed=await cembed(
                    interaction,
                    description=processed_desc
                )
                embed.set_author(
                    name=f"{username} (@{unique_id})", 
                    url=tiktok_link, 
                    icon_url=avatar_url
                )
                embed.set_footer(
                    text=tiktokstats, 
                    icon_url="https://git.cursi.ng/tiktok_logo.png?2"
                )
                await interaction.followup.send(
                    file=video_file, embed=embed)
            else:
                processed_desc = await process_description(description) if description else ""
                embed=await cembed(
                    interaction,
                    description=processed_desc
                )
                embed.set_author(
                    name=f"{username} (@{unique_id})", 
                    url=tiktok_link, 
                    icon_url=avatar_url
                )
                embed.set_footer(
                    text=tiktokstats, 
                    icon_url="https://git.cursi.ng/tiktok_logo.png?2"
                )
                await interaction.followup.send(
                    "-# Missing the `Attach Files` permission, unable to show video.", 
                    embed=embed
                )

        async def handle_medium_video(catbox_url, description, username, unique_id, tiktok_link, tiktokstats):
            processed_desc = await process_description(description) if description else ""
            message = f"-# Uploaded by **`{username}`** [**`(@{unique_id})`**](<https://www.tiktok.com/@{unique_id}>)\n"
            if description:
                message += f"-# {processed_desc}\n"
            message += f"-# {tiktokstats}\n\n-# [**TikTok**](<{tiktok_link}>) • [**Download**]({catbox_url})\n-# This video exceeds the limit of 10MB, hence it was uploaded to [catbox](<https://catbox.moe>)."
            await interaction.followup.send(message)

        async def handle_large_video(video_url, description, username, unique_id, tiktok_link, avatar_url, tiktokstats):
            processed_desc = await process_description(description) if description else ""
            embed = await cembed(
                interaction,
                description=processed_desc
            )
            embed.set_author(
                name=f"{username} (@{unique_id})", 
                url=tiktok_link, 
                icon_url=avatar_url
            )
            embed.set_footer(
                text=tiktokstats, 
                icon_url="https://git.cursi.ng/tiktok_logo.png?2"
            )
            await interaction.followup.send(
                f"Video is too large, [direct download]({video_url}).", 
                embed=embed
            )

        async def async_json_loads(data):
            if len(data) > 100_000:
                return await asyncio.to_thread(json.loads, data)
            return json.loads(data)

        async def async_json_dumps(data):
            json_str = json.dumps(data)
            if len(json_str) > 100_000:
                return await asyncio.to_thread(json.dumps, data)
            return json_str

        try:
            parsed_url = await asyncio.to_thread(urlparse, url)
            if "tiktok.com" not in parsed_url.netloc:
                await interaction.followup.send("The provided URL must be from TikTok.")
                return

            cache_key = f"tiktok:{url}"
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                tikwm_data = await async_json_loads(cached_data)
            else:
                tikwm_api_url = f"https://tikwm.com/api/?url={url}"
                async with self.session.get(tikwm_api_url) as response:
                    if response.status == 200:
                        tikwm_data = await response.json()
                        await redis_client.setex(cache_key, 7200, await async_json_dumps(tikwm_data))
                    else:
                        await interaction.followup.send(f"Failed to fetch TikTok data. Status code: {response.status}")
                        return

            stats = tikwm_data.get("data", {})
            post_id = stats.get("id", "Unknown")
            author_data = stats.get("author", {})
            username = author_data.get("nickname", "Unknown")
            unique_id = author_data.get("unique_id", "")
            avatar_url = author_data.get("avatar", "")
            description = stats.get("title", "")
            
            likes = await format_metric(stats.get('digg_count', 0))
            views = await format_metric(stats.get('play_count', 0), use_millions=True)
            comments = await format_metric(stats.get('comment_count', 0))
            shares = await format_metric(stats.get('share_count', 0))
            
            create_time = await asyncio.to_thread(lambda: datetime.datetime.fromtimestamp(stats.get('create_time', 0)).strftime("%m/%d/%Y %I:%M %p"))
            tiktokstats = f"❤️ {likes} • 👁️ {views} • 🗨️ {comments} • 🔄 {shares} | {create_time}"
            tiktok_link = f"https://www.tiktok.com/@{unique_id}/video/{post_id}"

            if "images" in stats:
                music_url = stats.get("music")
                view = SlideshowView(stats["images"], interaction, self.session, music_url)
                initial_images = stats["images"][:9]

                processed_description = await process_description(description) if description else ""
                embed = await cembed(
                    interaction,
                    description=processed_description
                )
                embed.set_author(name=f"{username} (@{unique_id})", url=tiktok_link, icon_url=avatar_url)
                embed.set_footer(text=f"Page 1/{len(stats['images']) // 9 + 1} - {tiktokstats}", icon_url="https://git.cursi.ng/tiktok_logo.png?2")

                if interaction.app_permissions.attach_files:
                    files = []
                    for i, image_url in enumerate(initial_images):
                        image_data = await download_image(image_url)
                        if image_data:
                            file = discord.File(image_data, filename=f"image{i + 1}.png")
                            files.append(file)
                    response = await interaction.followup.send(files=files, embed=embed, view=view)
                else:
                    for i, image_url in enumerate(initial_images):
                        embed.add_field(name=f"Image {i + 1}", value=f"[View Image]({image_url})", inline=False)
                    response = await interaction.followup.send(embed=embed, view=view)

                view.message = response
            
            else:
                video_url = stats.get("play")
                if video_url:
                    catbox_key = f"catbox:{video_url}"
                    catbox_url = await redis_client.get(catbox_key)
                    
                    if not catbox_url:
                        async with self.session.get(video_url) as video_response:
                            if video_response.status == 200:
                                video_content = await video_response.read()
                                video_size = len(video_content)

                                if video_size <= 10 * 1024 * 1024:
                                    await handle_small_video(video_content, description, username, unique_id, tiktok_link, avatar_url, tiktokstats)
                                elif video_size <= 50 * 1024 * 1024:
                                    catbox_url = await upload_to_catbox(io.BytesIO(video_content))
                                    if catbox_url:
                                        await redis_client.setex(catbox_key, 7200, catbox_url)
                                        await handle_medium_video(catbox_url, description, username, unique_id, tiktok_link, tiktokstats)
                                    else:
                                        await handle_large_video(video_url, description, username, unique_id, tiktok_link, avatar_url, tiktokstats)
                                else:
                                    await handle_large_video(video_url, description, username, unique_id, tiktok_link, avatar_url, tiktokstats)
                            else:
                                await interaction.followup.send(f"Failed to download the video. Status code: {video_response.status}")
                    else:
                        await handle_medium_video(catbox_url, description, username, unique_id, tiktok_link, tiktokstats)
                else:
                    await interaction.followup.send("Video is currently unavailable.")
        except Exception as e:
            await error_handler(interaction, e)

    @tiktok.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def trending(self, interaction: Interaction):
        """Get a trending TikTok video."""

        class SlideshowView(View):
            def __init__(self, images: list, interaction: discord.Interaction, session: aiohttp.ClientSession, music_url: str = None):
                super().__init__(timeout=240)
                self.images = images
                self.current_page = 0
                self.interaction = interaction
                self.message = None
                self.session = session
                self.music_url = music_url
                self.update_button_states()

            def update_button_states(self):
                self.previous_button.disabled = (self.current_page == 0)
                self.next_button.disabled = (self.current_page == (len(self.images) - 1) // 9)

            async def update_embed(self):
                if self.message is None:
                    return

                start_index = self.current_page * 9
                end_index = start_index + 9
                current_images = self.images[start_index:end_index]

                stats = self.video_data
                likes = await format_metric(stats.get('digg_count', 0))
                views = await format_metric(stats.get('play_count', 0), use_millions=True)
                comments = await format_metric(stats.get('comment_count', 0))
                shares = await format_metric(stats.get('share_count', 0))
                
                create_time = await asyncio.to_thread(lambda: datetime.datetime.fromtimestamp(stats.get('create_time', 0)).strftime("%m/%d/%Y %I:%M %p"))
                tiktokstats = f"❤️ {likes} • 👁️ {views} • 🗨️ {comments} • 🔄 {shares} | {create_time}"

                description = stats.get("title", "")
                if description:
                    description = await process_description(description)

                embed = await cembed(
                    self.interaction,
                    description=description
                )
                embed.set_author(name=f"{self.username} (@{self.unique_id})", url=self.tiktok_link, icon_url=self.avatar_url)
                embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.images) // 9 + 1} - {tiktokstats}", icon_url="https://git.cursi.ng/tiktok_logo.png?2")

                if self.interaction.app_permissions.attach_files:
                    files = []
                    for i, image_url in enumerate(current_images):
                        image_data = await download_image(image_url)
                        if image_data:
                            file = discord.File(image_data, filename=f"image{i + 1}.png")
                            files.append(file)
                    await self.message.edit(embed=embed, attachments=files, view=self)
                else:
                    for i, image_url in enumerate(current_images):
                        embed.add_field(name=f"Image {i + 1}", value=f"[View Image]({image_url})", inline=False)
                    await self.message.edit(embed=embed, view=self)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary, custom_id="slideshowleft")
            async def previous_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's embed.", ephemeral=True)
                    return

                await interaction.response.defer()
                if self.current_page > 0:
                    self.current_page -= 1
                    self.update_button_states()
                    await self.update_embed()

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary, custom_id="slideshowright")
            async def next_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's embed.", ephemeral=True)
                    return

                await interaction.response.defer()
                if self.current_page < (len(self.images) - 1) // 9:
                    self.current_page += 1
                    self.update_button_states()
                    await self.update_embed()

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary, custom_id="slideshowskip")
            async def skip_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's embed.", ephemeral=True)
                    return

                class GoToPageModal(discord.ui.Modal, title="Go to Page"):
                    page_number = discord.ui.TextInput(label="Navigate to page", placeholder=f"Enter a page number (1-{len(self.view.images) // 9 + 1})", min_length=1, max_length=len(str(len(self.view.images) // 9 + 1)))

                    async def on_submit(self, interaction: discord.Interaction):
                        await interaction.response.defer()
                        try:
                            page = int(self.page_number.value) - 1
                            if page < 0 or page >= len(self.view.images) // 9 + 1:
                                raise ValueError
                            self.view.current_page = page
                            self.view.update_button_states()
                            await self.view.update_embed()
                        except ValueError:
                            await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

                modal = GoToPageModal()
                modal.view = self
                await interaction.response.send_modal(modal)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:audio:1345517095101923439>"), style=discord.ButtonStyle.secondary, custom_id="slideshowaudio")
            async def audio_button(self, interaction: discord.Interaction, button: Button):
                if self.music_url:
                    async with self.session.get(self.music_url) as music_response:
                        if music_response.status == 200:
                            await interaction.response.defer(ephemeral=True)
                            audio_content = await music_response.read()
                            audio_file = discord.File(io.BytesIO(audio_content), filename="audio.opus")
                            await interaction.followup.send(file=audio_file, voice_message=True, ephemeral=True)
                        else:
                            await interaction.followup.send("Failed to download the audio.", ephemeral=True)
                else:
                    await interaction.followup.send("No audio available.", ephemeral=True)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger, custom_id="slideshowdelete")
            async def delete_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's embed.", ephemeral=True)
                    return

                await interaction.response.defer()
                await interaction.delete_original_response()

            async def on_timeout(self):
                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                        item.disabled = True

                try:
                    await self.interaction.edit_original_response(view=self)
                except discord.NotFound:
                    pass

        async def download_image(url: str) -> io.BytesIO | None:
            async with self.session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    return io.BytesIO(image_data)
                else:
                    return None

        async def upload_to_catbox(file_data: io.BytesIO) -> str | None:
            try:
                data = aiohttp.FormData()
                data.add_field('reqtype', 'fileupload')
                data.add_field('fileToUpload', file_data, filename='heist.mp4')
                async with self.session.post('https://catbox.moe/user/api.php', data=data) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        return None
            except Exception:
                return None

        async def format_metric(value, use_millions=False):
            if use_millions and value >= 1000000:
                return f"{int(value/1000000)}M" if value % 1000000 == 0 else f"{value/1000000:.1f}M"
            elif value >= 1000:
                return f"{int(value/1000)}k" if value % 1000 == 0 else f"{value/1000:.1f}k"
            return str(value)

        async def process_description(description: str) -> str:
            return await asyncio.to_thread(
                lambda: "> " + re.sub(r"#(\S+)", r"[#\1](<https://tiktok.com/tag/\1>)", description)
            )

        async def handle_small_video(video_content, description, username, unique_id, tiktok_link, avatar_url, tiktokstats):
            video_file = discord.File(io.BytesIO(video_content), filename="heist.mp4")
            if interaction.app_permissions.attach_files:
                processed_desc = await process_description(description) if description else ""
                embed=await cembed(
                    interaction,
                    description=processed_desc
                )
                embed.set_author(
                    name=f"{username} (@{unique_id})", 
                    url=tiktok_link, 
                    icon_url=avatar_url
                )
                embed.set_footer(
                    text=tiktokstats, 
                    icon_url="https://git.cursi.ng/tiktok_logo.png?2"
                )
                await interaction.followup.send(
                    file=video_file, embed=embed)
            else:
                processed_desc = await process_description(description) if description else ""
                embed=await cembed(
                    interaction,
                    description=processed_desc
                )
                embed.set_author(
                    name=f"{username} (@{unique_id})", 
                    url=tiktok_link, 
                    icon_url=avatar_url
                )
                embed.set_footer(
                    text=tiktokstats, 
                    icon_url="https://git.cursi.ng/tiktok_logo.png?2"
                )
                await interaction.followup.send(
                    "-# Missing the `Attach Files` permission, unable to show video.", 
                    embed=embed
                )

        async def handle_medium_video(catbox_url, description, username, unique_id, tiktok_link, tiktokstats):
            processed_desc = await process_description(description) if description else ""
            message = f"-# Uploaded by **`{username}`** [**`(@{unique_id})`**](<https://www.tiktok.com/@{unique_id}>)\n"
            if description:
                message += f"-# {processed_desc}\n"
            message += f"-# {tiktokstats}\n\n-# [**TikTok**](<{tiktok_link}>) • [**Download**]({catbox_url})\n-# This video exceeds the limit of 10MB, hence it was uploaded to [catbox](<https://catbox.moe>)."
            await interaction.followup.send(message)

        async def handle_large_video(video_url, description, username, unique_id, tiktok_link, avatar_url, tiktokstats):
            processed_desc = await process_description(description) if description else ""
            embed = await cembed(
                interaction,
                description=processed_desc
            )
            embed.set_author(
                name=f"{username} (@{unique_id})", 
                url=tiktok_link, 
                icon_url=avatar_url
            )
            embed.set_footer(
                text=tiktokstats, 
                icon_url="https://git.cursi.ng/tiktok_logo.png?2"
            )
            await interaction.followup.send(
                f"Video is too large, [direct download]({video_url}).", 
                embed=embed
            )

        try:
            trending_videos = await self.client.socials.get_tiktok_trending(limit=1)
            if not trending_videos:
                await interaction.followup.send("No trending videos found")
                return

            video = trending_videos[0]
            video_url = video.video_url
            
            tikwm_api_url = f"https://tikwm.com/api/?url={video_url}"
            async with self.session.get(tikwm_api_url) as tikwm_response:
                if tikwm_response.status == 200:
                    tikwm_data = await tikwm_response.json()
                else:
                    await interaction.followup.send(f"Failed to fetch TikTok data. Status code: {tikwm_response.status}")
                    return

            stats = tikwm_data.get("data", {})
            post_id = stats.get("id", "Unknown")
            author_data = stats.get("author", {})
            username = author_data.get("nickname", "Unknown")
            unique_id = author_data.get("unique_id", "")
            avatar_url = author_data.get("avatar", "")
            description = stats.get("title", "")
            
            likes = await format_metric(stats.get('digg_count', 0))
            views = await format_metric(stats.get('play_count', 0), use_millions=True)
            comments = await format_metric(stats.get('comment_count', 0))
            shares = await format_metric(stats.get('share_count', 0))
            
            create_time = await asyncio.to_thread(lambda: datetime.datetime.fromtimestamp(stats.get('create_time', 0)).strftime("%m/%d/%Y %I:%M %p"))
            tiktokstats = f"❤️ {likes} • 👁️ {views} • 🗨️ {comments} • 🔄 {shares} | {create_time}"
            tiktok_link = f"https://www.tiktok.com/@{unique_id}/video/{post_id}"

            if "images" in stats:
                music_url = stats.get("music")
                view = SlideshowView(stats["images"], interaction, self.session, music_url)
                view.video_data = stats
                view.username = username
                view.unique_id = unique_id
                view.tiktok_link = tiktok_link
                view.avatar_url = avatar_url

                initial_images = stats["images"][:9]

                processed_description = await process_description(description) if description else ""
                embed = await cembed(
                    interaction,
                    description=processed_description
                )
                embed.set_author(name=f"{username} (@{unique_id})", url=tiktok_link, icon_url=avatar_url)
                embed.set_footer(text=f"Page 1/{len(stats['images']) // 9 + 1} - {tiktokstats}", icon_url="https://git.cursi.ng/tiktok_logo.png?2")

                if interaction.app_permissions.attach_files:
                    files = []
                    for i, image_url in enumerate(initial_images):
                        image_data = await download_image(image_url)
                        if image_data:
                            file = discord.File(image_data, filename=f"image{i + 1}.png")
                            files.append(file)
                    response = await interaction.followup.send(files=files, embed=embed, view=view)
                else:
                    for i, image_url in enumerate(initial_images):
                        embed.add_field(name=f"Image {i + 1}", value=f"[View Image]({image_url})", inline=False)
                    response = await interaction.followup.send(embed=embed, view=view)

                view.message = response
            
            else:
                video_url = stats.get("play")
                if video_url:
                    catbox_key = f"catbox:{video_url}"
                    catbox_url = await redis_client.get(catbox_key)
                    
                    if not catbox_url:
                        async with self.session.get(video_url) as video_response:
                            if video_response.status == 200:
                                video_content = await video_response.read()
                                video_size = len(video_content)

                                if video_size <= 10 * 1024 * 1024:
                                    await handle_small_video(video_content, description, username, unique_id, tiktok_link, avatar_url, tiktokstats)
                                elif video_size <= 50 * 1024 * 1024:
                                    catbox_url = await upload_to_catbox(io.BytesIO(video_content))
                                    if catbox_url:
                                        await redis_client.setex(catbox_key, 7200, catbox_url)
                                        await handle_medium_video(catbox_url, description, username, unique_id, tiktok_link, tiktokstats)
                                    else:
                                        await handle_large_video(video_url, description, username, unique_id, tiktok_link, avatar_url, tiktokstats)
                                else:
                                    await handle_large_video(video_url, description, username, unique_id, tiktok_link, avatar_url, tiktokstats)
                            else:
                                await interaction.followup.send(f"Failed to download the video. Status code: {video_response.status}")
                    else:
                        await handle_medium_video(catbox_url, description, username, unique_id, tiktok_link, tiktokstats)
                else:
                    await interaction.followup.send("Video is currently unavailable.")
        except Exception as e:
            await error_handler(interaction, e)

    @instagram.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="The URL of the Instagram Reel.")
    @commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def repost(self, interaction: Interaction, url: str):
        """Repost an Instagram Reel."""
        try:
            parsed_url = await asyncio.to_thread(urlparse, url)
            if "instagram.com" not in parsed_url.netloc:
                await interaction.followup.send("The provided URL must be from Instagram.")
                return

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'keep-alive',
                'Dnt': '1',
                'Referer': 'https://www.instagram.com/',
                'Upgrade-Insecure-Requests': '1',
                'TE': 'Trailers',
                'X-Instagram-AJAX': '1',
                'X-CSRFToken': 'missing',
                'X-Requested-With': 'XMLHttpRequest',
            }

            api_url = f"http://localhost:3001/api/video?postUrl={url}"

            async with self.session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    status = data.get("status")

                    if status == "success":
                        video_data = data.get("data")
                        video_url = video_data.get("videoUrl")
                        filename = video_data.get("filename")

                        async with self.session.get(video_url) as video_response:
                            if video_response.status == 200:
                                video_bytes = io.BytesIO(await video_response.read())
                                video_file = discord.File(video_bytes, filename=filename)

                                await interaction.followup.send(
                                    content=f"[Original Reel](<{url}>)",
                                    files=[video_file]
                                )
                            else:
                                await interaction.followup.send(
                                    f"Failed to download the video. Status: {video_response.status}"
                                )
                    else:
                        await interaction.followup.send(f"Error: {data.get('error', 'Unknown error')}")
                else:
                    response_text = await response.text()
                    error_message = f"API request failed. Status code: {response.status}. Response: {response_text}"
                    await interaction.followup.send(f"An error occurred: {error_message}")
                    return

        except aiohttp.ClientError as e:
            await interaction.followup.send(f"Network error occurred: {str(e)}")
        except json.JSONDecodeError:
            await interaction.followup.send("Failed to parse the API response.")
        except Exception as e:
            await error_handler(interaction, e)

    @pinterest.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="The URL of the Pinterest pin.")
    @commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def pin(self, interaction: Interaction, url: str):
        """Repost a Pinterest pin."""

        try:
            parsed = urlparse(url)
            if parsed.netloc.endswith("pinterest.com") and parsed.path.startswith("/pin/"):
                pin_id = parsed.path.split('/')[2]
                cleaned_url = f"https://www.pinterest.com/pin/{pin_id}"
            elif parsed.netloc.endswith("pin.it"):
                pin_id = parsed.path.lstrip('/')
                cleaned_url = f"https://www.pinterest.com/pin/{pin_id}"
            else:
                await interaction.followup.send("The provided URL must be from a Pinterest pin.")
                return

            pin_data = await self.client.socials.get_pinterest_pin(cleaned_url)

            title = pin_data.get("title")
            description = pin_data.get("description")
            embed_url = pin_data.get("link")
            author_username = pin_data.get("fullName")
            author_avatar = pin_data.get("avatar")
            image_url = pin_data.get("image")
            username = pin_data.get("username")
            repin_count = pin_data.get("repinCount", 0)
            comments_count = pin_data.get("commentsCount", 0)
            reactions = pin_data.get("reactions", 0)
            created_at = pin_data.get("createdAt")
            alt_text = pin_data.get("altText")
            annotations = pin_data.get("annotations", [])

            created_at_dt = datetime.datetime.strptime(created_at, "%a, %d %b %Y %H:%M:%S %z")
            created_at_fmt = created_at_dt.strftime("%d/%m/%Y %I:%M %p")

            if alt_text != "N/A":
                annotations_text = f"-# {alt_text}"
            else:
                annotations_text = "-# " + ", ".join([annotation.get("label", "N/A") for annotation in annotations]) if annotations else ""

            async with self.session.get(image_url) as image_response:
                if image_response.status == 200:
                    image_data = await image_response.read()
                    image_file = discord.File(io.BytesIO(image_data), filename="heist.jpg")

                    embed = await cembed(
                        interaction, 
                        title=title, 
                        description=f"-# {description}\n{annotations_text}", 
                        url=embed_url
                    )
                    embed.set_footer(
                        text=f"{repin_count} 📌 • {comments_count} 💬 • {reactions} ❤️ | {created_at_fmt}", 
                        icon_url="https://git.cursi.ng/pinterest_logo.png"
                    )
                    embed.set_author(
                        name=f"{author_username} (@{username})", 
                        icon_url=author_avatar, 
                        url=f"https://www.pinterest.com/{username}/"
                    )
                    embed.set_image(url="attachment://heist.jpg")

                    await interaction.followup.send(
                        embed=embed, 
                        file=image_file
                    )
                else:
                    await interaction.followup.send("Failed to retrieve the image from Pinterest.")

        except ValueError as e:
            await interaction.followup.send(str(e))
        except Exception as e:
            await error_handler(interaction, e)

    @pinterestsearch.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(query="What to search for on Pinterest.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def image(self, interaction: Interaction, query: str):
        """Search for images on Pinterest."""

        try:
            image_urls = await self.client.socials.search_pinterest(query)
            
            if not image_urls:
                await interaction.followup.send(f"No images found for **{query}**.", ephemeral=True)
                return

            async def fetch_image(url):
                try:
                    async with self.session.get(url) as image_response:
                        if image_response.status == 200:
                            return await image_response.read()
                except Exception:
                    return None

            image_tasks = [fetch_image(url) for url in image_urls[:9]]
            images = await asyncio.gather(*image_tasks)
            images = [img for img in images if img is not None]

            if not images:
                await interaction.followup.send(f"No images found for **{query}**.", ephemeral=True)
                return

            files = [discord.File(io.BytesIO(image), filename=f"heist_{i+1}.png") for i, image in enumerate(images)]
            await interaction.followup.send(f"Successfully searched for **{query}**.", files=files)

        except Exception as e:
            await error_handler(interaction, e)

    @bio.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="The Guns.lol username.")
    @commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def gunslol(self, interaction: Interaction, username: str):
        """Lookup a guns.lol user."""
        try:
            url = "https://guns.lol/api/user/lookup"
            api = GUNSLOL_KEY
            headers = {"Content-Type": "application/json"}
            data = {
                "username": username,
                "key": api
            }

            response = await self.session.post(url, headers=headers, json=data)

            if response.status == 200:
                user_data = await response.json()
                title = f"{username}"
                if "premium" in user_data["config"]["user_badges"]:
                    title += " <a:diamond:1282326797685624832>"
                
                embed = await cembed(
                    interaction,
                    title=title, 
                    url=f"https://guns.lol/{username}", 
                    description=user_data['config']['description'], 
                )

                embed.set_author(
                    name=f"{interaction.user.name}", 
                    icon_url=interaction.user.display_avatar.url if interaction.user.avatar else interaction.user.default_avatar.url
                )

                gunslol_avatar = user_data['config'].get('avatar')
                if gunslol_avatar:
                    embed.set_thumbnail(url=gunslol_avatar)

                background_url = user_data['config'].get('url')
                if background_url and background_url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    embed.set_image(url=background_url)

                created_timestamp = user_data["account_created"]
                discord_timestamp = f"<t:{created_timestamp}:R>"
                embed.add_field(name="Created", value=discord_timestamp, inline=True)

                alias = user_data.get('alias')
                if alias:
                    embed.add_field(name="Alias", value=alias, inline=True)

                file_url = user_data.get('config', {}).get('url')
                if file_url:
                    if file_url.lower().endswith(('.mp4', '.avi', '.mov')):
                        field_name = "Video"
                    elif file_url.lower().endswith(('.jpg', '.jpeg', '.png')):
                        field_name = "Image"
                    elif file_url.lower().endswith('.gif'):
                        field_name = "GIF"
                    else:
                        field_name = "File"

                    embed.add_field(name=field_name, value=f"[Click here]({file_url})", inline=True)

                audio_list = user_data.get('config', {}).get('audio')
                if audio_list:
                    if isinstance(audio_list, list):
                        audio_field = "\n".join([f"[{audio['title']}]({audio['url']})" for audio in audio_list])
                    else:
                        audio_field = f"[Click here]({audio_list})"
                    embed.add_field(name="Audio", value=audio_field, inline=True)

                cursor = user_data.get('config', {}).get('custom_cursor')
                if cursor:
                    embed.add_field(name="Cursor", value=f"[Click here]({cursor})", inline=True)

                embed.set_footer(
                    text=f"{user_data['config']['page_views']} views ● UID {user_data['uid']}", 
                    icon_url="https://git.cursi.ng/guns_logo.png?v2"
                )
                
                await interaction.followup.send(embed=embed)
            else:
                error_content = await response.text()
                print(f"Error {response.status}: {error_content}")
                await interaction.followup.send("User not found, check out [@cosmin](<https://guns.lol/cosmin>) tho.")
        except Exception as e:
            await error_handler(interaction, e)

    @bio.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="The Ammo.lol username.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def ammolol(self, interaction: Interaction, username: str):
        """Lookup an ammo.lol user."""
        try:
            url = "https://ammo.lol/api/v1/public/user"
            api_key = AMMOLOL_KEY
            headers = {"Content-Type": "application/json", "API-Key": api_key}
            params = {'username': username}

            response = await self.session.get(url, headers=headers, params=params)

            if response.status == 200:
                user_data = await response.json()
                title = f"{user_data['username']}"
                if user_data.get('premium'):
                    title += " <a:diamond:1282326797685624832>"
                embed = await cembed(interaction, title=title, url=user_data['url'])

                embed.set_author(name=f"{interaction.user.name}", icon_url=interaction.user.display_avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)

                if 'description' in user_data and user_data['description']:
                    embed.description = user_data['description']

                if 'avatar_url' in user_data and user_data['avatar_url'] != 'No avatar':
                    embed.set_thumbnail(url=user_data['avatar_url'])

                if 'background_url' in user_data and user_data['background_url'] != 'No background':
                    embed.set_image(url=user_data['background_url'])

                created_date = datetime.datetime.strptime(user_data['created'], "%d/%m/%Y")
                created_timestamp = int(time.mktime(created_date.timetuple()))
                discord_timestamp = f"<t:{created_timestamp}:R>"

                embed.add_field(name="Created", value=discord_timestamp, inline=True)

                alias = user_data.get('alias')
                if alias:
                    embed.add_field(name="Alias", value=alias, inline=True)

                cursor_url = user_data.get('cursor_url')
                if cursor_url and cursor_url.lower() != 'no cursor':
                    embed.add_field(name="Cursor", value=f"[Click here]({cursor_url})", inline=True)

                audio_url = user_data.get('audio_url')
                if audio_url and audio_url.lower() != 'no audio':
                    embed.add_field(name="Audio", value=f"[Click here]({audio_url})", inline=True)

                background_url = user_data.get('background_url')
                if background_url and background_url.lower() != 'no background':
                    if background_url.lower().endswith(('.mp4', '.avi', '.mov', '.jpg', '.jpeg', '.png', '.gif')):
                        embed.add_field(name="Background", value=f"[Click here]({background_url})", inline=True)

                embed.set_footer(text=f"{user_data['profile_views']} views ● UID {user_data['uid']}", icon_url="https://git.cursi.ng/ammo_logo.png?2")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("User not found.")
        except Exception as e:
            await error_handler(interaction, e)

    @bio.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="The Emogirls.ls username")
    @commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def emogirls(self, interaction: Interaction, username: str):
        """Lookup an emogir.ls user."""
        class EmogirlsView(discord.ui.View):
            def __init__(self, banner_url: str, audio_tracks: list, session: aiohttp.ClientSession, username: str):
                super().__init__(timeout=240)
                self.banner_url = banner_url
                self.audio_tracks = audio_tracks
                self.username = username
                self.session = session
                
                self.banner_button = discord.ui.Button(style=discord.ButtonStyle.blurple, label="Banner", disabled=not bool(banner_url))
                self.banner_button.callback = self.banner_callback
                self.add_item(self.banner_button)
                
                self.audio_button = discord.ui.Button(style=discord.ButtonStyle.blurple, emoji=discord.PartialEmoji.from_str("<:audio:1345517095101923439>"), disabled=not bool(audio_tracks))
                self.audio_button.callback = self.audio_callback
                self.add_item(self.audio_button)
                
                self.details_button = discord.ui.Button(style=discord.ButtonStyle.secondary, label="+")
                self.details_button.callback = self.details_callback
                self.add_item(self.details_button)
            
            async def banner_callback(self, interaction: Interaction):
                await interaction.response.send_message(self.banner_url, ephemeral=True)
            
            async def audio_callback(self, interaction: Interaction):
                class AudioView(discord.ui.View):
                    def __init__(self, audio_tracks: list, interaction: Interaction, session: aiohttp.ClientSession):
                        super().__init__(timeout=60)
                        self.audio_tracks = audio_tracks
                        self.current_page = 0
                        self.interaction = interaction
                        self.session = session
                        self.cached_audio = {}
                        self.update_buttons()
                    
                    def update_buttons(self):
                        self.clear_items()
                        
                        left_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"),
                            style=discord.ButtonStyle.primary,
                            custom_id="robloxleft",
                            disabled=self.current_page <= 0
                        )
                        left_button.callback = self.previous_button
                        self.add_item(left_button)
                        
                        right_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"),
                            style=discord.ButtonStyle.primary,
                            custom_id="robloxright",
                            disabled=self.current_page >= len(self.audio_tracks) - 1
                        )
                        right_button.callback = self.next_button
                        self.add_item(right_button)
                    
                    async def get_audio(self, index: int):
                        if index in self.cached_audio:
                            return self.cached_audio[index]
                        
                        try:
                            async with self.session.get(self.audio_tracks[index]['url']) as resp:
                                if resp.status == 200:
                                    audio_data = await resp.read()
                                    self.cached_audio[index] = audio_data
                                    return audio_data
                                return None
                        except Exception:
                            return None
                    
                    async def send_audio(self):
                        audio_data = await self.get_audio(self.current_page)
                        if audio_data is None:
                            await self.interaction.followup.send("Failed to load audio track.", ephemeral=True)
                            return
                        
                        track_name = self.audio_tracks[self.current_page].get('title', f'audio_{self.current_page}')
                        file = discord.File(io.BytesIO(audio_data), filename=f"{track_name}.mp3")
                        await self.interaction.edit_original_response(attachments=[file], view=self)
                    
                    async def previous_button(self, interaction: Interaction):
                        if interaction.user.id != self.interaction.user.id:
                            await interaction.response.send_message("You cannot interact with someone else's message.", ephemeral=True)
                            return
                        
                        if self.current_page > 0:
                            self.current_page -= 1
                            self.update_buttons()
                            await self.send_audio()
                        await interaction.response.defer()
                    
                    async def next_button(self, interaction: Interaction):
                        if interaction.user.id != self.interaction.user.id:
                            await interaction.response.send_message("You cannot interact with someone else's message.", ephemeral=True)
                            return
                        
                        if self.current_page < len(self.audio_tracks) - 1:
                            self.current_page += 1
                            self.update_buttons()
                            await self.send_audio()
                        await interaction.response.defer()
                    
                    async def on_timeout(self):
                        for item in self.children:
                            item.disabled = True
                        try:
                            await self.interaction.edit_original_response(view=self)
                        except discord.NotFound:
                            pass
                
                view = AudioView(self.audio_tracks, interaction, self.session)
                audio_data = await view.get_audio(0)
                if audio_data is None:
                    await interaction.response.send_message("Failed to load audio track.", ephemeral=True)
                    return
                    
                track_name = self.audio_tracks[0].get('title', 'audio_0')
                file = discord.File(io.BytesIO(audio_data), filename=f"{track_name}.mp3")
                await interaction.response.send_message(file=file, view=view, ephemeral=True)
            
            async def details_callback(self, interaction: Interaction):
                async def fetch_data(url):
                    async with self.session.get(url, headers={'Authorization': f'Bearer {EMOGIRLS_KEY}'}) as resp:
                        return await resp.json() if resp.status == 200 else {}
                
                try:
                    appearance_data, links_data = await asyncio.gather(
                        fetch_data(f'https://emogir.ls/api/v1/{self.username}/appearance'),
                        fetch_data(f'https://emogir.ls/api/v1/{self.username}/links')
                    )
                    
                    embed = await cembed(
                        interaction,
                        title=f"@{self.username}'s customization settings",
                    )
                    
                    if appearance_data:
                        embed.add_field(name="Display Name", value=appearance_data.get('displayName', 'Not set'), inline=False)
                        embed.add_field(name="Bio", value=appearance_data.get('bio', 'Not set')[:1024] or 'Not set', inline=False)
                        embed.add_field(name="Layout Style", value=appearance_data.get('layoutStyle', 'default'), inline=False)
                        embed.add_field(name="Container BG Color", value=appearance_data.get('containerBackgroundColor', '#000000'), inline=False)
                        embed.add_field(name="Glass Effect", value="Enabled" if appearance_data.get('glassEffect', False) else "Disabled", inline=False)
                        
                        if appearance_data.get('audioTracks'):
                            audio_info = "\n".join(f"[{track.get('title', 'Untitled')} ({track.get('icon', '🎵')})]({track['url']})" for track in appearance_data['audioTracks'])
                            embed.add_field(name=f"Audio Tracks ({len(appearance_data['audioTracks'])})", value=audio_info[:1024], inline=False)
                    
                    if links_data:
                        links_info = "\n".join(f"[{link.get('title', 'Untitled')}]({link['url']}) ({link.get('clicks', 0)} clicks)" for link in links_data[:5])
                        embed.add_field(name=f"Links ({len(links_data)})", value=links_info[:1024] or "No links", inline=False)
                    
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message("Failed to fetch details.", ephemeral=True)
            
            async def on_timeout(self):
                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                        item.disabled = True

        try:
            headers = {'Authorization': f'Bearer {EMOGIRLS_KEY}'}
            
            async with self.session.get(f'https://emogir.ls/api/v1/{username}/profile', headers=headers) as resp:
                if resp.status != 200:
                    return await interaction.followup.send("User not found, check out [@c](<https://emogir.ls/c>) tho.")
                profile_data = await resp.json()
            
            async with self.session.get(f'https://emogir.ls/api/v1/{username}/appearance', headers=headers) as resp:
                appearance_data = await resp.json() if resp.status == 200 else {}
            
            display_name = appearance_data.get('displayName', profile_data.get('name', username))
            title = f"{display_name} (@{username})" if display_name != username else username
            
            badges = profile_data.get('badges', [])
            badge_emojis = {
                'PREMIUM': '<:emopremium:1354834643328962717>',
                'VERIFIED': '<:emoverified:1354834780277182537>',
                'OG': '<:emoog:1354834636420944032>',
                'STAFF': '<:emostaff:1354834957448642570>',
                'OWNER': '<:emoowner:1354834970954432543>'
            }
            
            description_parts = []
            for badge in badges:
                if badge in badge_emojis:
                    description_parts.append(badge_emojis[badge])
            
            bio = appearance_data.get('bio', profile_data.get('bio', ''))
            if bio:
                description_parts.append(f"\n-# **{bio}**")
            
            embed = await cembed(
                interaction,
                title=title,
                url=f"https://emogir.ls/{username}",
                description=' '.join(description_parts)[:4096] if description_parts else 'No bio',
            )
            
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            
            avatar_url = appearance_data.get('avatar') or profile_data.get('image')
            if avatar_url:
                embed.set_thumbnail(url=avatar_url)
            
            banner_url = appearance_data.get('banner') or appearance_data.get('backgroundUrl')
            if banner_url and any(banner_url.lower().endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.gif')):
                embed.set_image(url=banner_url)
            
            view = EmogirlsView(
                banner_url=banner_url,
                audio_tracks=appearance_data.get('audioTracks', []),
                session=self.session,
                username=username
            )
            
            await interaction.followup.send(embed=embed, view=view)
        
        except Exception as e:
            await error_handler(interaction, e)

    @minecraft.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.check(permissions.is_blacklisted)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def randomserver(self, interaction: Interaction):
        """Get a random Minecraft server."""

        url = "https://minecraft-mp.com/servers/random/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    def parse_html(html_content):
                        soup = BeautifulSoup(html_content, 'html.parser')
                        return [elem['data-clipboard-text'] for elem in 
                            soup.find_all(attrs={"data-clipboard-text": True})]
                    
                    server_ips = await asyncio.to_thread(parse_html, html)

                    if server_ips:
                        random_ip = random.choice(server_ips)
                        
                        status_url = f"https://api.mcstatus.io/v2/status/java/{random_ip}?query=true"
                        async with self.session.get(status_url) as status_response:
                            if status_response.status == 200:
                                server_data = await status_response.json()
                                online = server_data.get('online', False)
                                
                                if online:
                                    host = server_data.get('host', 'Unknown')
                                    players_online = server_data['players'].get('online', 0)
                                    max_players = server_data['players'].get('max', 0)
                                    motd = server_data['motd'].get('clean', 'Unknown')
                                    version = server_data['version'].get('name_clean', 'Unknown')
                                    icon = server_data.get('icon')

                                    embed = await cembed(interaction, title=f"Random Minecraft Server")
                                    embed.add_field(name="Server IP", value=f"`{random_ip}`", inline=False)
                                    embed.add_field(name="Players Online", value=f"{players_online}/{max_players}", inline=True)
                                    embed.add_field(name="Version", value=version, inline=True)
                                    if motd and motd != "Unknown":
                                        embed.add_field(name="MOTD", value=motd, inline=False)
                                    embed.set_footer(text=footer, icon_url="https://git.cursi.ng/minecraft_logo.png")

                                    if icon:
                                        icon_data = await asyncio.to_thread(lambda: icon.split(",")[1])
                                        icon_bytes = await asyncio.to_thread(lambda: io.BytesIO(base64.b64decode(icon_data)))
                                        file = discord.File(icon_bytes, filename="server_icon.png")
                                        embed.set_thumbnail(url="attachment://server_icon.png")
                                        await interaction.followup.send(embed=embed, file=file)
                                    else:
                                        await interaction.followup.send(embed=embed)
                                else:
                                    await interaction.followup.send("Found a server but it appears to be offline. Try again!")
                            else:
                                await interaction.followup.send("Failed to fetch server status. Try again!")
                    else:
                        await interaction.followup.send("No servers found. Try again!")
                else:
                    await interaction.followup.send("Failed to fetch random server. Try again!")

        except Exception as e:
            await error_handler(interaction, e)

    #@app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="The CashApp username.")
    @commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True, attach_files=True)
    async def cashapp(self, interaction: Interaction, username: str):
        """Get information about a CashApp user."""

        url = 'https://api.phoenixbot.lol/cashapp'
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': '4f7a9c8d1b2e3g5h0k6m7n9p2q4r8s1t'
        }
        payload = {'username': username}

        async with self.session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                try:
                    data = await response.json()
                    display_name = data.get('displayName', 'Unknown')
                    cashtag = f"${data.get('username', 'Unknown')}"
                    rate_plan = data.get('ratePlan', 'Unknown')
                    payment_button_type = data.get('paymentButtonType', 'Unknown')
                    is_verified = "Yes" if data.get('isVerifiedAccount') else "No"
                    pfp = data.get('profilePictureUrl', '')
                    qrcode = data.get('qrCodeUrl', '')

                    embed = Embed(interaction, title=f"CashApp Info for {username}", url=f"https://cash.app/${username}")
                    embed.add_field(name="Cashtag", value=cashtag, inline=True)
                    embed.add_field(name="Display Name", value=display_name, inline=True)
                    embed.add_field(name="Rate Plan", value=rate_plan, inline=True)
                    embed.add_field(name="Payment Button Type", value=payment_button_type, inline=True)
                    embed.add_field(name="Verified Account", value=is_verified, inline=True)
                    embed.set_thumbnail(url=pfp)
                    embed.set_image(url=qrcode)
                    embed.set_footer(text=footer, icon_url="https://git.cursi.ng/cashapp_logo.png")

                    await interaction.followup.send(embed=embed)
                except Exception as e:
                    await error_handler(interaction, e)
            else:
                await interaction.followup.send(f"User does not exist.", ephemeral=True)
                    
async def setup(client):
    await client.add_cog(Socials(client))
