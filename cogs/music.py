import discord
from discord import app_commands, Interaction, InteractionType, Embed, ButtonStyle, ui
from discord.ui import Button, View
from discord.ext import commands, tasks
import aiohttp, asyncio, datetime, time, json, re, io, random, os, base64, subprocess, tempfile
from pydub import AudioSegment
from bs4 import BeautifulSoup
import urllib
from urllib.parse import urlparse, quote
from PIL import Image, ImageDraw, ImageFont
from utils.db import check_donor, get_db_connection, redis_client
from utils.previewhandler import AudioPreviewHandler
from utils.error import error_handler
from utils.embed import cembed
from utils.cache import get_embed_color
from utils.cd import cooldown
from utils import default, permissions
from dotenv import dotenv_values
from typing import Optional, Dict
import calendar
from collections import Counter

footer = "heist.lol"
config = dotenv_values(".env")
API_KEY = config["HEIST_API_KEY"]
LASTFM_KEY = config["LASTFM_API_KEY"]

periods = {
    "7 days": "7day",
    "1 month": "1month",
    "3 months": "3month",
    "6 months": "6month",
    "1 year": "12month",
    "lifetime": "overall"
}

class TopItems(View):
    def __init__(self, interaction: Interaction, session: aiohttp.ClientSession, items, type, display_username, period, total_scrobbles):
        super().__init__(timeout=120)
        self.original_author = interaction.user
        self.interaction = interaction
        self.items = items
        self.type = type
        self.display_username = display_username
        self.period = period
        self.current_page = 0
        self.session = session
        self.items_per_page = 10
        self.total_scrobbles = total_scrobbles
        self.update_button_states()

    def update_button_states(self):
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = ((self.current_page + 1) * self.items_per_page >= len(self.items))

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user != self.original_author:
            await interaction.response.send_message("You cannot interact with someone else's embed.", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.defer()
            self.update_button_states()
            await interaction.response.edit_message(embed=await self.create_embed(), view=self)

    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: Interaction, button: Button):
        if (self.current_page + 1) * self.items_per_page < len(self.items):
            self.current_page += 1
            self.update_button_states()
            await interaction.response.edit_message(embed=await self.create_embed(), view=self)

    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction: Interaction, button: Button):
        class GoToPageModal(discord.ui.Modal, title="Go to Page"):
            page_number = discord.ui.TextInput(label="Navigate to page", placeholder=f"Enter a page number (1-{len(self.items) // self.items_per_page + 1})", min_length=1, max_length=len(str(len(self.items) // self.items_per_page + 1)))

            async def on_submit(self, interaction: Interaction):
                try:
                    page = int(self.page_number.value) - 1
                    if page < 0 or page >= len(self.view.items) // self.view.items_per_page + 1:
                        raise ValueError
                    self.view.current_page = page
                    self.view.update_button_states()
                    await interaction.response.edit_message(embed=await self.view.create_embed(), view=self.view)
                    await interaction.response.defer()
                except ValueError:
                    await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

        modal = GoToPageModal()
        modal.view = self
        await interaction.response.send_modal(modal)

    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: Interaction, button: Button):
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

    async def fetch_artist_image(self, artist_name):
        artist_name_escaped = artist_name.replace(" ", "+")
        spotify_url = f"http://127.0.0.1:2053/api/spotify/artist?artist_name={artist_name_escaped}"
        headers = {"X-API-Key": f"{API_KEY}"}
        async with self.session.get(spotify_url, headers=headers) as spotify_response:
            if spotify_response.status == 200:
                spotify_data = await spotify_response.json()
                return spotify_data.get('cover_art')
        return None

    async def create_embed(self):
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        current_items = self.items[start_idx:end_idx]

        thumbnail_url = ''
        if current_items:
            first_item = current_items[0]

            if self.type == "tracks":
                album_images = first_item.get('album', {}).get('image', [])
                for image in album_images:
                    if image['#text'] and image['size'] == 'large':
                        thumbnail_url = image['#text']
                        break
            elif self.type == "albums":
                images = first_item.get('image', [])
                for image in images:
                    if image['#text'] and image['size'] == 'large':
                        thumbnail_url = image['#text']
                        break
            elif self.type == "artists":
                artist_name = first_item['name']
                thumbnail_url = await self.fetch_artist_image(artist_name)
                if not thumbnail_url:
                    images = first_item.get('image', [])
                    for image in images:
                        if image['#text'] and image['size'] == 'large':
                            thumbnail_url = image['#text']
                            break

        author_name = f"{self.display_username}'s Top {self.type.capitalize()} ({self.period})" if self.display_username != "(hidden)" else f"Top {self.type.capitalize()} ({self.period})"
        author_url = f"https://last.fm/user/{self.display_username}" if self.display_username != "(hidden)" else None

        embed = await cembed(self.interaction)
        embed.set_author(name=author_name, url=author_url, icon_url=self.interaction.user.display_avatar.url)
        embed.set_thumbnail(url=thumbnail_url)

        description = ""
        for i, item in enumerate(current_items, start=start_idx + 1):
            if self.type == "albums" or self.type == "tracks":
                name = item['name']
                artist_name = item['artist']['name']
                playcount = item['playcount']
                artist_url = f"https://www.last.fm/music/{artist_name.replace(' ', '+')}"
                item_url = f"{artist_url}/_/{name.replace(' ', '+')}" if self.type == "tracks" else f"{artist_url}/{name.replace(' ', '+')}"
                description += f"{i}. **[{name}]({item_url})** by [{artist_name}]({artist_url}) - *{playcount} plays*\n"
            
            elif self.type == "artists":
                name = item['name']
                playcount = item['playcount']
                artist_url = f"https://www.last.fm/music/{name.replace(' ', '+')}"
                description += f"{i}. **[{name}]({artist_url})** - *{playcount} plays*\n"

        embed.description = description.strip()
        
        different_items = len(set(item['name'] for item in self.items))
        footer_text = f"Page {self.current_page + 1}/{(len(self.items) + self.items_per_page - 1) // self.items_per_page} • {self.display_username if self.display_username != '(hidden)' else '(hidden)'} has {self.total_scrobbles} scrobbles "
        embed.set_footer(text=footer_text, icon_url="https://git.cursi.ng/lastfm_logo.png")

        return embed

class Music(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.TRACKS_PER_PAGE = 5
        self.FETCH_LIMIT = 50
        self.redis = redis_client
        self.session = aiohttp.ClientSession()
        self.preview_handler = AudioPreviewHandler(self.session)
        self.ctx_addfriend2 = app_commands.ContextMenu(
            name='LastFM: Add Friend',
            callback=self.addfriend2,
        )
        self.ctx_removefriend2 = app_commands.ContextMenu(
            name='LastFM: Remove Friend',
            callback=self.removefriend2,
        )
        self.client.tree.add_command(self.ctx_addfriend2)
        self.client.tree.add_command(self.ctx_removefriend2)

    async def cog_unload(self) -> None:
        self.client.tree.remove_command(self.ctx_addfriend2.name, type=self.ctx_addfriend2.type)
        self.client.tree.remove_command(self.ctx_removefriend2.name, type=self.ctx_removefriend2.type)
        await self.session.close()
        # self.check_presence_task.cancel()

    lastfm = app_commands.Group(
        name="lastfm", 
        description="LastFM related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    friends = app_commands.Group(
        name="friends",
        description="Friends related LastFM commands",
        parent=lastfm 
    )

    top = app_commands.Group(
        name="top",
        description="Stats related LastFM commands",
        parent=lastfm 
    )

    statsfm = app_commands.Group(
        name="statsfm", 
        description="StatsFM related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    @lastfm.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def unset(self, interaction: Interaction):
        """Remove your Last.fm username."""
        user_id = str(interaction.user.id)

        class ConfirmUnsetView(View):
            def __init__(self):
                super().__init__(timeout=60)
                self.message = None

            async def on_timeout(self):
                for item in view.children:
                    if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                        item.disabled = True

                try:
                    await interaction.edit_original_response(view=view)
                except discord.NotFound:
                    pass

            @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
            async def confirm(self, interaction: Interaction, button: Button):
                async with get_db_connection() as conn:
                    try:
                        result = await conn.execute("""
                            DELETE FROM lastfm_usernames
                            WHERE user_id = $1
                        """, user_id)

                        await conn.execute("""
                            DELETE FROM lastfm_friends
                            WHERE user_id = $1 OR friend_id = $1
                        """, user_id)

                        if result == 'DELETE 0':
                            embed = await cembed(interaction, description="You don't have a Last.fm username set.")
                            await interaction.response.edit_message(embed, view=None)
                        else:
                            embed = await cembed(interaction, description="<:check:1344689360527949834> Last.fm username removed successfully.")
                            await interaction.response.edit_message(embed, view=None)
                    except Exception as e:
                        print(f"Failed to remove Last.fm username: {e}")
                    await interaction.response.edit_message(content="An error occurred while removing your Last.fm username. Please try again later.", view=None)

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
            async def cancel(self, interaction: Interaction, button: Button):
                await interaction.response.defer()
                await interaction.delete_original_response()

        view = ConfirmUnsetView()

        timestamp = int(time.time()) + 60
        message_content = (
            "Are you sure you wish to **unset** your username?\n"
            f"This request will expire <t:{timestamp}:R>.\n"
            "-# **This will also remove all LFM friends you have added.**\n"
            "-# **If you only wish to change your username, using </lastfm set:1245774423143874645> is recommended.**\n"
        )
        embed = await cembed(interaction, description=message_content)

        view.message = await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

    @lastfm.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="Your Last.fm username.")
    @app_commands.check(permissions.is_blacklisted)
    async def set(self, interaction: Interaction, username: str):
        """Set your Last.fm username."""
        if len(username) > 15:
            await interaction.response.send_message("Username must be 15 characters or less.", ephemeral=True)
            return

        if not username.replace('_', '').isalnum():
            await interaction.response.send_message("Username can only contain letters, numbers, and underscores.", ephemeral=True)
            return

        if ' ' in username:
            await interaction.response.send_message("Username cannot contain spaces.", ephemeral=True)
            return
        user_id = str(interaction.user.id)
        
        async with get_db_connection() as conn:
            try:
                await conn.execute("""
                    INSERT INTO lastfm_usernames (user_id, lastfm_username)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE
                    SET lastfm_username = EXCLUDED.lastfm_username
                """, user_id, username)

                await conn.execute("""
                    UPDATE lastfm_friends
                    SET friend_lastfm_name = $1
                    WHERE friend_id = $2
                """, username, user_id)

                embed = await cembed(interaction, description=f"<:check:1344689360527949834> [{username}](https://last.fm/user/{username}) has been linked to {interaction.user.mention}.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                print(f"Failed to update Last.fm username: {e}")
                embed = await cembed(interaction, description=f"{interaction.user.mention}: An error occured while linking [{username}](https://last.fm/user/{username}).")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            finally:
                await conn.close()

    @statsfm.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="Your Stats.fm username.")
    @app_commands.check(permissions.is_blacklisted)
    async def set(self, interaction: Interaction, username: str):
        """Set your Stats.fm username."""
        if not username.replace('_', '').isalnum():
            await interaction.response.send_message("Username can only contain letters, numbers, and underscores.", ephemeral=True)
            return

        if ' ' in username:
            await interaction.response.send_message("Username cannot contain spaces.", ephemeral=True)
            return

        user_id = str(interaction.user.id)

        async with get_db_connection() as conn:
            try:
                await conn.execute("""
                    INSERT INTO statsfm_usernames (user_id, statsfm_username)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE
                    SET statsfm_username = EXCLUDED.statsfm_username
                """, user_id, username)

                embed = await cembed(interaction, description=f"<:check:1344689360527949834> [{username}](https://stats.fm/user/{username}) has been linked to {interaction.user.mention}.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                print(f"Failed to update Stats.fm username: {e}")
                embed = await cembed(interaction, description=f"{interaction.user.mention}: An error occurred while linking [{username}](https://stats.fm/user/{username}).")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            finally:
                await conn.close()

    @statsfm.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def unset(self, interaction: Interaction):
        """Remove your Stats.fm username."""
        user_id = str(interaction.user.id)

        class ConfirmUnsetView(View):
            def __init__(self):
                super().__init__(timeout=60)
                self.message = None

            async def on_timeout(self):
                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                        item.disabled = True

                try:
                    await self.message.edit(view=self)
                except discord.NotFound:
                    pass

            @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
            async def confirm(self, interaction: Interaction, button: Button):
                async with get_db_connection() as conn:
                    try:
                        result = await conn.execute("""
                            DELETE FROM statsfm_usernames
                            WHERE user_id = $1
                        """, user_id)

                        if result == 'DELETE 0':
                            embed = await cembed(interaction, description="You don't have a Stats.fm username set.")
                            await interaction.response.edit_message(embed=embed, view=None)
                        else:
                            embed = await cembed(interaction, description="<:check:1344689360527949834> Stats.fm username removed successfully.")
                            await interaction.response.edit_message(embed=embed, view=None)
                    except Exception as e:
                        print(f"Failed to remove Stats.fm username: {e}")
                        embed = await cembed(interaction, description="An error occurred while removing your Stats.fm username. Please try again later.")
                        await interaction.response.edit_message(embed=embed, view=None)

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
            async def cancel(self, interaction: Interaction, button: Button):
                await interaction.response.defer()
                await interaction.delete_original_response()

        view = ConfirmUnsetView()

        timestamp = int(time.time()) + 60
        message_content = (
            "Are you sure you wish to **unset** your Stats.fm username?\n"
            f"This request will expire <t:{timestamp}:R>.\n"
            "-# **If you only wish to change your username, using </statsfm set:1344800027184332870> is recommended.**\n"
        )
        embed = await cembed(interaction, description=message_content)

        view.message = await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

    @statsfm.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="Your Stats.fm username.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def profile(self, interaction: discord.Interaction, username: str = None):
        "View Stats.fm profile."
        try:
            user_id = str(interaction.user.id)
            headers = {"User-Agent": "Heist Bot/1.0"}
            
            if not username:
                async with get_db_connection() as conn:
                    statsfm_username = await conn.fetchval("SELECT statsfm_username FROM statsfm_usernames WHERE user_id = $1", user_id)
                    if not statsfm_username:
                        await interaction.followup.send(f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your Stats.fm username yet. Use </statsfm set:1344800027184332870> to set it.")
                        return
            else:
                statsfm_username = username
                
            async with self.session.get(f"https://api.stats.fm/api/v1/users/{statsfm_username}/", headers=headers) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"Couldn't find a Stats.fm profile with the username '{statsfm_username}'.")
                    return
                user_data = await resp.json()
                    
            async with self.session.get(f"https://api.stats.fm/api/v1/users/{statsfm_username}/streams/stats", headers=headers) as resp:
                if resp.status != 200:
                    await interaction.followup.send("Failed to get stream statistics.")
                    return
                stats_data = await resp.json()
            
            async with self.session.get(f"https://api.stats.fm/api/v1/users/{statsfm_username}/streams/current", headers=headers) as resp:
                current_data = await resp.json()
                
            if current_data.get("item") is None or not current_data["item"].get("isPlaying", False):
                user_id = user_data["item"]["id"]
                async with self.session.get(f"https://api.stats.fm/api/v1/users/{user_id}/streams/recent", headers=headers) as resp:
                    if resp.status == 200:
                        recent_data = await resp.json()
                    else:
                        recent_data = {"items": []}
            
            user_info = user_data["item"]
            display_name = user_info["displayName"]
            custom_id = user_info["customId"]
            profile_image = user_info["image"]
            is_plus = user_info["isPlus"]
            is_pro = user_info["isPro"]
            
            title = display_name
            if is_plus:
                title += " ✨"
            if is_pro:
                title += " 🌟"
            
            embed = await cembed(
                interaction,
                title=title,
                url=f"https://stats.fm/{custom_id}"
            )
            
            embed.set_author(
                name=f"{interaction.user.display_name} · @{custom_id}",
                icon_url=interaction.user.display_avatar.url,
                url=f"https://stats.fm/{custom_id}"
            )
            
            embed.set_thumbnail(url=profile_image)
            
            description = ""
            if user_info.get("spotifyAuth"):
                spotify_info = user_info["spotifyAuth"]
                spotify_display_name = spotify_info["displayName"]
                spotify_id = spotify_info["platformUserId"]
                sync_status = "Enabled" if spotify_info["sync"] else "Disabled"
                import_status = "Imported" if spotify_info["imported"] else "Not imported"
                
                description = f"<:spotify:1274904265114124308> [`{spotify_display_name}`](https://open.spotify.com/user/{spotify_id})\nSync Status: `{sync_status}`\nImport Status: `{import_status}`"
                
                if user_info.get("profile") and user_info["profile"].get("bio"):
                    bio = user_info["profile"]["bio"]
                    bio = re.sub(r'https?://(www\.)?([^\s]+)', r'[\2](https://\2)', bio)
                    description += f"\n{bio}"
                    
            embed.description = description
            
            if "items" in stats_data:
                stats = stats_data["items"]
                streams_count = stats["count"]
                minutes_streamed = int(stats["durationMs"] / 60000)
                hours_streamed = int(minutes_streamed / 60)
                unique_tracks = stats["cardinality"]["tracks"]
                unique_artists = stats["cardinality"]["artists"]
                unique_albums = stats["cardinality"]["albums"]
                
                stats_value = f"```ansi\n\u001b[0;33m{streams_count:,}\u001b[0m streams\n\u001b[0;33m{minutes_streamed:,}\u001b[0m minutes streamed\n\u001b[0;33m{hours_streamed:,}\u001b[0m hours streamed\n\u001b[0;33m{unique_tracks:,}\u001b[0m unique tracks\n\u001b[0;33m{unique_artists:,}\u001b[0m unique artists\n\u001b[0;33m{unique_albums:,}\u001b[0m unique albums```"
                
                embed.add_field(name="Stats", value=stats_value, inline=False)
            
            current_track = None
            if current_data.get("item"):
                track_info = current_data["item"]
                track_name = track_info["track"]["name"]
                artist_name = track_info["track"]["artists"][0]["name"]
                track_id = track_info["track"]["id"]
                timestamp = int(time.mktime(time.strptime(track_info["date"], "%Y-%m-%dT%H:%M:%S.%fZ")))
                
                album_name = "Unknown Album"
                if track_info["track"]["albums"]:
                    album_name = track_info["track"]["albums"][0]["name"]
                    
                if track_info.get("isPlaying", False):
                    embed.add_field(
                        name="Now Playing",
                        value=f"[{track_name}](https://stats.fm/track/{track_id}) by **{artist_name}**\non *{album_name}*",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Now Playing (Paused)",
                        value=f"[{track_name}](https://stats.fm/track/{track_id}) by **{artist_name}**\non *{album_name}*",
                        inline=False
                    )
                current_track = track_info["track"]
            elif recent_data.get("items") and len(recent_data["items"]) > 0:
                track_info = recent_data["items"][0]
                track_name = track_info["track"]["name"]
                artist_name = track_info["track"]["artists"][0]["name"]
                track_id = track_info["track"]["id"]
                timestamp = int(time.mktime(time.strptime(track_info["endTime"], "%Y-%m-%dT%H:%M:%S.%fZ")))
                
                album_name = "Unknown Album"
                if track_info["track"]["albums"]:
                    album_name = track_info["track"]["albums"][0]["name"]
                    
                embed.add_field(
                    name="Last Listened",
                    value=f"[{track_name}](https://stats.fm/track/{track_id}) by **{artist_name}**\n<t:{timestamp}:R>\non *{album_name}*",
                    inline=False
                )
                current_track = track_info["track"]
            
            embed.set_footer(
                text=f"{footer} · {display_name}",
                icon_url="https://git.cursi.ng/statsfm_logo.png"
            )
            
            class ProfileView(discord.ui.View):
                def __init__(self, interaction: discord.Interaction, session: aiohttp.ClientSession, has_audio: bool):
                    super().__init__(timeout=240)
                    self.interaction = interaction
                    self.message = None
                    self.session = session
                    self.has_audio = has_audio
                    self.preview_handler = AudioPreviewHandler(session)

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:audio:1345517095101923439>"), style=discord.ButtonStyle.secondary, custom_id="profileaudio", disabled=True)
                async def audio_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer(ephemeral=True)
                    preview_url = await self.preview_handler.get_preview(track_data=current_track)
                    if preview_url:
                        await self.preview_handler.send_preview(interaction, preview_url)
                    else:
                        await interaction.followup.send("No audio preview available", ephemeral=True)

                async def on_timeout(self):
                    for item in self.children:
                        if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                            item.disabled = True

                    try:
                        await self.message.edit(view=self)
                    except discord.NotFound:
                        pass

            has_audio = False
            if current_track:
                preview_url = current_track.get('spotifyPreview') or current_track.get('appleMusicPreview')
                has_audio = bool(preview_url)

            view = ProfileView(interaction, self.session, has_audio)
            if has_audio:
                for item in view.children:
                    if isinstance(item, discord.ui.Button) and item.custom_id == "profileaudio":
                        item.disabled = False

            await interaction.followup.send(embed=embed, view=view)
            view.message = await interaction.original_response()
        except Exception as e:
            await error_handler(interaction, e)

    @statsfm.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="Your Stats.fm username.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True, attach_files=True)
    async def nowplaying(self, interaction: discord.Interaction, username: str = None):
        """Get the current playing track on Stats.fm."""
        user_id = str(interaction.user.id)

        if not username:
            async with get_db_connection() as conn:
                statsfm_username = await conn.fetchval("SELECT statsfm_username FROM statsfm_usernames WHERE user_id = $1", user_id)
                if not statsfm_username:
                    await interaction.followup.send(f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your Stats.fm username yet.")
                    return
        else:
            statsfm_username = username

        try:
            headers = {"User-Agent": "Heist Bot/1.0"}
            is_playing = True
            last_seen = None
            current_track = None
            
            async with self.session.get(
                f"https://api.stats.fm/api/v1/users/{statsfm_username}/streams/current",
                headers=headers
            ) as response:
                if response.status == 404:
                    await interaction.followup.send(f"Could not find Stats.fm user with username `{statsfm_username}`.")
                    return
                elif response.status == 409:
                    await interaction.followup.send("Please re-link your Spotify to the Stats.fm account you're using.")
                    return
                elif response.status != 200:
                    await interaction.followup.send("The Stats.fm API is currently unavailable.")
                    return
                data = await response.json()

            if not data or not isinstance(data.get('item'), dict):
                is_playing = False
                async with self.session.get(
                    f"https://api.stats.fm/api/v1/users/{statsfm_username}/streams/recent",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        await interaction.followup.send(f"{interaction.user.mention}: You're currently not listening to something.")
                        return
                    recent_data = await response.json()
                    
                    if not recent_data or not recent_data.get('items') or not recent_data['items']:
                        await interaction.followup.send(f"{interaction.user.mention}: No recent listening activity found.")
                        return
                    
                    item = recent_data['items'][0]
                    current_track = item.get('track')
                    end_time = item.get('endTime')
                    
                    if end_time:
                        end_datetime = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                        now = datetime.datetime.now(datetime.timezone.utc)
                        time_diff = now - end_datetime
                        
                        minutes = int(time_diff.total_seconds() / 60)
                        hours = int(minutes / 60)
                        days = int(hours / 24)
                        months = int(days / 30)
                        years = int(days / 365)
                        
                        if years > 0:
                            last_seen = f"{years} year{'s' if years != 1 else ''} ago"
                        elif months > 0:
                            last_seen = f"{months} month{'s' if months != 1 else ''} ago"
                        elif days > 0:
                            last_seen = f"{days} day{'s' if days != 1 else ''} ago"
                        elif hours > 0:
                            last_seen = f"{hours} hour{'s' if hours != 1 else ''} ago"
                        else:
                            last_seen = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            else:
                current_track = data['item'].get('track')
                is_playing = data['item'].get('isPlaying', False)
                
            if not current_track:
                await interaction.followup.send(f"{interaction.user.mention}: Failed to get track information.")
                return

            song_name = current_track['name']
            artist_name = current_track['artists'][0]['name']
            album_name = current_track['albums'][0]['name']
            cover_url = current_track['albums'][0].get('image', None)
            
            if is_playing:
                progress_ms = data['item']['progressMs']
                duration_ms = current_track['durationMs']
                device_name = data['item']['deviceName']
                platform = data['item']['platform'].capitalize()
            else:
                progress_ms = current_track['durationMs']
                duration_ms = current_track['durationMs']

            if cover_url:
                async with self.session.get(cover_url) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()

                        def process_image(data):
                            image = Image.open(io.BytesIO(data))
                            image = image.resize((50, 50))
                            image = image.convert("RGB")
                            dominant_color = image.getpixel((0, 0))
                            return (dominant_color[0] << 16) + (dominant_color[1] << 8) + dominant_color[2]

                        gyat = await asyncio.to_thread(process_image, image_data)
                    else:
                        gyat = await get_embed_color(str(interaction.user.id))
            else:
                gyat = await get_embed_color(str(interaction.user.id))

            progress_bar_task = asyncio.create_task(self.create_progress_bar(gyat, progress_ms, duration_ms))
            
            display_name = None
            async with self.session.get(
                f"https://api.stats.fm/api/v1/users/{statsfm_username}/",
                headers=headers
            ) as response:
                if response.status == 200:
                    user_data = await response.json()
                    if user_data and isinstance(user_data.get('item'), dict):
                        display_name = user_data['item'].get('displayName', statsfm_username)
            
            spotify_id = None
            for ext_id in current_track.get('externalIds', {}).get('spotify', []):
                if ext_id:
                    spotify_id = ext_id
                    break
                    
            spotify_url = f"https://open.spotify.com/track/{spotify_id}" if spotify_id else None
            artist_url = f"https://stats.fm/artist/{current_track['artists'][0]['id']}"
            album_url = f"https://stats.fm/album/{current_track['albums'][0]['id']}"

            description = f"-# [{artist_name}]({artist_url}) • [*{album_name}*]({album_url})"
            
            if is_playing:
                progress = f"{progress_ms//60000}:{str(progress_ms//1000%60).zfill(2)}"
                duration = f"{duration_ms//60000}:{str(duration_ms//1000%60).zfill(2)}"
                description += f"\n-# **`{progress}/{duration}`**"
                if device_name:
                    description += f"\n-# on 📱 **{device_name}**"
            else:
                description += f"\n-# **Paused**" if not last_seen else f"\n-# **Last seen {last_seen}**"

            embed = discord.Embed(title=f"**{song_name}**", description=description, color=gyat)
            if cover_url:
                embed.set_thumbnail(url=cover_url)
            embed.set_author(name=f"{interaction.user.name} · @{statsfm_username}", icon_url=interaction.user.display_avatar.url, url=f"https://stats.fm/user/{statsfm_username}")
            embed.set_image(url="attachment://progress.png")
            embed.set_footer(text=f"{footer} · {display_name or statsfm_username}", icon_url="https://git.cursi.ng/statsfm_logo.png")
            
            if spotify_url:
                embed.url = spotify_url
            
            spotify_preview = current_track.get('spotifyPreview')
            apple_preview = current_track.get('appleMusicPreview')
            has_audio = bool(spotify_preview or apple_preview)

            class NowPlayingView(discord.ui.View):
                def __init__(self, interaction: discord.Interaction, session: aiohttp.ClientSession, has_audio: bool, spotify_url: str):
                    super().__init__(timeout=360)
                    self.interaction = interaction
                    self.message = None
                    self.session = session
                    self.has_audio = has_audio
                    self.spotify_url = spotify_url
                    self.preview_handler = AudioPreviewHandler(session)

                    if self.spotify_url:
                        self.add_item(discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:spotify:1274904265114124308>"),
                            style=discord.ButtonStyle.link,
                            url=self.spotify_url,
                            row=0
                        ))

                    self.add_item(discord.ui.Button(
                        emoji=discord.PartialEmoji.from_str("<:audio:1345517095101923439>"),
                        style=discord.ButtonStyle.secondary,
                        custom_id="nowplayingaudio",
                        disabled=not self.has_audio,
                        row=0
                    ))

                async def interaction_check(self, interaction: discord.Interaction) -> bool:
                    if interaction.data["custom_id"] == "nowplayingaudio":
                        await self.audio_button(interaction)
                    return True

                async def audio_button(self, interaction: discord.Interaction):
                    await interaction.response.defer(ephemeral=True)
                    preview_url = spotify_preview or apple_preview
                    if preview_url:
                        await self.preview_handler.send_preview(interaction, preview_url)
                    else:
                        await interaction.followup.send("No audio preview available", ephemeral=True)

                async def on_timeout(self):
                    for item in self.children:
                        if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                            item.disabled = True
                    try:
                        await self.message.edit(view=self)
                    except discord.NotFound:
                        pass

            view = NowPlayingView(interaction, self.session, has_audio, spotify_url)
            progress_bar = await progress_bar_task
            message = await interaction.followup.send(file=progress_bar, embed=embed, view=view)
            view.message = message

        except Exception as e:
            await error_handler(interaction, e)

    async def create_progress_bar(self, gyat: str, progress_ms: int, duration_ms: int):
        async def _create_image():
            def _render():
                width, height = 300, 10
                image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(image)
                red, green, blue = (gyat >> 16) & 255, (gyat >> 8) & 255, gyat & 255
                progress = progress_ms / duration_ms if duration_ms > 0 else 1
                progress_width = int(width * progress)
                draw.rectangle([(0, 0), (width, height)], fill=(255, 255, 255, 50))
                draw.rectangle([(0, 0), (progress_width, height)], fill=(red, green, blue, 255))
                
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                return discord.File(img_byte_arr, 'progress.png')
            
            return await asyncio.to_thread(_render)
        
        return await _create_image()

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def addfriend2(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self.lastfmaddfriend(interaction, user)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def removefriend2(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self.lastfmremovefriend(interaction, user)

    @friends.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user you want to add as a Last.fm friend.")
    @app_commands.check(permissions.is_blacklisted)
    async def add(self, interaction: discord.Interaction, user: discord.User) -> None:
        """Add someone as a Last.fm friend."""
        await self.lastfmaddfriend(interaction, user)

    async def lastfmaddfriend(self, interaction: discord.Interaction, user: discord.User):
            await interaction.response.defer(thinking=True, ephemeral=True)
            
            user_id = str(interaction.user.id)
            friend_id = str(user.id)
            
            if user_id == friend_id:
                await interaction.followup.send("You cannot add yourself as a friend!", ephemeral=True)
                return

            async with get_db_connection() as conn:
                try:
                    visibility_result = await conn.fetchrow(
                        "SELECT lastfm_state FROM settings WHERE user_id = $1",
                        friend_id
                    )
                    friend_visibility = visibility_result['lastfm_state'] if visibility_result else 'Show'
                    
                    if friend_visibility == 'Hide':
                        await interaction.followup.send(
                            f"{user.name} has their Last.fm hidden, you can't add them.",
                            ephemeral=True
                        )
                        return

                    user_result = await conn.fetchrow(
                        "SELECT lastfm_username FROM lastfm_usernames WHERE user_id = $1",
                        user_id
                    )
                    friend_result = await conn.fetchrow(
                        "SELECT lastfm_username FROM lastfm_usernames WHERE user_id = $1",
                        friend_id
                    )

                    if not user_result:
                        await interaction.followup.send(
                            f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your Last.fm username yet. Use </lastfm set:1245774423143874645> to set it first.",
                            ephemeral=True
                        )
                        return

                    if not friend_result:
                        await interaction.followup.send(
                            f"{user.name} hasn't linked their Last.fm account with Heist.",
                            ephemeral=True
                        )
                        return

                    existing_friend = await conn.fetchrow(
                        "SELECT 1 FROM lastfm_friends WHERE user_id = $1 AND friend_id = $2",
                        user_id, friend_id
                    )

                    if existing_friend:
                        await interaction.followup.send(
                            f"You're already friends with {user.name} on Last.fm!",
                            ephemeral=True
                        )
                        return

                    await conn.execute("""
                        INSERT INTO lastfm_friends (user_id, friend_id)
                        VALUES ($1, $2)
                    """, user_id, friend_id)

                    await interaction.followup.send(
                        f"Successfully added {user.name} as a Last.fm friend!",
                        ephemeral=True
                    )

                except Exception as e:
                    print(f"Database error while adding friend: {e}")
                    await interaction.followup.send(
                        "An error occurred while adding your friend. Please try again later.",
                        ephemeral=True
                    )
                finally:
                    await conn.close()

    @friends.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user you want to remove as a Last.fm friend.")
    @app_commands.check(permissions.is_blacklisted)
    async def remove(self, interaction: discord.Interaction, user: discord.User) -> None:
        """Remove a user from your Last.fm friends list."""
        await self.lastfmremovefriend(interaction, user)

    async def lastfmremovefriend(self, interaction: discord.Interaction, user: discord.User) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        user_id = str(interaction.user.id)
        friend_id = str(user.id)
        
        if user_id == friend_id:
            await interaction.followup.send("You cannot remove yourself as a friend!", ephemeral=True)
            return

        async with get_db_connection() as conn:
            try:
                friend = await conn.fetchrow("""
                    SELECT 1 
                    FROM lastfm_friends
                    WHERE user_id = $1 AND friend_id = $2
                """, user_id, friend_id)

                if not friend:
                    await interaction.followup.send(
                        f"{user.name} is not in your Last.fm friends list!",
                        ephemeral=True
                    )
                    return

                await conn.execute("""
                    DELETE FROM lastfm_friends
                    WHERE user_id = $1 AND friend_id = $2
                """, user_id, friend_id)

                await interaction.followup.send(
                    f"Successfully removed {user.name} from your Last.fm friends!",
                    ephemeral=True
                )

            except Exception as e:
                print(f"Database error while removing friend: {e}")
                await interaction.followup.send(
                    "An error occurred while removing your friend. Please try again later.",
                    ephemeral=True
                )
            finally:
                await conn.close()

    @friends.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def list(self, interaction: discord.Interaction):
        """View your Last.fm friends list."""
        user_id = str(interaction.user.id)
        async with get_db_connection() as conn:
            try:
                friends = await conn.fetch("""
                    SELECT 
                        f.friend_id, 
                        lf.lastfm_username,
                        COALESCE(s.lastfm_state, 'Show') as visibility
                    FROM lastfm_friends f
                    JOIN lastfm_usernames lf ON f.friend_id = lf.user_id
                    LEFT JOIN settings s ON f.friend_id = s.user_id
                    WHERE f.user_id = $1
                """, user_id)

                if not friends:
                    await interaction.followup.send(
                        "You haven't added any Last.fm friends yet! Use </lastfm friends add:1245774423143874645> to add friends.",
                        ephemeral=True
                    )
                    return

                class PaginationView(discord.ui.View):
                    def __init__(self, total_pages: int, user: discord.User):
                        super().__init__(timeout=300)
                        self.current_page = 1
                        self.total_pages = total_pages
                        self.user = user
                        self.update_button_states()

                    async def interaction_check(self, interaction: discord.Interaction) -> bool:
                        if interaction.user != self.user:
                            await interaction.response.send_message(
                                "You cannot interact with someone else's embed.", ephemeral=True
                            )
                            return False
                        return True

                    def update_button_states(self):
                        self.prev_page_button.disabled = self.current_page == 1
                        self.next_page_button.disabled = self.current_page == self.total_pages

                    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary)
                    async def prev_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        self.current_page = max(1, self.current_page - 1)
                        self.update_button_states()
                        await self.update_page(interaction)

                    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary)
                    async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        self.current_page = min(self.total_pages, self.current_page + 1)
                        self.update_button_states()
                        await self.update_page(interaction)

                    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary)
                    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        class GoToPageModal(discord.ui.Modal, title="Go to Page"):
                            page_number = discord.ui.TextInput(label="Navigate to page", placeholder=f"Enter a page number (1-{self.total_pages})", min_length=1, max_length=len(str(self.total_pages)))

                            async def on_submit(self, interaction: discord.Interaction):
                                try:
                                    page = int(self.page_number.value)
                                    if page < 1 or page > self.view.total_pages:
                                        raise ValueError
                                    self.view.current_page = page
                                    self.view.update_button_states()
                                    await self.view.update_page(interaction)
                                    await interaction.response.defer()
                                except ValueError:
                                    await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

                        modal = GoToPageModal()
                        modal.view = self
                        await interaction.response.send_modal(modal)

                    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger)
                    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        await interaction.response.defer()
                        await interaction.delete_original_response()

                    async def on_timeout(self):
                        for item in view.children:
                            if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                                item.disabled = True

                        try:
                            await interaction.edit_original_response(view=view)
                        except discord.NotFound:
                            pass

                    async def update_page(self, interaction: discord.Interaction):
                        start = (self.current_page - 1) * 10
                        end = start + 10
                        friend_list = []
                        
                        for friend in friends[start:end]:
                            friend_user = await interaction.client.fetch_user(int(friend['friend_id']))
                            discord_link = f"[{friend_user.name}](discord://-/users/{friend_user.id})"
                            lastfm_link = (f"[@{friend['lastfm_username']}](https://www.last.fm/user/{friend['lastfm_username']})" 
                                        if friend['visibility'] != 'Hide' else "hidden")
                            friend_list.append((friend_user.name.lower(), f"• {discord_link} ({lastfm_link})"))
                        
                        friend_list.sort(key=lambda x: x[0])
                        friend_list = [x[1] for x in friend_list]

                        embed = await cembed(
                            interaction,
                            title="Your Last.fm Friends",
                            description="\n".join(friend_list)
                        )
                        embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
                        embed.set_footer(
                            text=f"Total friends: {len(friends)} (Page {self.current_page}/{self.total_pages})",
                            icon_url="https://git.cursi.ng/lastfm_logo.png"
                        )
                        
                        await interaction.response.edit_message(embed=embed, view=self)

                friend_data = []
                for friend in friends:
                    friend_user = await interaction.client.fetch_user(int(friend['friend_id']))
                    discord_link = f"[{friend_user.name}](discord://-/users/{friend_user.id})"
                    lastfm_link = (f"[@{friend['lastfm_username']}](https://www.last.fm/user/{friend['lastfm_username']})" 
                                if friend['visibility'] != 'Hide' else "hidden")
                    friend_data.append((friend_user.name.lower(), f"• {discord_link} ({lastfm_link})"))

                friend_data.sort(key=lambda x: x[0])
                friends = friend_data

                initial_friend_list = [x[1] for x in friends[:10]]

                initial_embed = await cembed(
                    interaction,
                    title="Your Last.fm Friends",
                    description="\n".join(initial_friend_list)
                    )
                initial_embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
                
                total_pages = (len(friends) + 9) // 10
                initial_embed.set_footer(
                    text=f"Total friends: {len(friends)}" + (f" (Page 1/{total_pages})" if total_pages > 1 else ""),
                    icon_url="https://git.cursi.ng/lastfm_logo.png"
                )

                class EmptyView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=120)

                view = PaginationView(total_pages, interaction.user) if total_pages > 1 else EmptyView()
                await interaction.followup.send(embed=initial_embed, view=view)

            except Exception as e:
                print(f"Database error while fetching friends: {e}")
                await interaction.followup.send(
                    "An error occurred while fetching your friends list. Please try again later.",
                    ephemeral=True
                )
            except Exception as e:
                print(e)
                await error_handler(interaction, e)
            finally:
                await conn.close()

    @lastfm.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="Your Last.fm username.")
    @permissions.requires_perms(embed_links=True)
    @app_commands.check(permissions.is_blacklisted)
    async def nowplaying(self, interaction: discord.Interaction, username: str = None):
        """Get the current playing track on Last.fm."""
        user_id = str(interaction.user.id)
        async with get_db_connection() as conn:
            try:
                result = await conn.fetchrow(
                    "SELECT l.lastfm_username, s.lastfm_state "
                    "FROM lastfm_usernames l "
                    "LEFT JOIN settings s ON l.user_id = s.user_id "
                    "WHERE l.user_id = $1", 
                    user_id
                )
                
                if username is None:
                    if not result or not result['lastfm_username']:
                        await interaction.followup.send(
                            f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your Last.fm username yet. Use </lastfm set:1245774423143874645> to set it.",
                            ephemeral=True
                        )
                        return
                    
                    lastfm_username = result['lastfm_username']
                    lastfm_visibility = result.get('lastfm_state', 'Show')
                else:
                    lastfm_username = username
                    lastfm_visibility = 'Show'
                
                display_username = interaction.user.name if lastfm_visibility == 'Hide' else lastfm_username
                user_url = None if lastfm_visibility == 'Hide' else f"https://last.fm/user/{lastfm_username}"

                api_key = f"{LASTFM_KEY}"
                user_info_url = f"http://ws.audioscrobbler.com/2.0/?method=user.getinfo&user={lastfm_username}&api_key={api_key}&format=json"
                recent_tracks_url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={lastfm_username}&api_key={api_key}&format=json&limit=1"

                try:
                    user_info_response, recent_tracks_response = await asyncio.gather(
                        self.session.get(user_info_url),
                        self.session.get(recent_tracks_url)
                    )

                    if user_info_response.status != 200:
                        await interaction.followup.send("User not found. Make sure you set the right one.", ephemeral=True)
                        return

                    user_data = await user_info_response.json()
                    if 'user' not in user_data:
                        await interaction.followup.send("Invalid user data received from Last.fm", ephemeral=True)
                        return

                    total_scrobbles = user_data['user'].get('playcount', 'Not available')
                    country = user_data['user'].get('country', 'Not available')
                    large_avatar_url = next((image.get('#text') for image in user_data['user'].get('image', []) if image.get('size') == 'extralarge'), None)
                    av = large_avatar_url if lastfm_visibility == 'Show' and large_avatar_url else interaction.user.display_avatar.url

                    if recent_tracks_response.status != 200:
                        await interaction.followup.send(f"Failed to fetch recent tracks. Status code: {recent_tracks_response.status}", ephemeral=True)
                        return

                    tracks_data = await recent_tracks_response.json()
                    if 'recenttracks' not in tracks_data:
                        await interaction.followup.send("No track data received from Last.fm", ephemeral=True)
                        return

                    tracks = tracks_data['recenttracks'].get('track', [])
                    if not tracks:
                        await interaction.followup.send("No recently played tracks found.", ephemeral=True)
                        return

                    now_playing = tracks[0]
                    is_now_playing = '@attr' in now_playing and 'nowplaying' in now_playing['@attr'] and now_playing['@attr']['nowplaying'] == 'true'

                    artist_name = now_playing['artist'].get('#text', 'Unknown Artist')
                    track_name = now_playing.get('name', 'Unknown Track')
                    album_name = now_playing['album'].get('#text', '')
                    track_url = now_playing.get('url', '')

                    artistenc = urllib.parse.quote(artist_name)
                    trackenc = urllib.parse.quote(track_name)
                    albumenc = urllib.parse.quote(album_name) if album_name else ''

                    track_info_url = f"http://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key={api_key}&artist={artistenc}&track={trackenc}&username={lastfm_username}&format=json&limit=1"
                    album_info_url = f"http://ws.audioscrobbler.com/2.0/?method=album.getInfo&api_key={api_key}&artist={artistenc}&album={albumenc}&username={lastfm_username}&format=json&limit=1" if album_name else None
                    artist_info_url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getInfo&api_key={api_key}&artist={artistenc}&username={lastfm_username}&format=json&limit=1"

                    responses = await asyncio.gather(
                        self.session.get(track_info_url),
                        self.session.get(album_info_url) if album_info_url else asyncio.sleep(0),
                        self.session.get(artist_info_url)
                    )

                    track_info_response = responses[0]
                    album_info_response = responses[1] if album_name else None
                    artist_info_response = responses[2]

                    track_scrobbles = 0
                    album_scrobbles = 0
                    artist_scrobbles = 0

                    response_data = await asyncio.gather(
                        track_info_response.json() if track_info_response.status == 200 else asyncio.sleep(0),
                        album_info_response.json() if album_info_response and album_info_response.status == 200 else asyncio.sleep(0),
                        artist_info_response.json() if artist_info_response.status == 200 else asyncio.sleep(0)
                    )

                    track_data = response_data[0] if track_info_response.status == 200 else {}
                    album_data = response_data[1] if album_info_response and album_info_response.status == 200 else {}
                    artist_data = response_data[2] if artist_info_response.status == 200 else {}

                    if 'track' in track_data:
                        track_scrobbles = max(0, int(track_data['track'].get('userplaycount', '0')))

                    if 'album' in album_data:
                        album_scrobbles = max(0, int(album_data['album'].get('userplaycount', '0')))

                    if 'artist' in artist_data:
                        artist_stats = artist_data['artist'].get('stats', {})
                        artist_scrobbles = max(0, int(artist_stats.get('userplaycount', '0')))

                    spotify_data = await self.client.socials.search_spotify_track(track_name, artist_name) if self.client.socials else {}
                    spotify_track_url = spotify_data.get('spotify_link')
                    cover_art_url = spotify_data.get('cover_art') or next((image.get('#text') for image in now_playing.get('image', []) if image.get('size') == 'extralarge'), None)

                    preview_handler = AudioPreviewHandler(self.session)
                    preview_url = await preview_handler.get_preview(track_name=track_name, artist_name=artist_name)

                    scrobble_info = f"{track_scrobbles} track scrobble{'s' if track_scrobbles != 1 else ''}"
                    if album_name:
                        scrobble_info += f" · {album_scrobbles} album scrobble{'s' if album_scrobbles != 1 else ''}\n"
                    scrobble_info += f"{artist_scrobbles} artist scrobble{'s' if artist_scrobbles != 1 else ''}"
                    scrobble_info += f" · {total_scrobbles} total scrobble{'s' if total_scrobbles != 1 else ''}"

                    scrobble_info2 = f"-# **{track_scrobbles}** track scrobble{'s' if track_scrobbles != 1 else ''}"
                    if album_name:
                        scrobble_info2 += f" · **{album_scrobbles}** album scrobble{'s' if album_scrobbles != 1 else ''}\n"
                    scrobble_info2 += f"-# **{artist_scrobbles}** artist scrobble{'s' if artist_scrobbles != 1 else ''}"
                    scrobble_info2 += f" · **{total_scrobbles}** total scrobble{'s' if total_scrobbles != 1 else ''}"

                    artist_url = f"https://www.last.fm/music/{artistenc}"
                    album_url = f"https://www.last.fm/music/{artistenc}/{albumenc}" if album_name else None
                    now_playing_description = f"[{artist_name}]({artist_url})"
                    if album_name:
                        now_playing_description += f" • [*{album_name}*]({album_url})"

                    embed_color = None
                    if cover_art_url:
                        async with self.session.get(cover_art_url) as resp:
                            if resp.status == 200:
                                image_data = await resp.read()

                                def process_image(data):
                                    image = Image.open(io.BytesIO(data))
                                    image = image.resize((50, 50))
                                    image = image.convert("RGB")
                                    dominant_color = image.getpixel((0, 0))
                                    return (dominant_color[0] << 16) + (dominant_color[1] << 8) + dominant_color[2]

                                embed_color = await asyncio.to_thread(process_image, image_data)

                    embed = await cembed(interaction, title=f"{track_name}", description=now_playing_description, color=embed_color)
                    embed.set_author(
                        name=f"Now playing · {display_username}" if is_now_playing else f"Last track for {display_username}",
                        icon_url=av,
                        url=user_url
                    )
                    embed.set_footer(text=f"{scrobble_info}", icon_url="https://git.cursi.ng/lastfm_logo.png")
                    embed.url = track_url
                    if cover_art_url:
                        embed.set_thumbnail(url=cover_art_url)

                    class NowPlayingView(discord.ui.View):
                        def __init__(self, interaction: discord.Interaction, session: aiohttp.ClientSession, has_audio: bool, spotify_track_url: str):
                            super().__init__(timeout=360)
                            self.interaction = interaction
                            self.message = None
                            self.session = session
                            self.has_audio = has_audio
                            self.spotify_track_url = spotify_track_url
                            self.preview_handler = AudioPreviewHandler(session)

                            if self.spotify_track_url:
                                self.add_item(discord.ui.Button(
                                    emoji=discord.PartialEmoji.from_str("<:spotify:1274904265114124308>"),
                                    style=discord.ButtonStyle.link,
                                    url=self.spotify_track_url,
                                    row=0
                                ))
                            

                            self.add_item(discord.ui.Button(
                                emoji=discord.PartialEmoji.from_str("<:audio:1345517095101923439>"),
                                style=discord.ButtonStyle.secondary,
                                custom_id="nowplayingaudio",
                                disabled=not self.has_audio,
                                row=0
                            ))

                        async def interaction_check(self, interaction: discord.Interaction) -> bool:
                            if interaction.data["custom_id"] == "nowplayingaudio":
                                await self.audio_button(interaction)
                            return True

                        async def audio_button(self, interaction: discord.Interaction):
                            await interaction.response.defer(ephemeral=True)
                            if preview_url:
                                await self.preview_handler.send_preview(interaction, preview_url)
                            else:
                                await interaction.followup.send("No audio preview available", ephemeral=True)

                        async def on_timeout(self):
                            for item in self.children:
                                if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                                    item.disabled = True
                            try:
                                await self.message.edit(view=self)
                            except discord.NotFound:
                                pass

                    view = NowPlayingView(interaction, self.session, bool(preview_url), spotify_track_url)
                    message = await interaction.followup.send(embed=embed, view=view)
                    view.message = message

                except Exception as e:
                    await error_handler(interaction, e)

            except Exception as e:
                await error_handler(interaction, e)

    @lastfm.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="Your Last.fm username.")
    @app_commands.check(permissions.is_blacklisted)
    async def spotify(self, interaction: discord.Interaction, username: str = None):
        """Find your current playing Last.fm song on Spotify."""
        await interaction.response.defer(thinking=True)

        user_id = str(interaction.user.id)
        async with get_db_connection() as conn:
            result = await conn.fetchrow("SELECT lastfm_username FROM lastfm_usernames WHERE user_id = $1", user_id)
            lastfm_username = result['lastfm_username'] if result else None

            if username is None and lastfm_username is None:
                await interaction.followup.send(
                    f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your Last.fm username yet. Use </lastfm set:1245774423143874645> to set it.",
                    ephemeral=True
                )
                return
            
            if username is not None:
                lastfm_username = username

            api_key = f"{LASTFM_KEY}"
            recent_tracks_url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={lastfm_username}&api_key={api_key}&format=json"

            try:
                async with self.session.get(recent_tracks_url) as recent_tracks_response:
                    if recent_tracks_response.status == 200:
                        tracks = (await recent_tracks_response.json())['recenttracks'].get('track', [])
                        
                        if tracks:
                            track = tracks[0]
                            artist_name = track['artist']['#text']
                            track_name = track['name']

                            artistenc = urllib.parse.quote(artist_name)
                            trackenc = urllib.parse.quote(track_name)

                            spotify_url = f"http://127.0.0.1:2053/api/search?lastfm_username={lastfm_username}&track_name={trackenc}&artist_name={artistenc}"
                            headers = {"X-API-Key": f"{API_KEY}"}
                            
                            async with self.session.get(spotify_url, headers=headers) as spotify_response:
                                if spotify_response.status == 200:
                                    spotify_data = await spotify_response.json()
                                    spotify_track_url = spotify_data.get('spotify_link')
                                    
                                    if spotify_track_url:
                                        is_now_playing = '@attr' in track and 'nowplaying' in track['@attr'] and track['@attr']['nowplaying'] == 'true'
                                        status = "Now playing" if is_now_playing else "Last played"
                                        await interaction.followup.send(spotify_track_url)
                                    else:
                                        await interaction.followup.send(f"Couldn't find song on Spotify.")
                                else:
                                    await interaction.followup.send(f"Failed to fetch Spotify data. Status code: {spotify_response.status}")
                        else:
                            await interaction.followup.send("No recent tracks found for this user.")
                    elif recent_tracks_response.status == 404:
                        await interaction.followup.send("User not found.")
                    else:
                        await interaction.followup.send(f"Failed to fetch data from Last.fm. Status code: {recent_tracks_response.status}")
            except Exception as e:
                await error_handler(interaction, e)

    async def fetch_user_info2(self, username):
        url = f"http://ws.audioscrobbler.com/2.0/?method=user.getinfo&user={username}&api_key={LASTFM_KEY}&format=json"
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data['user']
        return None

    async def fetch_top_artists2(self, username):
        url = f"http://ws.audioscrobbler.com/2.0/?method=user.gettopartists&user={username}&api_key={LASTFM_KEY}&format=json&limit=10"
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data['topartists']['artist']
        return None

    async def fetch_unique_counts2(self, username):
        counts = {'artists': 0, 'albums': 0, 'tracks': 0}
        for method in ['artist', 'album', 'track']:
            url = f"http://ws.audioscrobbler.com/2.0/?method=user.gettop{method}s&user={username}&api_key={LASTFM_KEY}&format=json&limit=1"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    counts[f"{method}s"] = int(data[f'top{method}s']['@attr']['total'])
        return counts

    async def fetch_most_active_day2(self, username):
        url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={username}&api_key={LASTFM_KEY}&format=json&limit=1000"
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                tracks = data['recenttracks']['track']
                weekdays = [calendar.day_name[datetime.datetime.fromtimestamp(int(track['date']['uts'])).weekday()] for track in tracks if 'date' in track]
                return Counter(weekdays).most_common(1)[0][0] if weekdays else "Unknown"
        return "Unknown"

    @friends.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def whoknowstrack(self, interaction: discord.Interaction):
        """See which of your Last.fm friends know your current playing track."""
        user_id = str(interaction.user.id)
        async with get_db_connection() as conn:
            try:
                visibility_result = await conn.fetchrow("SELECT lastfm_state FROM settings WHERE user_id = $1", user_id)
                result = await conn.fetchrow("SELECT lastfm_username FROM lastfm_usernames WHERE user_id = $1", user_id)
                lastfm_visibility = visibility_result['lastfm_state'] if visibility_result else 'Show'
                lastfm_username = result['lastfm_username'] if result else None

                if not lastfm_username:
                    await interaction.followup.send(
                        f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your Last.fm username yet. Use </lastfm set:1245774423143874645> to set it.",
                        ephemeral=True
                    )
                    return
                
                friends = await conn.fetch("""
                    SELECT 
                        f.friend_id,
                        u.lastfm_username AS lastfm_username,
                        s.lastfm_state AS lastfm_visibility
                    FROM lastfm_friends f
                    LEFT JOIN lastfm_usernames u ON f.friend_id = u.user_id
                    LEFT JOIN settings s ON f.friend_id = s.user_id
                    WHERE f.user_id = $1
                """, user_id)

                if not friends:
                    await interaction.followup.send(
                        "You haven't added any Last.fm friends yet! Use </lastfm friends add:1245774423143874645> to add friends.",
                        ephemeral=True
                    )
                    return

                api_key = f"{LASTFM_KEY}"
                recent_tracks_url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={lastfm_username}&api_key={api_key}&format=json"

                async with self.session.get(recent_tracks_url) as response:
                    if response.status != 200:
                        await interaction.followup.send("Failed to fetch your current track.")
                        return

                    data = await response.json()
                    tracks = data['recenttracks'].get('track', [])

                    if not tracks:
                        await interaction.followup.send("You haven't scrobbled any tracks yet!")
                        return

                    current_track = tracks[0]
                    artist_name = current_track['artist']['#text']
                    track_name = current_track['name']
                    album_name = current_track['album']['#text']
                    track_url = current_track['url']

                    track_info_url = f"http://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key={api_key}&artist={urllib.parse.quote(artist_name)}&track={urllib.parse.quote(track_name)}&username={lastfm_username}&format=json"

                    async with self.session.get(track_info_url) as track_response:
                        track_data = await track_response.json()
                        user_playcount = int(track_data['track'].get('userplaycount', '0'))

                    friends_data = []
                    for friend in friends:
                        friend_track_url = f"http://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key={api_key}&artist={urllib.parse.quote(artist_name)}&track={urllib.parse.quote(track_name)}&username={friend['lastfm_username']}&format=json"

                        try:
                            async with self.session.get(friend_track_url) as friend_response:
                                if friend_response.status == 200:
                                    friend_data = await friend_response.json()
                                    playcount = int(friend_data['track'].get('userplaycount', '0'))

                                    if playcount > 0:
                                        try:
                                            discord_user = await interaction.client.fetch_user(int(friend['friend_id']))
                                            discord_name = discord_user.name
                                        except (discord.NotFound, discord.HTTPException):
                                            discord_name = f"User {friend['friend_id']}"

                                        friends_data.append({
                                            'name': discord_name,
                                            'lastfm_name': friend['lastfm_username'] if friend['lastfm_visibility'] != 'Hide' else None,
                                            'playcount': playcount
                                        })
                        except Exception as e:
                            print(f"Error fetching friend data: {e}")
                            continue

                    all_listeners = [{'name': lastfm_username if lastfm_visibility != 'Hide' else interaction.user.name, 'lastfm_name': lastfm_username if lastfm_visibility != 'Hide' else None, 'playcount': user_playcount, 'is_user': True}] + [dict(item, is_user=False) for item in friends_data]
                    all_listeners.sort(key=lambda x: x['playcount'], reverse=True)

                    embed_description = f"**{artist_name}** • *{album_name}*\n"

                    for idx, listener in enumerate(all_listeners[:5], start=1):
                        if listener['lastfm_name']:
                            name_part = f"[**{listener['name']}**](https://www.last.fm/user/{listener['lastfm_name']})"
                        else:
                            name_part = f"**{listener['name']}**"
                        
                        if listener['is_user']:
                            name_part += " *(You)*"
                        
                        embed_description += f"\n**`{idx}.`** {name_part} - **{listener['playcount']} plays**"

                    embed = await cembed(
                        interaction,
                        title=f"Friends Who Know: {track_name}",
                        description=embed_description,
                        url=track_url
                    )

                    try:
                        spotify_url = f"http://127.0.0.1:2053/api/search?lastfm_username={lastfm_username}&track_name={urllib.parse.quote(track_name)}&artist_name={urllib.parse.quote(artist_name)}"
                        headers = {"X-API-Key": f"{API_KEY}"}
                        async with self.session.get(spotify_url, headers=headers) as spotify_response:
                            if spotify_response.status == 200:
                                spotify_data = await spotify_response.json()
                                cover_art_url = spotify_data.get('cover_art')
                                if cover_art_url:
                                    embed.set_thumbnail(url=cover_art_url)
                    except Exception as e:
                        print(f"Error fetching cover art: {e}")

                    total_listeners = len(all_listeners)
                    total_plays = sum(listener['playcount'] for listener in all_listeners)
                    average_plays = total_plays // total_listeners
                    footer_text = f"{total_listeners} listeners • {total_plays} plays • {average_plays} average"

                    embed.set_footer(text=footer_text, icon_url="https://git.cursi.ng/lastfm_logo.png")

                    if len(all_listeners) > 5:
                        total_pages = (len(all_listeners) + 4) // 5
                        current_page = 1

                        first_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:lleft:1282403520254836829>"),
                            style=discord.ButtonStyle.secondary,
                            disabled=True
                        )

                        previous_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"),
                            style=discord.ButtonStyle.secondary,
                            disabled=True
                        )

                        next_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"),
                            style=discord.ButtonStyle.secondary,
                            disabled=False
                        )

                        last_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:rright:1282516005385404466>"),
                            style=discord.ButtonStyle.secondary,
                            disabled=False
                        )

                        async def update_embed(interaction, page_number):
                            start_index = (page_number - 1) * 5
                            end_index = min(start_index + 5, len(all_listeners))
                            paginated_listeners = all_listeners[start_index:end_index]

                            embed_description = f"**{artist_name}** • *{album_name}*\n"

                            for idx, listener in enumerate(paginated_listeners, start=start_index + 1):
                                if listener['lastfm_name']:
                                    name_part = f"[**{listener['name']}**](https://www.last.fm/user/{listener['lastfm_name']})"
                                else:
                                    name_part = f"**{listener['name']}**"
                                
                                if listener['is_user']:
                                    name_part += " *(You)*"
                                
                                embed_description += f"\n**`{idx}.`** {name_part} - **{listener['playcount']} plays**"

                            embed.description = embed_description
                            await interaction.edit_original_response(embed=embed, view=view)

                        async def on_timeout(self):
                            for item in view.children:
                                if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                                    item.disabled = True

                            try:
                                await interaction.edit_original_response(view=view)
                            except discord.NotFound:
                                pass

                        @first_button.callback
                        async def first_button_callback(interaction):
                            nonlocal current_page
                            current_page = 1
                            previous_button.disabled = True
                            first_button.disabled = True
                            next_button.disabled = False
                            last_button.disabled = False
                            await update_embed(interaction, current_page)

                        @previous_button.callback
                        async def previous_button_callback(interaction):
                            nonlocal current_page
                            if current_page > 1:
                                current_page -= 1
                                next_button.disabled = False
                                last_button.disabled = False
                            if current_page == 1:
                                previous_button.disabled = True
                                first_button.disabled = True
                            await update_embed(interaction, current_page)

                        @next_button.callback
                        async def next_button_callback(interaction):
                            nonlocal current_page
                            if current_page < total_pages:
                                current_page += 1
                                previous_button.disabled = False
                                first_button.disabled = False
                            if current_page == total_pages:
                                next_button.disabled = True
                                last_button.disabled = True
                            await update_embed(interaction, current_page)

                        @last_button.callback
                        async def last_button_callback(interaction):
                            nonlocal current_page
                            current_page = total_pages
                            next_button.disabled = True
                            last_button.disabled = True
                            previous_button.disabled = False
                            first_button.disabled = False
                            await update_embed(interaction, current_page)

                        buttons = [first_button, previous_button, next_button, last_button]
                        view = discord.ui.View(timeout=120)
                        for button in buttons:
                            view.add_item(button)

                        await interaction.followup.send(embed=embed, view=view)
                        await update_embed(interaction, current_page)

                    else:
                        await interaction.followup.send(embed=embed)

            except Exception as e:
                print(e)
                await error_handler(interaction, e)

    @friends.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def whoknowsalbum(self, interaction: discord.Interaction):
        """See which of your Last.fm friends know your current playing album."""
        user_id = str(interaction.user.id)
        async with get_db_connection() as conn:
            try:
                visibility_result = await conn.fetchrow("SELECT lastfm_state FROM settings WHERE user_id = $1", user_id)
                result = await conn.fetchrow("SELECT lastfm_username FROM lastfm_usernames WHERE user_id = $1", user_id)
                lastfm_visibility = visibility_result['lastfm_state'] if visibility_result else 'Show'
                lastfm_username = result['lastfm_username'] if result else None

                if not lastfm_username:
                    await interaction.followup.send(
                        f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your Last.fm username yet. Use </lastfm set:1245774423143874645> to set it.",
                        ephemeral=True
                    )
                    return
                
                friends = await conn.fetch("""
                    SELECT 
                        f.friend_id,
                        u.lastfm_username AS lastfm_username,
                        s.lastfm_state AS lastfm_visibility
                    FROM lastfm_friends f
                    LEFT JOIN lastfm_usernames u ON f.friend_id = u.user_id
                    LEFT JOIN settings s ON f.friend_id = s.user_id
                    WHERE f.user_id = $1
                """, user_id)

                if not friends:
                    await interaction.followup.send(
                        "You haven't added any Last.fm friends yet! Use </lastfm friends add:1245774423143874645> to add friends.",
                        ephemeral=True
                    )
                    return

                api_key = f"{LASTFM_KEY}"
                recent_tracks_url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={lastfm_username}&api_key={api_key}&format=json"

                async with self.session.get(recent_tracks_url) as response:
                    if response.status != 200:
                        await interaction.followup.send("Failed to fetch your current album.")
                        return

                    data = await response.json()
                    tracks = data['recenttracks'].get('track', [])

                    if not tracks:
                        await interaction.followup.send("You haven't scrobbled any tracks yet!")
                        return

                    current_track = tracks[0]
                    artist_name = current_track['artist']['#text']
                    album_name = current_track['album']['#text']
                    album_url = f"https://www.last.fm/music/{urllib.parse.quote(artist_name)}/{urllib.parse.quote(album_name)}"

                    if not album_name:
                        await interaction.followup.send("The current track doesn't have album information!")
                        return

                    album_info_url = f"http://ws.audioscrobbler.com/2.0/?method=album.getinfo&api_key={api_key}&artist={urllib.parse.quote(artist_name)}&album={urllib.parse.quote(album_name)}&username={lastfm_username}&format=json"

                    async with self.session.get(album_info_url) as album_response:
                        album_data = await album_response.json()
                        user_playcount = int(album_data.get('album', {}).get('userplaycount', '0'))

                    friends_data = []
                    for friend in friends:
                        friend_album_url = f"http://ws.audioscrobbler.com/2.0/?method=album.getinfo&api_key={api_key}&artist={urllib.parse.quote(artist_name)}&album={urllib.parse.quote(album_name)}&username={friend['lastfm_username']}&format=json"

                        try:
                            async with self.session.get(friend_album_url) as friend_response:
                                if friend_response.status == 200:
                                    friend_data = await friend_response.json()
                                    playcount = int(friend_data.get('album', {}).get('userplaycount', '0'))

                                    if playcount > 0:
                                        try:
                                            discord_user = await interaction.client.fetch_user(int(friend['friend_id']))
                                            discord_name = discord_user.name
                                        except (discord.NotFound, discord.HTTPException):
                                            discord_name = f"User {friend['friend_id']}"

                                        friends_data.append({
                                            'name': discord_name,
                                            'lastfm_name': friend['lastfm_username'] if friend['lastfm_visibility'] != 'Hide' else None,
                                            'playcount': playcount,
                                            'is_user': False
                                        })
                        except Exception as e:
                            print(f"Error fetching friend data: {e}")
                            continue

                    all_listeners = [{'name': lastfm_username if lastfm_visibility != 'Hide' else interaction.user.name, 'lastfm_name': lastfm_username if lastfm_visibility != 'Hide' else None, 'playcount': user_playcount, 'is_user': True}] + friends_data
                    all_listeners.sort(key=lambda x: x['playcount'], reverse=True)

                    embed_description = f"**{artist_name}** • *{album_name}*\n"

                    for idx, listener in enumerate(all_listeners[:5], start=1):
                        if listener['lastfm_name']:
                            name_part = f"[**{listener['name']}**](https://www.last.fm/user/{listener['lastfm_name']})"
                        else:
                            name_part = f"**{listener['name']}**"
                        
                        if listener['is_user']:
                            name_part += " *(You)*"
                        
                        embed_description += f"\n**`{idx}.`** {name_part} - **{listener['playcount']} plays**"

                    embed = await cembed(
                        interaction,
                        title=f"Friends Who Know: {album_name}",
                        description=embed_description,
                        url=album_url
                    )

                    try:
                        spotify_url = f"http://127.0.0.1:2053/api/search?lastfm_username={lastfm_username}&album_name={urllib.parse.quote(album_name)}&artist_name={urllib.parse.quote(artist_name)}"
                        headers = {"X-API-Key": f"{API_KEY}"}
                        async with self.session.get(spotify_url, headers=headers) as spotify_response:
                            if spotify_response.status == 200:
                                spotify_data = await spotify_response.json()
                                cover_art_url = spotify_data.get('cover_art')
                                if cover_art_url:
                                    embed.set_thumbnail(url=cover_art_url)
                    except Exception as e:
                        print(f"Error fetching cover art: {e}")

                    total_listeners = len(all_listeners)
                    total_plays = sum(listener['playcount'] for listener in all_listeners)
                    average_plays = total_plays // total_listeners
                    footer_text = f"{total_listeners} listeners • {total_plays} plays • {average_plays} average"

                    embed.set_footer(text=footer_text, icon_url="https://git.cursi.ng/lastfm_logo.png")

                    if len(all_listeners) > 5:
                        total_pages = (len(all_listeners) + 4) // 5
                        current_page = 1

                        first_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:lleft:1282403520254836829>"),
                            style=discord.ButtonStyle.secondary,
                            disabled=True
                        )

                        previous_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"),
                            style=discord.ButtonStyle.secondary,
                            disabled=True
                        )

                        next_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"),
                            style=discord.ButtonStyle.secondary,
                            disabled=False
                        )

                        last_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:rright:1282516005385404466>"),
                            style=discord.ButtonStyle.secondary,
                            disabled=False
                        )

                        async def update_embed(interaction, page_number):
                            start_index = (page_number - 1) * 5
                            end_index = min(start_index + 5, len(all_listeners))
                            paginated_listeners = all_listeners[start_index:end_index]

                            embed_description = f"**{artist_name}** • *{album_name}*\n"

                            for idx, listener in enumerate(paginated_listeners, start=start_index + 1):
                                if listener['lastfm_name']:
                                    name_part = f"[**{listener['name']}**](https://www.last.fm/user/{listener['lastfm_name']})"
                                else:
                                    name_part = f"**{listener['name']}**"
                                
                                if listener['is_user']:
                                    name_part += " *(You)*"
                                
                                embed_description += f"\n**`{idx}.`** {name_part} - **{listener['playcount']} plays**"

                            embed.description = embed_description
                            await interaction.edit_original_response(embed=embed, view=view)

                        @first_button.callback
                        async def first_button_callback(interaction):
                            nonlocal current_page
                            current_page = 1
                            previous_button.disabled = True
                            first_button.disabled = True
                            next_button.disabled = False
                            last_button.disabled = False
                            await update_embed(interaction, current_page)

                        @previous_button.callback
                        async def previous_button_callback(interaction):
                            nonlocal current_page
                            if current_page > 1:
                                current_page -= 1
                                next_button.disabled = False
                                last_button.disabled = False
                            if current_page == 1:
                                previous_button.disabled = True
                                first_button.disabled = True
                            await update_embed(interaction, current_page)

                        @next_button.callback
                        async def next_button_callback(interaction):
                            nonlocal current_page
                            if current_page < total_pages:
                                current_page += 1
                                previous_button.disabled = False
                                first_button.disabled = False
                            if current_page == total_pages:
                                next_button.disabled = True
                                last_button.disabled = True
                            await update_embed(interaction, current_page)

                        @last_button.callback
                        async def last_button_callback(interaction):
                            nonlocal current_page
                            current_page = total_pages
                            next_button.disabled = True
                            last_button.disabled = True
                            previous_button.disabled = False
                            first_button.disabled = False
                            await update_embed(interaction, current_page)

                        buttons = [first_button, previous_button, next_button, last_button]
                        view = discord.ui.View(timeout=120)
                        for button in buttons:
                            view.add_item(button)

                        await interaction.followup.send(embed=embed, view=view)
                        await update_embed(interaction, current_page)

                    else:
                        await interaction.followup.send(embed=embed)

            except Exception as e:
                print(e)
                await error_handler(interaction, e)

    @friends.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def whoknowsartist(self, interaction: discord.Interaction):
        """See which of your Last.fm friends know your current playing artist."""
        user_id = str(interaction.user.id)
        async with get_db_connection() as conn:
            try:
                visibility_result = await conn.fetchrow("SELECT lastfm_state FROM settings WHERE user_id = $1", user_id)
                result = await conn.fetchrow("SELECT lastfm_username FROM lastfm_usernames WHERE user_id = $1", user_id)
                lastfm_visibility = visibility_result['lastfm_state'] if visibility_result else 'Show'
                lastfm_username = result['lastfm_username'] if result else None

                if not lastfm_username:
                    await interaction.followup.send(
                        f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your Last.fm username yet. Use </lastfm set:1245774423143874645> to set it.",
                        ephemeral=True
                    )
                    return
                
                friends = await conn.fetch("""
                    SELECT 
                        f.friend_id,
                        u.lastfm_username AS lastfm_username,
                        s.lastfm_state AS lastfm_visibility
                    FROM lastfm_friends f
                    LEFT JOIN lastfm_usernames u ON f.friend_id = u.user_id
                    LEFT JOIN settings s ON f.friend_id = s.user_id
                    WHERE f.user_id = $1
                """, user_id)

                if not friends:
                    await interaction.followup.send(
                        "You haven't added any Last.fm friends yet! Use </lastfm friends add:1245774423143874645> to add friends.",
                        ephemeral=True
                    )
                    return

                api_key = f"{LASTFM_KEY}"
                recent_tracks_url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={lastfm_username}&api_key={api_key}&format=json"

                async with self.session.get(recent_tracks_url) as response:
                    if response.status != 200:
                        await interaction.followup.send("Failed to fetch your current artist.")
                        return

                    data = await response.json()
                    tracks = data['recenttracks'].get('track', [])

                    if not tracks:
                        await interaction.followup.send("You haven't scrobbled any tracks yet!")
                        return

                    current_track = tracks[0]
                    artist_name = current_track['artist']['#text']
                    artist_url = f"https://www.last.fm/music/{urllib.parse.quote(artist_name)}"

                    artist_info_url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&api_key={api_key}&artist={urllib.parse.quote(artist_name)}&username={lastfm_username}&format=json"

                    async with self.session.get(artist_info_url) as artist_response:
                        artist_data = await artist_response.json()
                        user_playcount = int(artist_data.get('artist', {}).get('stats', {}).get('userplaycount', '0'))

                    friends_data = []
                    for friend in friends:
                        friend_artist_url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&api_key={api_key}&artist={urllib.parse.quote(artist_name)}&username={friend['lastfm_username']}&format=json"

                        try:
                            async with self.session.get(friend_artist_url) as friend_response:
                                if friend_response.status == 200:
                                    friend_data = await friend_response.json()
                                    playcount = int(friend_data.get('artist', {}).get('stats', {}).get('userplaycount', '0'))

                                    if playcount > 0:
                                        try:
                                            discord_user = await interaction.client.fetch_user(int(friend['friend_id']))
                                            discord_name = discord_user.name
                                        except (discord.NotFound, discord.HTTPException):
                                            discord_name = f"User {friend['friend_id']}"

                                        friends_data.append({
                                            'name': discord_name,
                                            'lastfm_name': friend['lastfm_username'] if friend['lastfm_visibility'] != 'Hide' else None,
                                            'playcount': playcount,
                                            'is_user': False
                                        })
                        except Exception as e:
                            print(f"Error fetching friend data: {e}")
                            continue

                    all_listeners = [{'name': lastfm_username if lastfm_visibility != 'Hide' else interaction.user.name, 'lastfm_name': lastfm_username if lastfm_visibility != 'Hide' else None, 'playcount': user_playcount, 'is_user': True}] + friends_data
                    all_listeners.sort(key=lambda x: x['playcount'], reverse=True)

                    embed_description = f"**{artist_name}**\n"

                    for idx, listener in enumerate(all_listeners[:5], start=1):
                        if listener['lastfm_name']:
                            name_part = f"[**{listener['name']}**](https://www.last.fm/user/{listener['lastfm_name']})"
                        else:
                            name_part = f"**{listener['name']}**"
                        
                        if listener['is_user']:
                            name_part += " *(You)*"
                        
                        embed_description += f"\n**`{idx}.`** {name_part} - **{listener['playcount']} plays**"

                    embed = await cembed(
                        interaction,
                        title=f"Friends Who Know: {artist_name}",
                        description=embed_description,
                        url=artist_url
                    )

                    try:
                        artist_name_escaped = urllib.parse.quote(artist_name)
                        spotify_url = f"http://127.0.0.1:2053/api/spotify/artist?artist_name={artist_name_escaped}"
                        headers = {"X-API-Key": f"{API_KEY}"}
                        async with self.session.get(spotify_url, headers=headers) as spotify_response:
                            if spotify_response.status == 200:
                                spotify_data = await spotify_response.json()
                                artist_image = spotify_data.get('cover_art', artist_data["artist"]["image"][3]["#text"])
                            else:
                                artist_image = artist_data["artist"]["image"][3]["#text"]
                        
                        if artist_image:
                            embed.set_thumbnail(url=artist_image)
                    except Exception as e:
                        print(f"Error fetching artist image: {e}")

                    total_listeners = len(all_listeners)
                    total_plays = sum(listener['playcount'] for listener in all_listeners)
                    average_plays = total_plays // total_listeners
                    footer_text = f"{total_listeners} listeners • {total_plays} plays • {average_plays} average"

                    embed.set_footer(text=footer_text, icon_url="https://git.cursi.ng/lastfm_logo.png")

                    if len(all_listeners) > 5:
                        total_pages = (len(all_listeners) + 4) // 5
                        current_page = 1

                        first_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:lleft:1282403520254836829>"),
                            style=discord.ButtonStyle.secondary,
                            disabled=True
                        )

                        previous_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"),
                            style=discord.ButtonStyle.secondary,
                            disabled=True
                        )

                        next_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"),
                            style=discord.ButtonStyle.secondary,
                            disabled=False
                        )

                        last_button = discord.ui.Button(
                            emoji=discord.PartialEmoji.from_str("<:rright:1282516005385404466>"),
                            style=discord.ButtonStyle.secondary,
                            disabled=False
                        )

                        async def update_embed(interaction, page_number):
                            start_index = (page_number - 1) * 5
                            end_index = min(start_index + 5, len(all_listeners))
                            paginated_listeners = all_listeners[start_index:end_index]

                            embed_description = f"**{artist_name}**\n"

                            for idx, listener in enumerate(paginated_listeners, start=start_index + 1):
                                if listener['lastfm_name']:
                                    name_part = f"[**{listener['name']}**](https://www.last.fm/user/{listener['lastfm_name']})"
                                else:
                                    name_part = f"**{listener['name']}**"
                                
                                if listener['is_user']:
                                    name_part += " *(You)*"
                                
                                embed_description += f"\n**`{idx}.`** {name_part} - **{listener['playcount']} plays**"

                            embed.description = embed_description
                            await interaction.edit_original_response(embed=embed, view=view)

                        async def on_timeout(self):
                            for item in view.children:
                                if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                                    item.disabled = True

                            try:
                                await interaction.edit_original_response(view=view)
                            except discord.NotFound:
                                pass

                        @first_button.callback
                        async def first_button_callback(interaction):
                            nonlocal current_page
                            current_page = 1
                            previous_button.disabled = True
                            first_button.disabled = True
                            next_button.disabled = False
                            last_button.disabled = False
                            await update_embed(interaction, current_page)

                        @previous_button.callback
                        async def previous_button_callback(interaction):
                            nonlocal current_page
                            if current_page > 1:
                                current_page -= 1
                                next_button.disabled = False
                                last_button.disabled = False
                            if current_page == 1:
                                previous_button.disabled = True
                                first_button.disabled = True
                            await update_embed(interaction, current_page)

                        @next_button.callback
                        async def next_button_callback(interaction):
                            nonlocal current_page
                            if current_page < total_pages:
                                current_page += 1
                                previous_button.disabled = False
                                first_button.disabled = False
                            if current_page == total_pages:
                                next_button.disabled = True
                                last_button.disabled = True
                            await update_embed(interaction, current_page)

                        @last_button.callback
                        async def last_button_callback(interaction):
                            nonlocal current_page
                            current_page = total_pages
                            next_button.disabled = True
                            last_button.disabled = True
                            previous_button.disabled = False
                            first_button.disabled = False
                            await update_embed(interaction, current_page)

                        buttons = [first_button, previous_button, next_button, last_button]
                        view = discord.ui.View(timeout=120)
                        for button in buttons:
                            view.add_item(button)

                        await interaction.followup.send(embed=embed, view=view)
                        await update_embed(interaction, current_page)

                    else:
                        await interaction.followup.send(embed=embed)

            except Exception as e:
                print(e)
                await error_handler(interaction, e)

    async def fetch_lastfm_details(self, user_id: str):
        async with get_db_connection() as conn:
            try:
                username_result = await conn.fetchrow("""
                    SELECT lastfm_username
                    FROM lastfm_usernames
                    WHERE user_id = $1
                """, user_id)

                state_result = await conn.fetchrow("""
                    SELECT lastfm_state
                    FROM settings
                    WHERE user_id = $1
                """, user_id)

                lastfm_username = username_result['lastfm_username'] if username_result else None
                lastfm_state = state_result['lastfm_state'] if state_result else 'Show'

                return lastfm_username, lastfm_state

            except Exception as e:
                print(f"Database query error: {e}")
                return None, 'Show'
            finally:
                await conn.close()

    async def generate_collage(self, interaction, real_username, display_username, period, method):
        if real_username is None:
            await interaction.followup.send(
                f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your Last.fm username yet. Use </lastfm set:1245774423143874645> to set it.",
                ephemeral=True
            )
            return
        
        method_map = {
            "albums": "album",
            "artists": "artist",
            "tracks": "track"
        }
        
        method_value = method_map.get(method)
        if not method_value:
            await interaction.followup.send("Invalid type. Please choose from: albums, artists, tracks.")
            return
        
        url = f"https://songstitch.art/collage?username={real_username}&method={method_value}&period={periods[period]}&artist=true&album=true&playcount=true&rows=3&columns=3"
        headers = {'User-Agent': 'Mozilla/5.0'}

        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                image_data = await response.read()

                def process_image(image_data):
                    img = Image.open(io.BytesIO(image_data))
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='JPEG')
                    img_byte_arr.seek(0)
                    return img_byte_arr

                img_byte_arr = await asyncio.to_thread(process_image, image_data)

                file = discord.File(img_byte_arr, filename=f"heist.jpg")
                embed = Embed(
                    interaction,
                    title=f"3x3 {period} Top {method.capitalize()} Chart for {display_username}"
                )

                if display_username != "(hidden)":
                    embed.url = f"https://last.fm/user/{real_username}/library/{method_value}s?date_preset={periods[period]}"

                embed.set_footer(text=footer, icon_url="https://git.cursi.ng/lastfm_logo.png")

                try:
                    await interaction.followup.send(file=file, embed=embed)
                except Exception as e:
                    await error_handler(interaction, e)
            else:
                await interaction.followup.send(f"User not found.")

    async def fetch_user_info(self, username: str) -> dict:
        url = f"http://ws.audioscrobbler.com/2.0/?method=user.getinfo&user={username}&api_key={LASTFM_KEY}&format=json"
        async with self.session.get(url) as response:
            return await response.json()

    async def fetch_top_albums(self, username: str, period: str = "7day") -> dict:
        url = f"http://ws.audioscrobbler.com/2.0/?method=user.gettopalbums&user={username}&api_key={LASTFM_KEY}&format=json&period={period}"
        async with self.session.get(url) as response:
            data = await response.json()
            if 'error' in data:
                raise Exception(f"Last.fm API error: {data['message']}")
            if 'topalbums' not in data or 'album' not in data['topalbums']:
                raise Exception("No albums found in the API response.")
            return data

    async def fetch_top_artists(self, username: str, period: str = "7day") -> dict:
        url = f"http://ws.audioscrobbler.com/2.0/?method=user.gettopartists&user={username}&api_key={LASTFM_KEY}&format=json&period={period}"
        async with self.session.get(url) as response:
            data = await response.json()
            if 'error' in data:
                raise Exception(f"Last.fm API error: {data['message']}")
            if 'topartists' not in data or 'artist' not in data['topartists']:
                raise Exception("No artists found in the API response.")
            return data

    async def fetch_top_tracks(self, username: str, period: str = "7day") -> dict:
        url = f"http://ws.audioscrobbler.com/2.0/?method=user.gettoptracks&user={username}&api_key={LASTFM_KEY}&format=json&period={period}"
        print(url)
        async with self.session.get(url) as response:
            data = await response.json()
            print(data)
            if 'error' in data:
                raise Exception(f"Last.fm API error: {data['message']}")
            if 'toptracks' not in data or 'track' not in data['toptracks']:
                raise Exception("No tracks found in the API response.")
            return data['toptracks']['track']

    async def lastfm_top(self, interaction: Interaction, type: str, username: str = None, period: str = "7 days"):
        if not interaction.app_permissions.embed_links:
            await interaction.response.defer(thinking=True, ephemeral=True)
        else:
            await interaction.response.defer(thinking=True)

        try:
            user_id = str(interaction.user.id)
            if username is None:
                real_username, visibility = await self.fetch_lastfm_details(user_id)
                if not real_username:
                    return await interaction.followup.send(f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your LastFM username yet. Use </lastfm set:1245774423143874645> to set it.\n-# You can create a LastFM account [here](https://last.fm/join).")
                display_username = "(hidden)" if visibility == 'Hide' else real_username
            else:
                real_username = username
                if real_username.lower() == (await self.fetch_lastfm_details(user_id))[0].lower():
                    visibility = (await self.fetch_lastfm_details(user_id))[1]
                    display_username = "(hidden)" if visibility == 'Hide' else real_username
                else:
                    display_username = real_username

            if period not in periods:
                return await interaction.followup.send("Invalid period. Please choose from: 7 days, 1 month, 3 months, 6 months, 1 year, lifetime.")

            period_mapping = {
                "7 days": "7day",
                "1 month": "1month",
                "3 months": "3month",
                "6 months": "6month",
                "1 year": "12month",
                "lifetime": "overall"
            }

            period_key = period_mapping.get(period)
            if period_key is None:
                return await interaction.followup.send("Invalid period. Please choose from: 7 days, 1 month, 3 months, 6 months, 1 year, lifetime.")

            user_info = await self.fetch_user_info(real_username)
            if user_info is None or 'user' not in user_info:
                return await interaction.followup.send("User not found. Make sure you set the right one.")
            total_scrobbles = int(user_info['user']['playcount'])

            try:
                if type == "albums":
                    top_data = await self.fetch_top_albums(real_username, period_key)
                    items = top_data['topalbums']['album'][:1000]
                elif type == "artists":
                    top_data = await self.fetch_top_artists(real_username, period_key)
                    items = top_data['topartists']['artist'][:1000]
                elif type == "tracks":
                    top_data = await self.fetch_top_tracks(real_username, period_key)
                    items = top_data[:1000]
            except Exception as e:
                return await interaction.followup.send(f"No {type} found for this user or period.")

            if not items:
                return await interaction.followup.send(f"No {type} found for this user or period.")

            paginator = TopItems(interaction, self.session, items, type, display_username, period, total_scrobbles)
            initial_embed = await paginator.create_embed()

            await interaction.followup.send(embed=initial_embed, view=paginator)

        except Exception as e:
            await error_handler(interaction, e)

    @top.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="Last.fm username.", period="Time period for the content.")
    @app_commands.check(permissions.is_blacklisted)
    async def albums(self, interaction: Interaction, username: str = None, period: str = "7 days"):
        """Get your Last.fm top albums."""
        await self.lastfm_top(interaction, "albums", username, period)

    @top.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="Last.fm username.", period="Time period for the content.")
    @app_commands.check(permissions.is_blacklisted)
    async def tracks(self, interaction: Interaction, username: str = None, period: str = "7 days"):
        """Get your Last.fm top tracks."""
        await self.lastfm_top(interaction, "tracks", username, period)

    @top.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="Last.fm username.", period="Time period for the content.")
    @app_commands.check(permissions.is_blacklisted)
    async def artists(self, interaction: Interaction, username: str = None, period: str = "7 days"):
        """Get your Last.fm top artists."""
        await self.lastfm_top(interaction, "artists", username, period)

    @albums.autocomplete("period")
    @tracks.autocomplete("period")
    @artists.autocomplete("period")
    async def period_autocomplete(self, interaction: Interaction, current: str):
        filtered_periods = [period for period in periods.keys() if current.lower() in period.lower()]
        return [app_commands.Choice(name=period, value=period) for period in filtered_periods]

    async def fetch_recent_tracks(self, username: str, page: int = 1) -> dict:
        url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={username}&api_key={LASTFM_KEY}&format=json&limit={self.FETCH_LIMIT}&page={page}"
        async with self.session.get(url) as response:
            return await response.json()

    async def get_tracks_for_page(self, username: str, page: int) -> tuple:
        api_page = (page * self.TRACKS_PER_PAGE) // self.FETCH_LIMIT + 1
        data = await self.fetch_recent_tracks(username, api_page)
        
        if 'recenttracks' not in data or not data['recenttracks']['track']:
            return None, None, 0
        
        tracks = data['recenttracks']['track']
        start_index = (page * self.TRACKS_PER_PAGE) % self.FETCH_LIMIT
        end_index = start_index + self.TRACKS_PER_PAGE
        page_tracks = tracks[start_index:end_index]
        
        total_pages = (int(data['recenttracks']['@attr']['total']) + self.TRACKS_PER_PAGE - 1) // self.TRACKS_PER_PAGE
        return page_tracks, data['recenttracks']['@attr']['total'], total_pages

    @lastfm.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="Last.fm username.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def latest(self, interaction: Interaction, username: str = None):
        """Get latest Last.fm scrobbles."""

        try:
            user_id = str(interaction.user.id)
            display_username = None
            if username is None:
                real_username, visibility = await self.fetch_lastfm_details(user_id)
                if not real_username:
                    return await interaction.followup.send(f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your LastFM username yet. Use </lastfm set:1245774423143874645> to set it.\n-# You can create a LastFM account [here](https://last.fm/join).")
                display_username = "(hidden)" if visibility == 'Hide' else real_username
            else:
                real_username = username
                display_username = real_username

            tracks, total_scrobbles, total_pages = await self.get_tracks_for_page(real_username, 0)
            if not tracks:
                return await interaction.followup.send("You haven't played anything recently.")

            current_page = 0

            async def create_embed(page_tracks, page_num):
                embed_description = []
                current_art = None

                for track in page_tracks:
                    track_name = track.get('name', 'Unknown Track')
                    artist_name = track.get('artist', {}).get('#text', 'Unknown Artist')
                    album_name = track.get('album', {}).get('#text', '')
                    timestamp = track.get('date', {}).get('uts')
                    if timestamp:
                        now = datetime.datetime.utcnow()
                        track_time = datetime.datetime.utcfromtimestamp(int(timestamp))
                        if now.date() == track_time.date():
                            timestamp_format = f"<t:{int(timestamp)}:R>"
                        else:
                            timestamp_format = f"<t:{int(timestamp)}:f>"
                    else:
                        timestamp_format = "🎶"
                    track_url = track.get('url', '#')

                    track_hyperlink = f"[{track_name}]({track_url})"

                    if not current_art:
                        current_art = track.get('image', [{}])[-1].get('#text', None)

                    if album_name:
                        embed_description.append(f"**{track_hyperlink}** by **{artist_name}**\n-# {timestamp_format} • *{album_name}*\n\n")
                    else:
                        embed_description.append(f"**{track_hyperlink}** by **{artist_name}**\n-# {timestamp_format}\n\n")

                lastfm_url = f"https://www.last.fm/user/{real_username}" if display_username != "(hidden)" else None
                title = f"Latest tracks for {display_username}"
                title_url = lastfm_url if lastfm_url else None

                embed = await cembed(interaction, description="".join(embed_description))
                embed.set_author(name=title, url=title_url, icon_url=interaction.user.display_avatar.url)
                embed.set_footer(text=f"Page {page_num + 1}/{total_pages} • {display_username} has {total_scrobbles} scrobbles", icon_url="https://git.cursi.ng/lastfm_logo.png")
                if current_art:
                    embed.set_thumbnail(url=current_art)

                return embed

            class LatestView(View):
                def __init__(self, cog, interaction, total_pages, current_page):
                    super().__init__(timeout=120)
                    self.cog = cog
                    self.interaction = interaction
                    self.total_pages = total_pages
                    self.current_page = current_page
                    self.update_buttons()

                def update_buttons(self):
                    self.children[0].disabled = self.current_page == 0
                    self.children[1].disabled = self.current_page == self.total_pages - 1

                async def update_page(self, new_page):
                    self.current_page = new_page
                    new_tracks, _, _ = await self.cog.get_tracks_for_page(real_username, new_page)
                    new_embed = await create_embed(new_tracks, new_page)
                    self.update_buttons()
                    await self.interaction.edit_original_response(embed=new_embed, view=self)

                @ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=ButtonStyle.primary, custom_id="latestleft")
                async def previous_button(self, interaction: Interaction, button: Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's embed.", ephemeral=True)
                        return
                    if self.current_page > 0:
                        await interaction.response.defer()
                        await self.update_page(self.current_page - 1)

                @ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=ButtonStyle.primary, custom_id="latestright")
                async def next_button(self, interaction: Interaction, button: Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's embed.", ephemeral=True)
                        return
                    if self.current_page < self.total_pages - 1:
                        await interaction.response.defer()
                        await self.update_page(self.current_page + 1)

                @ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=ButtonStyle.secondary, custom_id="latestskip")
                async def skip_button(self, interaction: Interaction, button: Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's embed.", ephemeral=True)
                        return

                    class GoToPageModal(discord.ui.Modal, title="Go to Page"):
                        page_number = discord.ui.TextInput(label="Navigate to page", placeholder=f"Enter a page number (1-{self.total_pages})", min_length=1, max_length=len(str(self.total_pages)))

                        async def on_submit(self, interaction: Interaction):
                            try:
                                page = int(self.page_number.value) - 1
                                if page < 0 or page >= self.view.total_pages:
                                    raise ValueError
                                await interaction.response.defer()
                                await self.view.update_page(page)
                            except ValueError:
                                await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

                    modal = GoToPageModal()
                    modal.view = self
                    await interaction.response.send_modal(modal)

                @ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=ButtonStyle.danger, custom_id="latestdelete")
                async def delete_button(self, interaction: Interaction, button: Button):
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

            initial_embed = await create_embed(tracks, current_page)
            await interaction.followup.send(embed=initial_embed, view=LatestView(self, interaction, total_pages, current_page))

        except Exception as e:
            await error_handler(interaction, e)

    @lastfm.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(artist="Name of the artist.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def artist(self, interaction: Interaction, artist: str):
        """Get information about a Last.fm artist."""
        user_id = str(interaction.user.id)
        async with get_db_connection() as conn:
            result = await conn.fetchrow(
                "SELECT lastfm_username FROM lastfm_usernames WHERE user_id = $1", user_id
            )
            if not result or not result['lastfm_username']:
                await interaction.followup.send(
                    f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your Last.fm username yet. Use </lastfm set:1245774423143874645> to set it.\n-# You can create a LastFM account [here](https://last.fm/join).",
                    ephemeral=True
                )
                return

        artist_name_escaped = artist.replace(" ", "+")
        lastfm_user = result['lastfm_username']
        artist_info_url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={artist_name_escaped}&api_key={LASTFM_KEY}&format=json"
        user_artist_info_url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={artist_name_escaped}&username={lastfm_user}&api_key={LASTFM_KEY}&format=json"
        artist_tags_url = f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptags&artist={artist_name_escaped}&api_key={LASTFM_KEY}&format=json"
        artist_tracks_url = f"http://ws.audioscrobbler.com/2.0/?method=user.getArtistTracks&user={lastfm_user}&artist={artist_name_escaped}&api_key={LASTFM_KEY}&format=json"

        try:
            artist_info_response, user_artist_info_response, tags_response, tracks_response, total_scrobbles_response, wikipedia_response = await asyncio.gather(
                self.session.get(artist_info_url),
                self.session.get(user_artist_info_url),
                self.session.get(artist_tags_url),
                self.session.get(artist_tracks_url),
                self.session.get(f"http://ws.audioscrobbler.com/2.0/?method=user.getinfo&user={lastfm_user}&api_key={LASTFM_KEY}&format=json"),
                self.session.get(f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exintro&explaintext&titles={artist_name_escaped}&format=json")
            )

            if artist_info_response.status != 200:
                await interaction.followup.send("Failed to retrieve artist information.", ephemeral=True)
                return

            artist_info_data = await artist_info_response.json()
            if "artist" not in artist_info_data:
                await interaction.followup.send("Artist not found. Are you sure they have a Last.fm page?", ephemeral=True)
                return

            artist_info = artist_info_data["artist"]
            artist_playcount = int(artist_info["stats"]["playcount"])
            artist_listeners = int(artist_info["stats"]["listeners"])
            artist_bio = artist_info.get("bio", {}).get("summary", "").split("<")[0].strip()

            user_artist_info_data = await user_artist_info_response.json()
            user_playcount = int(user_artist_info_data.get("artist", {}).get("stats", {}).get("userplaycount", 0))

            if tags_response.status == 200:
                tags_data = await tags_response.json()
                top_tag = tags_data.get("toptags", {}).get("tag", [{}])[0].get("name", "Unknown")
            else:
                top_tag = "Unknown"

            total_scrobbles_data = await total_scrobbles_response.json()
            total_scrobbles = int(total_scrobbles_data.get("user", {}).get("playcount", 0))

            wikipedia_data = await wikipedia_response.json()
            pages = wikipedia_data.get("query", {}).get("pages", {})
            page_id = next(iter(pages))
            page = pages.get(page_id, {})
            extract = page.get("extract", "")
            birthdate, nationality = "Unknown", "Unknown"

            if extract:
                if "Born" in extract:
                    birthdate = extract.split("Born")[1].split(" ")[0]
                if "Nationality" in extract:
                    nationality = extract.split("Nationality")[1].split(" ")[0]

            spotify_url = f"http://127.0.0.1:2053/api/spotify/artist?artist_name={artist_name_escaped}"
            headers = {"X-API-Key": f"{API_KEY}"}
            async with self.session.get(spotify_url, headers=headers) as spotify_response:
                if spotify_response.status == 200:
                    spotify_data = await spotify_response.json()
                    artist_image = spotify_data.get('cover_art', artist_info["image"][3]["#text"])
                else:
                    artist_image = artist_info["image"][3]["#text"]

            percentage_of_plays = (user_playcount / total_scrobbles * 100) if total_scrobbles > 0 else 0

            embed = await cembed(interaction, description=f"`{artist_listeners:,}` listeners\n`{artist_playcount:,}` global plays\n`{user_playcount:,}` plays by you")
            embed.set_thumbnail(url=artist_image)
            embed.set_author(name=f"Artist: {artist_info['name']}", url=artist_info["url"], icon_url=interaction.user.display_avatar.url)
            embed.add_field(name="Summary", value=f"{artist_bio}", inline=False)
            embed.set_footer(text=f"Image source: Spotify\n{percentage_of_plays:.2f}% of all your scrobbles are for this artist\n{top_tag}", icon_url="https://git.cursi.ng/lastfm_logo.png")

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await error_handler(interaction, e)

    @artist.autocomplete("artist")
    async def artist_autocomplete(self, interaction: Interaction, current: str):
        if not current:
            await interaction.response.autocomplete([])
            return
        
        url = f"http://ws.audioscrobbler.com/2.0/?method=artist.search&artist={current}&api_key={LASTFM_KEY}&format=json&limit=10"
        
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                artists = data.get("results", {}).get("artistmatches", {}).get("artist", [])

                if not isinstance(artists, list):
                    await interaction.response.autocomplete([])
                    return

                suggestions = []
                for artist in artists:
                    name = artist["name"]
                    if len(name) > 100:
                        name = name[:97] + "..."
                    
                    suggestions.append(app_commands.Choice(name=name, value=name))

                await interaction.response.autocomplete(suggestions)

    @lastfm.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="LastFM username to lookup.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def profile(self, interaction: discord.Interaction, username: str = None):
        "View Last.fm profile."
        user_id = str(interaction.user.id)
        async with get_db_connection() as conn:
            try:
                visibility_result = await conn.fetchrow("SELECT lastfm_state FROM settings WHERE user_id = $1", user_id)
                lastfm_visibility = visibility_result['lastfm_state'] if visibility_result else 'Show'

                result = await conn.fetchrow("SELECT lastfm_username FROM lastfm_usernames WHERE user_id = $1", user_id)
                lastfm_username = result['lastfm_username'] if result else None

                if username is None and lastfm_username is None:
                    await interaction.followup.send(
                        f"<:warning:1350239604925530192> {interaction.user.mention}: You haven't set your Last.fm username yet. Use </lastfm set:1245774423143874645> to set it.\n-# You can create a LastFM account [here](https://last.fm/join).",
                        ephemeral=True
                    )
                    return

                if username is not None:
                    lastfm_username = username

                is_hidden = lastfm_visibility == 'Hide'
                display_username = "Hidden" if is_hidden else lastfm_username
                user_url = None if is_hidden else f"https://last.fm/user/{lastfm_username}"

                async with aiohttp.ClientSession() as session:
                    user_info = await self.fetch_user_info2(lastfm_username)
                    if not user_info:
                        await interaction.followup.send("User not found.")
                        return

                    top_artists = await self.fetch_top_artists2(lastfm_username)
                    unique_counts = await self.fetch_unique_counts2(lastfm_username)

                    if not top_artists or not unique_counts:
                        await interaction.followup.send("Failed to fetch user statistics.")
                        return

                    discord_display_name = interaction.user.display_name
                    lastfm_display = "Hidden" if is_hidden else (user_info['realname'] or user_info['name'])
                    country = user_info.get('country') if not is_hidden else None
                    registered = int(user_info['registered']['unixtime'])
                    playcount = int(user_info['playcount'])
                    profile_picture = user_info['image'][-1]['#text']

                    days_since_registration = (time.time() - registered) / 86400
                    avg_scrobbles_per_day = playcount / days_since_registration

                    top_10_scrobbles = sum(int(artist['playcount']) for artist in top_artists[:10])
                    top_10_percentage = (top_10_scrobbles / playcount) * 100

                    avg_albums_per_artist = unique_counts['albums'] / unique_counts['artists'] if unique_counts['artists'] > 0 else 0
                    tracks_count = int(unique_counts['tracks']) if isinstance(unique_counts['tracks'], (int, float)) else 0
                    artists_count = int(unique_counts['artists']) if isinstance(unique_counts['artists'], (int, float)) else 0
                    avg_tracks_per_artist = tracks_count / artists_count if artists_count > 0 else 0

                    most_active_day = await self.fetch_most_active_day2(lastfm_username)

                    friended = await conn.fetchval(
                        "SELECT COUNT(*) FROM lastfm_friends WHERE user_id = $1", user_id
                    )
                    befriendedby = await conn.fetchval(
                        "SELECT COUNT(*) FROM lastfm_friends WHERE friend_id = $1", user_id
                    )

                    embed = discord.Embed(title=f"{discord_display_name} (@{display_username})" if discord_display_name else f"@{display_username}", url=user_url)
                    embed.description = f"-# **Country:** {country}\n-# **Type:** User" if country else "-# **Type:** User"

                    embed.add_field(name="Scrobbles", value=f"{playcount:,}", inline=True)
                    embed.add_field(name="Artists", value=f"{unique_counts['artists']:,}", inline=True)
                    embed.add_field(name="Albums", value=f"{unique_counts['albums']:,}", inline=True)
                    embed.add_field(name="Created", value=f"<t:{registered}:D>", inline=True)

                    last_scrobble = await self.fetch_last_scrobble(lastfm_username)
                    if last_scrobble:
                        if last_scrobble['date']['uts'] == int(time.time()):
                            embed.add_field(name="Last Scrobble", value=f"**Scrobbling Now**\n [{last_scrobble['name']}]({last_scrobble['url']})\n-# **By:** [{last_scrobble['artist']['name']}]({last_scrobble['artist']['url']})", inline=True)
                        else:
                            embed.add_field(name="Last Scrobble", value=f"[{last_scrobble['name']}]({last_scrobble['url']})\n-# **By:** [{last_scrobble['artist']['name']}]({last_scrobble['artist']['url']})\n<t:{last_scrobble['date']['uts']}:D>", inline=True)
                    else:
                        embed.add_field(name="Last Scrobble", value="No recent scrobbles", inline=True)

                    embed.add_field(name="Community Stats", value=f"-# **Friends:** {friended}\n-# **Followers:** {befriendedby}\n-# **Following:** {friended}", inline=True)

                    top_artists_str = "\n".join([f"-# **{i+1}.** [{artist['name']}]({artist['url']}) ({artist['playcount']})" for i, artist in enumerate(top_artists[:5] if isinstance(top_artists, list) else [])])
                    embed.add_field(name="Top Artists", value=top_artists_str, inline=True)

                    top_tracks = await self.fetch_top_tracks(lastfm_username)
                    top_tracks_str = "\n".join([f"-# **{i+1}.** [{track['name']}]({track['url']}) ({track['playcount']})" for i, track in enumerate(top_tracks[:5] if isinstance(top_tracks, list) else [])])
                    embed.add_field(name="Top Tracks", value=top_tracks_str, inline=True)

                    album_data = await self.fetch_top_albums(lastfm_username)
                    album_list = album_data["topalbums"]["album"]

                    top_albums_str = "\n".join([
                        f"-# **{i+1}.** [{album['name']}]({album['url']}) ({album['playcount']})"
                        for i, album in enumerate(album_list[:5])
                    ])

                    embed.add_field(name="Top Albums", value=top_albums_str or "No albums found.", inline=True)

                    embed.set_thumbnail(url=profile_picture)
                    embed.set_footer(text=f"{display_username} • {friended} friends • befriended by {befriendedby}", icon_url="https://git.cursi.ng/lastfm_logo.png")

                    view = discord.ui.View()
                    if not is_hidden:
                        view.add_item(
                            discord.ui.Button(
                                label="LastFM",
                                emoji=discord.PartialEmoji.from_str("<:lastfm:1275185763574874134>"),
                                style=discord.ButtonStyle.link,
                                url=f"https://www.last.fm/user/{lastfm_username}"
                            )
                        )

                    await interaction.followup.send(embed=embed, view=view)
            except Exception as e:
                await error_handler(interaction, e)

    async def fetch_last_scrobble(self, username):
        url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={username}&api_key={LASTFM_KEY}&format=json&limit=1"
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if 'recenttracks' in data and 'track' in data['recenttracks'] and len(data['recenttracks']['track']) > 0:
                    track = data['recenttracks']['track'][0]
                    track_info = {
                        'name': track['name'],
                        'artist': {
                            'name': track['artist']['#text'],
                            'url': f"https://www.last.fm/music/{track['artist']['#text'].replace(' ', '+')}"
                        },
                        'url': track['url']
                    }
                    if 'date' in track:
                        track_info['date'] = {'uts': track['date']['uts']}
                    else:
                        track_info['date'] = {'uts': int(time.time())}
                    return track_info
            return None

async def setup(client):
    await client.add_cog(Music(client))