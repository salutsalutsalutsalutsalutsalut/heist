import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from utils.db import check_blacklisted, check_booster, check_donor, check_owner, get_db_connection, redis_client
from utils.error import error_handler
from utils.cd import cooldown
from utils.cache import get_embed_color
from utils import default, permissions
from dotenv import dotenv_values
import random, aiohttp, io, pytz, time, datetime, secrets, asyncio, os, aiohttp, urllib.parse, re, json, math, ast, operator, tempfile
from pydub import AudioSegment
import decimal
from decimal import Decimal
from urllib.parse import quote, urljoin, urlparse, parse_qs
from utils.embed import cembed
from datetime import timedelta
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple
from functools import partial
import asyncpg
import pyfiglet
from lyricsgenius import Genius

fonts = [
    "3d-ascii", "3d_diagonal", "5lineoblique", "avatar", "braced", 
    "cards", "computer", "drpepper", "fun_face", "keyboard", "konto_slant"]

footer = "heist.lol"

config = dotenv_values(".env")
GENIUS_KEY = config["GENIUS_API_KEY"]

allowed_operators = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow
}

MAX_INPUT_LENGTH = 200
MAX_RECURSION_DEPTH = 20
MAX_EXECUTION_TIME = 2
MAX_NUMBER = Decimal('1e1000')

class SafeMathEvaluator:
    def __init__(self):
        self.start_time = None

    def evaluate_expression(self, expression):
        if len(expression) > MAX_INPUT_LENGTH:
            return "Error: Expression too long"

        try:
            decimal.getcontext().prec = 50
            self.start_time = time.time()
            tree = ast.parse(expression, mode='eval')
            for node in ast.walk(tree):
                if isinstance(node, ast.BinOp):
                    if type(node.op) not in allowed_operators:
                        raise ValueError("Unsupported operator")
            return self._eval_ast(tree.body, 0)
        except Exception as e:
            return f"Error: {e}"

    def _eval_ast(self, node, depth):
        if depth > MAX_RECURSION_DEPTH:
            raise ValueError("Maximum recursion depth exceeded")

        if time.time() - self.start_time > MAX_EXECUTION_TIME:
            raise ValueError("Execution time limit exceeded")

        if isinstance(node, ast.Expression):
            return self._eval_ast(node.body, depth + 1)
        elif isinstance(node, ast.BinOp):
            left = self._eval_ast(node.left, depth + 1)
            right = self._eval_ast(node.right, depth + 1)
            op_func = allowed_operators[type(node.op)]

            if isinstance(node.op, ast.Div) and right == 0:
                raise ValueError("Division by zero")

            if isinstance(node.op, ast.Pow):
                if left == 0 and right < 0:
                    raise ValueError("Zero cannot be raised to a negative power")
                if abs(right) > 1000:
                    raise ValueError("Exponent too large")

            result = op_func(Decimal(str(left)), Decimal(str(right)))
            if abs(result) > MAX_NUMBER:
                raise ValueError("Result too large")
            return result

        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_ast(node.operand, depth + 1)
            if isinstance(node.op, ast.UAdd):
                return +operand
            elif isinstance(node.op, ast.USub):
                return -operand
            else:
                raise ValueError("Unsupported unary operator")
        elif isinstance(node, ast.Num):
            if abs(Decimal(str(node.n))) > MAX_NUMBER:
                raise ValueError("Number too large")
            return Decimal(str(node.n))
        else:
            raise ValueError("Unsupported AST node")

class GiftButtonView(discord.ui.View):
    def __init__(self, disabled: bool = False):
        super().__init__(timeout=500)
        self.add_item(discord.ui.Button(
            label="Claim",
            custom_id="gift_click",
            disabled=disabled,
            style=discord.ButtonStyle.primary
        ))

class Fun(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.redis = redis_client
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    @app_commands.command(name="8ball")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(question="The question you want answers to.")
    @app_commands.check(permissions.is_blacklisted)
    async def eightball(self, interaction: discord.Interaction, question: str):
        """Consult 8ball to receive an answer."""
        ballresponse = [
            "Yes", "No", "Take a wild guess...", "Very doubtful",
            "Sure", "Without a doubt", "Most likely", 
            "Might be possible", "You'll be the judge",
            "no wtf", "no... baka", "yuh fosho", 
            "maybe man idk lol"
        ]

        answer = random.choice(ballresponse)
        await interaction.response.send_message(
            f"🎱 **Question:** {question}\n**Answer:** {answer}"
        )

    async def randomimageapi(self, interaction: discord.Interaction, url: str):
        async def call_after():
            try:
                async with self.session.get(url) as response:
                    if response.status != 200:
                        return await interaction.followup.send("The API seems to be down...")
                    r = await response.json()

            except aiohttp.ClientConnectorError:
                return await interaction.followup.send("The API seems to be down...")
            except aiohttp.ContentTypeError:
                return await interaction.followup.send("The API returned an error or didn't return JSON...")

            if isinstance(r, dict):
                image_url = r.get("file")

                if image_url:
                    await interaction.followup.send(image_url)
                else:
                    await interaction.followup.send("No image found in the response.")
            else:
                await interaction.followup.send("Unexpected response format.")

        await call_after()

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    @app_commands.describe(type="Type of animal.")
    async def animal(self, interaction: discord.Interaction, type: str):
        """Sends a random animal."""
        if type == "capybara":
            api_url = "https://api.capy.lol/v1/capybara"
            filename = "capybara.png"
            await self.fetch_capybara(interaction, api_url, filename)
        elif type in ["cat", "dog"]:
            url = f"https://api.alexflipnote.dev/{type}s"
            await self.randomimageapi(interaction, url)
        elif type in ["birb"]:
            url = f"https://api.alexflipnote.dev/{type}"
            await self.randomimageapi(interaction, url)
        else:
            await interaction.followup.send("Invalid animal type. Please use `birb`, `capybara`, `cat`, or `dog`.")

    async def fetch_capybara(self, interaction: discord.Interaction, api_url: str, filename: str):
        async def call_after():
            try:
                response = await self.session.get(api_url)

                if response.status == 200:
                    animal_bytes = await response.read()
                    animal_image = io.BytesIO(animal_bytes)
                    await interaction.followup.send(file=discord.File(animal_image, filename=filename))
                else:
                    await interaction.followup.send("Failed to fetch the animal.")
            except Exception as e:
                await error_handler(interaction, e)

        await call_after()

    @animal.autocomplete('type')
    async def type_autocomplete(self, interaction: discord.Interaction, current: str):
        options = ["birb", "capybara", "cat", "dog"]
        return [app_commands.Choice(name=option, value=option) for option in options if current.lower() in option.lower()]

    #@app_commands.command()
    #@app_commands.allowed_installs(guilds=True, users=True)
    #@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    #@app_commands.describe(text="What are we paying respect for?")
    #@app_commands.check(permissions.is_blacklisted)
    #async def f(self, interaction: discord.Interaction, text: str = None):
        #"""Press F to pay respect."""
        #hearts = ["❤", "💛", "💚", "💙", "💜"]
        #reason = f"for **{text}** " if text else ""

        #await interaction.response.send_message(
            #f"**{interaction.user.name}** has paid their respect {reason}{random.choice(hearts)}"
        #)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(search="The term you want to search for.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def urban(self, interaction: discord.Interaction, search: str):
        """Search the Urban Dictionary."""
        class UrbanView(View):
            def __init__(self, definitions: list, interaction: discord.Interaction):
                super().__init__(timeout=240)
                self.definitions = definitions
                self.current_page = 0
                self.interaction = interaction
                self.message = None

                self.update_button_states()

            def update_button_states(self):
                self.previous_button.disabled = (self.current_page == 0)
                self.next_button.disabled = (self.current_page == len(self.definitions) - 1)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary, custom_id="urbanleft")
            async def previous_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return

                if self.current_page > 0:
                    self.current_page -= 1
                    await interaction.response.defer()
                    self.update_button_states()
                    await self.update_content()

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary, custom_id="urbanright")
            async def next_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return

                if self.current_page < len(self.definitions) - 1:
                    self.current_page += 1
                    await interaction.response.defer()
                    self.update_button_states()
                    await self.update_content()

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary, custom_id="urbanskip")
            async def skip_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return

                class GoToPageModal(discord.ui.Modal, title="Go to Page"):
                    page_number = discord.ui.TextInput(label="Navigate to page", placeholder=f"Enter a page number (1-{len(self.definitions)})", min_length=1, max_length=len(str(len(self.definitions))))

                    async def on_submit(self, interaction: discord.Interaction):
                        try:
                            page = int(self.page_number.value) - 1
                            if page < 0 or page >= len(self.view.definitions):
                                raise ValueError
                            self.view.current_page = page
                            self.view.update_button_states()
                            await self.view.update_content()
                            await interaction.response.defer()
                        except ValueError:
                            await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

                modal = GoToPageModal()
                modal.view = self
                await interaction.response.send_modal(modal)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger, custom_id="urbandelete")
            async def delete_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return

                await interaction.response.defer()
                await interaction.delete_original_response()

            async def update_content(self):
                if self.message is None:
                    return

                definition_data = self.definitions[self.current_page]
                definition = definition_data['definition']
                word = definition_data['word']
                url = definition_data['permalink']

                if len(definition) >= 1000:
                    definition = definition[:1000].rsplit(" ", 1)[0] + "..."

                embed = await cembed(
                    interaction,
                    title=word,
                    url=url,
                    description=definition
                )

                if definition_data['example']:
                    embed.add_field(name="Example", value=definition_data['example'], inline=False)

                embed.set_author(
                    name=f"{self.interaction.user.name}", 
                    icon_url=self.interaction.user.avatar.url if self.interaction.user.avatar else self.interaction.user.default_avatar.url
                )
                embed.set_footer(
                    text=f"Page {self.current_page + 1}/{len(self.definitions)} | {definition_data['thumbs_up']} 👍 • {definition_data['thumbs_down']} 👎", 
                    icon_url="https://git.cursi.ng/heist.png?c"
                )
                await self.message.edit(embed=embed, view=self)

            async def start(self):
                definition_data = self.definitions[0]
                definition = definition_data['definition']
                word = definition_data['word']
                url = definition_data['permalink']

                if len(definition) >= 1000:
                    definition = definition[:1000].rsplit(" ", 1)[0] + "..."

                embed = await cembed(
                    interaction,
                    title=word,
                    url=url,
                    description=definition
                )

                if definition_data['example']:
                    embed.add_field(name="Example", value=definition_data['example'], inline=False)

                embed.set_author(
                    name=f"{self.interaction.user.name}", 
                    icon_url=self.interaction.user.avatar.url if self.interaction.user.avatar else self.interaction.user.default_avatar.url
                )
                embed.set_footer(
                    text=f"Page 1/{len(self.definitions)} | {definition_data['thumbs_up']} 👍 • {definition_data['thumbs_down']} 👎", 
                    icon_url="https://git.cursi.ng/heist.png?c"
                )
                response = await self.interaction.followup.send(embed=embed, view=self)
                self.message = response

        async def call_after():
            try:
                async with self.session.get(f"https://api.urbandictionary.com/v0/define?term={search}") as r:
                    if not r.ok:
                        await interaction.followup.send("I think the API broke..")
                        return

                    data = await r.json()
                    if not data["list"]:
                        await interaction.followup.send("Couldn't find your search in the dictionary...")
                        return

                    definitions = sorted(data["list"], reverse=True, key=lambda g: int(g["thumbs_up"]))

                    if not definitions:
                        await interaction.followup.send("No definitions found.")
                        return

                    view = UrbanView(definitions, interaction)
                    await view.start()
                        
            except Exception as e:
                await error_handler(interaction, e)
        await call_after()

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(song="The song you want to get the lyrics of.")
    @app_commands.check(permissions.is_blacklisted)
    async def lyrics(self, interaction: discord.Interaction, song: str):
        """Get the lyrics of a song."""
        await interaction.response.defer(thinking=True)
        try:
            async def fetch_lyrics(song: str):
                try:
                    loop = asyncio.get_running_loop()
                    genius = Genius(GENIUS_KEY)
                    genius.remove_section_headers = True
                    genius.skip_non_songs = True
                    genius.excluded_terms = ["(Remix)", "(Live)"]

                    song_obj = await loop.run_in_executor(None, genius.search_song, song)

                    if song_obj and song_obj.lyrics and song_obj.lyrics.strip():
                        lyrics = song_obj.lyrics
                        if "Lyrics" in lyrics:
                            lyrics_index = lyrics.find("Lyrics")
                            lyrics = lyrics[lyrics_index + len("Lyrics"):].strip()
                        
                        return lyrics, song_obj.title, song_obj.artist, song_obj.url, song_obj.song_art_image_url
                    else:
                        return None, None, None, None, None
                except Exception as e:
                    return None, None, None, None, None

            def split_lyrics(lyrics: str):
                if not lyrics:
                    return []
                paragraphs = lyrics.split("\n\n")
                paragraphs = [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]
                return paragraphs

            class GoToPageModal(discord.ui.Modal):
                def __init__(self, max_pages: int, view) -> None:
                    super().__init__(title="Go to Page")
                    self.view = view
                    self.page_number = discord.ui.TextInput(
                        label="Navigate to page",
                        placeholder=f"Enter a page number (1-{max_pages})",
                        min_length=1,
                        max_length=len(str(max_pages))
                    )
                    self.add_item(self.page_number)

                async def on_submit(self, interaction: discord.Interaction):
                    try:
                        page = int(self.page_number.value) - 1
                        if 0 <= page < len(self.view.pages):
                            self.view.current_page = page
                            self.view.update_button_states()
                            await self.view.update_content()
                            await interaction.response.defer()
                        else:
                            await interaction.response.send_message("Invalid page number.", ephemeral=True)
                    except ValueError:
                        await interaction.response.send_message("Please enter a valid number.", ephemeral=True)

            class LyricsView(discord.ui.View):
                def __init__(self, pages: list, interaction: discord.Interaction, session: aiohttp.ClientSession, use_embeds: bool = True, has_audio: bool = False):
                    super().__init__(timeout=240)
                    self.pages = pages
                    self.current_page = 0
                    self.interaction = interaction
                    self.message = None
                    self.use_embeds = use_embeds
                    self.has_audio = has_audio
                    self.session = session
                    self.update_button_states()

                def update_button_states(self):
                    self.previous_button.disabled = (self.current_page == 0)
                    self.next_button.disabled = (self.current_page == len(self.pages) - 1)
                    self.audio_button.disabled = not self.has_audio

                async def update_content(self):
                    if self.message is None:
                        return

                    content = self.pages[self.current_page]
                    if self.use_embeds:
                        embed = await cembed(
                            self.interaction,
                            title=f"{title} - {artist}",
                            description=f"```yaml\n{content}```",
                            url=genius_url
                        )
                        embed.set_author(name=f"{self.interaction.user.name}", icon_url=self.interaction.user.avatar.url if self.interaction.user.avatar else self.interaction.user.default_avatar.url)
                        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)} • {footer}", icon_url="https://git.cursi.ng/genius_logo.png")
                        embed.set_thumbnail(url=cover_image)
                        await self.message.edit(embed=embed, view=self)
                    else:
                        content_text = f"```yaml\n{content}```\nPage **`{self.current_page + 1}/{len(self.pages)}`**\n\n-# Missing the `Embed Links` permission in this server, so no embed for you."
                        await self.message.edit(content=content_text, view=self)

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary, custom_id="lyricsleft")
                async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                        return

                    await interaction.response.defer()
                    if self.current_page > 0:
                        self.current_page -= 1
                        self.update_button_states()
                        await self.update_content()

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary, custom_id="lyricsright")
                async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                        return

                    await interaction.response.defer()
                    if self.current_page < len(self.pages) - 1:
                        self.current_page += 1
                        self.update_button_states()
                        await self.update_content()

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary, custom_id="lyricsskip")
                async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                        return

                    modal = GoToPageModal(len(self.pages), self)
                    await interaction.response.send_modal(modal)

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:audio:1345517095101923439>"), style=discord.ButtonStyle.secondary, custom_id="lyricsaudio")
                async def audio_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer(ephemeral=True)
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    }
                    query = f"{title} {artist}"
                    async with self.session.get(f"https://api.stats.fm/api/v1/search/elastic?query={query}%20{artist}&type=track&limit=5", headers=headers) as response:
                        if response.status != 200:
                            await interaction.followup.send("Failed to fetch track data.", ephemeral=True)
                            return
                        
                        data = await response.json()
                        tracks = data.get("items", {}).get("tracks", [])

                        if not tracks:
                            await interaction.followup.send("No tracks found.", ephemeral=True)
                            return

                        genius_title = title.lower().strip()
                        genius_artist = artist.lower().strip()

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
                            await interaction.followup.send("No matching track found.", ephemeral=True)
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

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger, custom_id="lyricsdelete")
                async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                        return

                    await interaction.response.defer()
                    await interaction.delete_original_response()

                async def on_timeout(self):
                    for item in self.children:
                        if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                            item.disabled = True

                    try:
                        await self.message.edit(view=self)
                    except discord.NotFound:
                        pass

            lyrics, title, artist, genius_url, cover_image = await fetch_lyrics(song)
            if lyrics:
                pages = split_lyrics(lyrics)

                if not pages:
                    await interaction.followup.send("Lyrics not found.")
                    return

                has_audio = False
                query = f"{title} {artist}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                async with self.session.get(f"https://api.stats.fm/api/v1/search/elastic?query={query}%20{artist}&type=track&limit=5", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        tracks = data.get("items", {}).get("tracks", [])

                        if tracks:
                            genius_title = title.lower().strip()
                            genius_artist = artist.lower().strip()

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

                use_embeds = interaction.app_permissions.embed_links
                if use_embeds:
                    embed = await cembed(
                        interaction,
                        title=f"{title} - {artist}",
                        description=f"```yaml\n{pages[0]}```",
                        url=genius_url
                    )
                    embed.set_author(name=f"{interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
                    embed.set_footer(text=f"Page 1/{len(pages)} • {footer}", icon_url="https://git.cursi.ng/genius_logo.png")
                    embed.set_thumbnail(url=cover_image)
                    view = LyricsView(pages, interaction, session=self.session, use_embeds=True, has_audio=has_audio)
                    message = await interaction.followup.send(embed=embed, view=view)
                else:
                    content = f"```yaml\n{pages[0]}```\nPage **`1/{len(pages)}`**\n\n-# Missing the `Embed Links` permission in this server, so no embed for you."
                    view = LyricsView(pages, interaction, session=self.session, use_embeds=False, has_audio=has_audio)
                    message = await interaction.followup.send(content=content, view=view)

                view.message = await interaction.original_response()
            else:
                await interaction.followup.send("Lyrics not found.")
        except Exception as e:
            await error_handler(interaction, e)

    @lyrics.autocomplete('song')
    async def lyrics_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if not current:
            default_songs = [
                "how u feel? - Destroy Lonely",
                "if looks could kill - Destroy Lonely",
                "JETLGGD - Destroy Lonely",
                "Foreign - Playboi Carti",
                "Freestyle 2 - Ken Carson",
                "overseas - Ken Carson",
                "NEVEREVER - Destroy Lonely",
                "Jennifer's Body - Ken Carson",
                "NOSTYLIST - Destroy Lonely",
                "ILoveUIHateU - Playboi Carti"
            ]
            return [app_commands.Choice(name=song, value=song) for song in default_songs]
        try:
            genius = Genius(GENIUS_KEY)
            genius.remove_section_headers = True
            genius.skip_non_songs = True
            genius.excluded_terms = ["(Remix)", "(Live)"]

            search_results = await asyncio.to_thread(genius.search_songs, current)
            
            choices = []
            for hit in search_results['hits'][:25]:
                song_title = hit['result']['title']
                artist_name = hit['result']['artist_names']
                choice_name = f"{song_title} - {artist_name}"
                if len(choice_name) > 100:
                    choice_name = choice_name[:97] + "..."
                choices.append(app_commands.Choice(name=choice_name, value=choice_name))
            
            return choices
        except Exception as e:
            return []

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(emoji1="The first emoji to mix.", emoji2="The second emoji to mix.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def emojimix(self, interaction: discord.Interaction, emoji1: str, emoji2: str):
        """Mix two emojis together."""
        try:
            url = f"https://emojik.vercel.app/s/{urllib.parse.quote(emoji1)}_{urllib.parse.quote(emoji2)}?size=256"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    file = discord.File(io.BytesIO(data), filename="heist.png")
                    await interaction.followup.send(file=file)
                else:
                    await interaction.followup.send("Failed to mix emojis. Please try again later.")
        except Exception as e:
            await error_handler(interaction, e)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user you want to check the pp size of.")
    @app_commands.check(permissions.is_blacklisted)
    async def ppsize(self, interaction: discord.Interaction, user: discord.User = None):
        """Check the size of someone's pp."""
        user = user or interaction.user

        length = random.randint(1, 20)
        pp = "=" * length
        emoji = "D"

        await interaction.response.send_message(
            f"**{user.name}**'s pp:\n**`8{pp}{emoji}`**"
        )

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(thing="The thing you want to rate.")
    @app_commands.check(permissions.is_blacklisted)
    async def rate(self, interaction: discord.Interaction, thing: str):
        """Rates what you desire."""
        if thing.lower() in ["csyn", "cosmin", "heist", "raluca", "hyqos"]:
            rating = 1000
        elif thing.lower() in ["mihaela", "mira", "yjwe"]:
            rating = -1000
        else:
            rating = random.uniform(0.0, 100.0)
        await interaction.response.send_message(
            f"I'd rate `{thing}` a **{round(rating, 4)} / 100**"
        )

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user you want to check the gayness of.")
    @app_commands.check(permissions.is_blacklisted)
    async def howgay(self, interaction: discord.Interaction, user: discord.User = None):
        """Check how gay someone is."""
        user = user or interaction.user
        
        if user.id == 1234025578232025122:
            await interaction.response.send_message("cosmin is NOT gay 😭🙏🏿")
            return
    
        rgay = random.randint(1, 100)
        gay = rgay / 1.17

        emoji = (
            "🏳️‍🌈" if gay > 75 else
            "🤑" if gay > 50 else
            "🤫" if gay > 25 else
            "🔥"
        )

        await interaction.response.send_message(
            f"**{user.name}** is **{gay:.2f}%** gay {emoji}"
        )

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user you want to check the autism of.")
    @app_commands.check(permissions.is_blacklisted)
    async def howautistic(self, interaction: discord.Interaction, user: discord.User = None):
        """Check how autistic someone is."""
        user = user or interaction.user

        if user.id == 1234025578232025122:
            await interaction.response.send_message("cosmin is NOT autistic 😭🙏🏿")
            return

        rautistic = random.randint(1, 100)
        autistic = rautistic / 1.17

        emoji = (
            "🧩" if autistic > 75 else
            "🧠" if autistic > 50 else
            "🤐" if autistic > 25 else
            "🔥"
        )

        await interaction.response.send_message(
            f"**{user.name}** is **{autistic:.2f}%** autistic {emoji}"
        )

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user you want to rate.")
    @app_commands.check(permissions.is_blacklisted)
    async def hotcalc(self, interaction: discord.Interaction, user: discord.User = None):
        """Returns a random percent for how hot a Discord user is."""
        user = user or interaction.user
        r = random.randint(1, 100)
        hot = r / 1.17

        emoji = (
            "💞" if hot > 75 else
            "💖" if hot > 50 else
            "❤" if hot > 25 else
            "💔"
        )

        await interaction.response.send_message(
            f"**{user.name}** is **{hot:.2f}%** hot {emoji}"
        )

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def nitro(self, interaction: discord.Interaction):
        """Why not send a little gift?"""
        expiration_date = datetime.datetime.utcnow() + timedelta(hours=24)
        expiration_timestamp = int(expiration_date.timestamp())
        expiration_formatted = f"<t:{expiration_timestamp}:R>"
        
        embed = discord.Embed(
            title="You've been gifted a subscription!",
            description=f"You've been gifted Nitro for **1 month**!\nExpires **{expiration_formatted}**\n\n[**Disclaimer**](https://csyn.me/disclaimer)",
            color=0x7289DA
        )
        embed.set_thumbnail(url="https://git.cursi.ng/nitro_logo.jpeg")

        class NitroView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=240)

            @discord.ui.button(label="Claim", style=discord.ButtonStyle.blurple)
            async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_message("https://git.cursi.ng/rickroll.gif", ephemeral=True)

            async def on_timeout(self):
                await interaction.delete_original_response()

        view = NitroView()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(text="The text you want to convert to ASCII art.", font="The font you want to use for the ASCII art.")
    @app_commands.check(permissions.is_blacklisted)
    async def asciify(self, interaction: discord.Interaction, text: str, font: str = "3d-ascii"):
        """Convert text to ASCII art."""
        await interaction.response.defer(thinking=True)

        if font not in fonts:
            await interaction.followup.send(f"Invalid font. Available fonts are: {', '.join(fonts)}", ephemeral=True)
            return

        try:
            ascii_art = await asyncio.to_thread(pyfiglet.figlet_format, text, font=font)
            await interaction.followup.send(f"```fix\n{ascii_art}\n```")
        except Exception as e:
            await interaction.followup.send("Text is too long to display.", ephemeral=True)

    @asciify.autocomplete("font")
    async def asciify_autocomplete(self, interaction: discord.Interaction, current: str):
        filtered_fonts = [font for font in fonts if current.lower() in font.lower()]
        choices = [app_commands.Choice(name=font, value=font) for font in filtered_fonts]
        await interaction.response.autocomplete(choices)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(expression="The expression to calculate.")
    @app_commands.check(permissions.is_blacklisted)
    async def math(self, interaction: discord.Interaction, expression: str):
        """Calculate stuff."""
        evaluator = SafeMathEvaluator()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, evaluator.evaluate_expression, expression)
        await interaction.response.send_message(f"Result: {result}")

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def coinflip(self, interaction: discord.Interaction):
        """Flip a coin."""
        try:
            result = "Heads" if secrets.randbelow(2) == 0 else "Tails"
            await interaction.response.send_message(f"{result}.")
        except Exception as e:
            await error_handler(interaction, e)

    async def async_image_process(self, func, *args, **kwargs):
        return await self.client.loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def create_circle_mask(self, size: Tuple[int, int]) -> Image.Image:
        return await self.async_image_process(self._create_circle_mask, size)

    def _create_circle_mask(self, size: Tuple[int, int]) -> Image.Image:
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + size, fill=255)
        return mask

    async def create_love_image(self, author_bytes: bytes, target_bytes: bytes, love_percent: int, bar_color: Tuple[int, int, int]) -> bytes:
        author_avatar = await self.async_image_process(Image.open, io.BytesIO(author_bytes))
        target_avatar = await self.async_image_process(Image.open, io.BytesIO(target_bytes))

        base = await self.async_image_process(Image.new, 'RGBA', (400, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)

        avatar_size = (100, 100)
        
        if author_avatar.mode != 'RGBA':
            author_avatar = await self.async_image_process(author_avatar.convert, 'RGBA')
        if target_avatar.mode != 'RGBA':
            target_avatar = await self.async_image_process(target_avatar.convert, 'RGBA')
            
        author_avatar = await self.async_image_process(author_avatar.resize, avatar_size, Image.LANCZOS)
        target_avatar = await self.async_image_process(target_avatar.resize, avatar_size, Image.LANCZOS)

        circle_mask = await self.create_circle_mask(avatar_size)
        author_avatar.putalpha(circle_mask)
        target_avatar.putalpha(circle_mask)

        await self.async_image_process(base.paste, author_avatar, (50, 25), author_avatar)
        await self.async_image_process(base.paste, target_avatar, (250, 25), target_avatar)

        try:
            if love_percent >= 80:
                heart_symbol = await self.async_image_process(Image.open, "/heist/structure/assets/growing_heart.png")
            elif love_percent >= 50:
                heart_symbol = await self.async_image_process(Image.open, "/heist/structure/assets/smiling_hearts_face.png")
            elif love_percent >= 30:
                heart_symbol = await self.async_image_process(Image.open, "/heist/structure/assets/broken_heart.png")
            elif love_percent >= 15:
                heart_symbol = await self.async_image_process(Image.open, "/heist/structure/assets/crying_face.png")
            else:
                heart_symbol = await self.async_image_process(Image.open, "/heist/structure/assets/skull_face.png")

            heart_symbol = await self.async_image_process(heart_symbol.resize, (100, 100), Image.LANCZOS)
            midpoint_x = (50 + 350) // 2
            heart_x = midpoint_x - 50
            
            await self.async_image_process(base.paste, heart_symbol, (heart_x, 30), heart_symbol)
        except Exception as e:
            print(e)
            await self.async_image_process(
                draw.text, 
                (175, 50), 
                "<3" if love_percent >= 50 else "</3", 
                font=ImageFont.truetype("DejaVuSans.ttf", 30),
                fill=(255, 0, 0) if love_percent >= 50 else (0, 0, 0)
            )

        bar_width, bar_height = 300, 20
        bar_x, bar_y = 50, 150

        await self.async_image_process(
            draw.rectangle,
            [(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)],
            fill=(169, 169, 169)
        )
            
        progress_width = int(bar_width * (love_percent / 100))
        await self.async_image_process(
            draw.rectangle,
            [(bar_x, bar_y), (bar_x + progress_width, bar_y + bar_height)],
            fill=bar_color
        )
        
        percent_text = f"{love_percent}% love"
        font = ImageFont.truetype("DejaVuSans.ttf", 14)
        text_bbox = await self.async_image_process(font.getbbox, percent_text)
        text_width = text_bbox[2] - text_bbox[0]
        
        text_x = bar_x + (bar_width - text_width) // 2
        text_y = bar_y + (bar_height - 14) // 2
        
        brightness = (bar_color[0] * 0.299 + bar_color[1] * 0.587 + bar_color[2] * 0.114)
        text_color = (0, 0, 0) if brightness > 128 else (255, 255, 255)
        
        await self.async_image_process(
            draw.text,
            (text_x, text_y),
            percent_text,
            font=font,
            fill=text_color
        )

        image_binary = io.BytesIO()
        await self.async_image_process(base.save, image_binary, format='PNG')
        return image_binary.getvalue()

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @permissions.requires_perms(embed_links=True, attach_files=True)
    @app_commands.check(permissions.is_blacklisted)
    async def ship(self, interaction: discord.Interaction, user1: discord.User, user2: discord.User = None):
        "Ship two users together."
        try:
            love_percent = random.randint(0, 100)

            user2 = user2 or interaction.user
            try:
                user1_url = user1.display_avatar.with_size(512).url if user1.display_avatar else user1.default_avatar.url
                user2_url = user2.display_avatar.with_size(512).url if user2.display_avatar else user2.default_avatar.url

                async with self.session.get(user1_url) as resp:
                    user1_bytes = await resp.read()
                async with self.session.get(user2_url) as resp:
                    user2_bytes = await resp.read()
                
                user_color = await get_embed_color(str(interaction.user.id))
                color_tuple = (
                    (user_color >> 16) & 255,
                    (user_color >> 8) & 255,
                    user_color & 255
                )
                
                image_bytes = await self.create_love_image(user1_bytes, user2_bytes, love_percent, color_tuple)
                
                combined_name = user1.name[:len(user1.name)//2] + user2.name[len(user2.name)//2:]
                combined_name = combined_name.lower()

                embed = await cembed(interaction,
                    title=f"**{combined_name} 💕**"
                )
                file = discord.File(fp=io.BytesIO(image_bytes), filename='love.png')
                embed.set_image(url="attachment://love.png")

                await interaction.followup.send(file=file, embed=embed)

            except Exception as e:
                await error_handler(interaction, e)
                return
        
        except Exception as e:
            await error_handler(interaction, e)

async def setup(client):
    await client.add_cog(Fun(client))