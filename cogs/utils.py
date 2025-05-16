import discord
from discord import app_commands, Interaction, Attachment, Webhook, ButtonStyle, Forbidden, File, Embed
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput, Select
from dotenv import dotenv_values
from langcodes import Language
from googletrans import Translator, LANGUAGES
from utils.db import check_donor, check_owner, get_db_connection, redis_client
from utils.cd import cooldown
from utils.error import error_handler
from utils.embed import cembed
from utils import default, permissions, messages
import io, subprocess, urllib.parse, shutil, re, brotli
from io import StringIO, BytesIO
import json, asyncio, subprocess, traceback, sys, os, base64, aiohttp, aiofiles, time, datetime, string, random, textwrap, uwuify, tempfile, functools, hashlib
import aiofiles.os
from pydub import AudioSegment
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageSequence, ImageEnhance, ImageChops
from shazamio import Shazam
from better_profanity import Profanity
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from pytube import Search
from pytubefix import YouTube
import pytesseract
import emoji
import shutil
import zipfile
import redis
import inspect
import yt_dlp
import pytz
import uuid
from eth_utils import to_checksum_address
from typing import Literal, List
from concurrent.futures import ThreadPoolExecutor
from lyricsgenius import Genius

footer = "heist.lol"
config = dotenv_values(".env")
TOKEN = config["DISCORD_TOKEN"]
API_KEY = config["HEIST_API_KEY"]
BYPASSVIP_KEY = config["BYPASSVIP_API_KEY"]
BLOCKCHAIR_KEY = config["BLOCKCHAIR_API_KEY"]
SPACE_KEY = config["SPACE_API_KEY"]
SAUCENAO_KEY = config["SAUCENAO_API_KEY"]
client_id = config["SPOTIFY_CLIENT_ID"]
client_secret = config["SPOTIFY_SECRET"]
redirect_uri = config["SPOTIFY_REDIRECT"]
GENIUS_KEY = config["GENIUS_API_KEY"]

valid_languages = [
    "English", "Spanish", "French", "German", "Italian", "Portuguese",
    "Russian", "Japanese", "Korean", "Arabic", "Dutch", "Swedish",
    "Norwegian", "Danish", "Finnish", "Polish", "Turkish", "Hungarian",
    "Romanian", "Czech", "Slovak", "Thai", "Indonesian", "Vietnamese"]

real_languages = [
    "English", "Spanish", "French", "German", "Italian", "Portuguese",
    "Russian", "Japanese", "Korean", "Arabic", "Dutch", "Swedish",
    "Norwegian", "Danish", "Finnish", "Polish", "Turkish", "Hungarian",
    "Romanian", "Czech", "Slovak", "Thai", "Indonesian", "Vietnamese",
    "Chinese (Traditional)", "Chinese (Simplified)", "Norwegian", "Swedish",
    "Danish", "Mandarin", "Korean", "Hindi", "Bengali", "Czech", "Albanian"]

SUPPORTED_EXTENSIONS = ['mp3', 'wav', 'm4a', 'opus']

class Utility(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.translator = Translator()
        self.redis = redis_client
        self.session = aiohttp.ClientSession()
        self.ctx_tospeech = app_commands.ContextMenu(
            name='Text to Speech',
            callback=self.tospeech,
        )
        self.ctx_translate = app_commands.ContextMenu(
            name='Translate to English',
            callback=self.toenglish,
        )
        self.ctx_totext = app_commands.ContextMenu(
            name='Image to Text (OCR)',
            callback=self.totext,
        )
        self.ctx_toimage = app_commands.ContextMenu(
            name='Get Sticker/Emoji',
            callback=self.toimage,
        )
        self.ctx_transcribe = app_commands.ContextMenu(
            name='Transcribe VM',
            callback=self.transcribevm,
        )
        #self.client.tree.add_command(self.ctx_tospeech)
        self.client.tree.add_command(self.ctx_translate)
        self.client.tree.add_command(self.ctx_transcribe)
        self.client.tree.add_command(self.ctx_totext)
        self.client.tree.add_command(self.ctx_toimage)

    async def cog_unload(self) -> None:
        self.client.tree.remove_command(self.ctx_tospeech.name, type=self.ctx_tospeech.type)
        self.client.tree.remove_command(self.ctx_translate.name, type=self.ctx_translate.type)
        self.client.tree.remove_command(self.ctx_transcribe.name, type=self.ctx_transcribe.type)
        self.client.tree.remove_command(self.ctx_toimage.name, type=self.ctx_toimage.type)
        self.client.tree.remove_command(self.ctx_totext.name, type=self.ctx_totext.type)
        await self.session.close()

    aitools = app_commands.Group(
        name="ask", 
        description="AI related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
   )

    get = app_commands.Group(
        name="get", 
        description="Pfp generation commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
   )

    soundcloud = app_commands.Group(
        name="soundcloud", 
        description="SoundCloud related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
   )

    spotify = app_commands.Group(
        name="spotify", 
        description="Spotify related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
   )

    crypto = app_commands.Group(
        name="crypto", 
        description="Crypto related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    google = app_commands.Group(
        name="google", 
        description="Google related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    brave = app_commands.Group(
        name="brave",
        description="Brave related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    bitcoin = app_commands.Group(
        name="bitcoin",
        description="Bitcoin related Crypto commands",
        parent=crypto 
    )

    ethereum = app_commands.Group(
        name="ethereum",
        description="Ethereum related Crypto commands",
        parent=crypto 
    )

    litecoin = app_commands.Group(
        name="litecoin",
        description="Litecoin related Crypto commands",
        parent=crypto 
    )

    base64 = app_commands.Group(
        name="base64",
        description="Base64 related commands",
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    )

    timezone = app_commands.Group(
        name="timezone",
        description="Timezone related commands",
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    )

    convert = app_commands.Group(
        name="convert", 
        description="Conversion related commands",
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    )
    
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def tospeech(self, interaction: Interaction, message: discord.Message) -> None:

        text = message.content or (message.embeds[0].title + ' ' + message.embeds[0].description if message.embeds else None)

        if text is None:
            await interaction.followup.send("No text available to convert to speech.", ephemeral=True)
            return
        
        invalid_chars = {'.', ',', '/', '\\'}
        if set(text) <= invalid_chars:
            await interaction.followup.send("No audio could be generated. Invalid character.", ephemeral=True)
            return
        if len(text) > 300:
            await interaction.followup.send("Text too long. Maximum 300 characters allowed.", ephemeral=True)
            return

        try:
            start_time = time.time()
            headers = {'Content-Type': 'application/json'}
            selected_voice = 'en_us_001'

            json_data = {'text': text, 'voice': selected_voice}

            async with self.session.post('https://tiktok-tts.weilnet.workers.dev/api/generation', headers=headers, json=json_data) as response:
                data = await response.json()

                if 'data' not in data or data['data'] is None:
                    await interaction.followup.send("API did not return anything. Please try again later.")
                    return

                audio = base64.b64decode(data['data'])
                rnum = random.randint(100, 999)
                filename = f"tts_{rnum}.mp3"

                async with aiofiles.open(filename, 'wb') as f:
                    await f.write(audio)

                end_time = time.time()
                duration = end_time - start_time

                embed = await cembed(
                    interaction,
                    description=f"<:audio:1345517095101923439> Audio generated in `{duration:.2f}s`.",
                )

                if interaction.app_permissions.embed_links:
                    await interaction.followup.send(f"Prompt: {text}", embed=embed, file=File(filename))
                else:
                    await interaction.followup.send(f"Prompt: {text}", file=File(filename))

        except Exception as e:
            await error_handler(interaction, e)

        finally:
            if filename and os.path.exists(filename):
                await aiofiles.os.remove(filename)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def toenglish(self, interaction: Interaction, message: discord.Message) -> None:
        try:
            if message.content:
                text_to_translate = message.content
            else:
                if message.embeds:
                    embed = message.embeds[0]
                    text_to_translate = (embed.title or '') + ' ' + (embed.description or '')
                elif message.attachments:
                    await interaction.response.send_message("You cannot use this on a message containing images/files.", ephemeral=True)
                    return
                elif message.stickers:
                    await interaction.response.send_message("You cannot use this on a message containing stickers.", ephemeral=True)
                    return
                else:
                    await interaction.response.send_message("No text available to translate.", ephemeral=True)
                    return
            
            detected_lang = self.translator.detect(text_to_translate)
            detected_lang_name = LANGUAGES.get(detected_lang.lang, detected_lang.lang.title()).capitalize()
            translated = self.translator.translate(text_to_translate, dest='en').text
            translation = translated[:997] + "..." if len(translated) > 997 else translated
            
            author_username = message.author.name
            user_id = str(interaction.user.id)
            
            await interaction.response.send_message(f"{translation}\n\nTranslated from **{detected_lang_name}**")
            
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def totext(self, interaction: Interaction, message: discord.Message) -> None:
        class TextView(discord.ui.View):
            def __init__(self, pages, interaction):
                super().__init__(timeout=240)
                self.pages = pages
                self.current_page = 0
                self.interaction = interaction
                self.message = None
                self.update_button_states()

            def update_button_states(self):
                self.previous_button.disabled = self.current_page == 0
                self.next_button.disabled = self.current_page == len(self.pages) - 1

            async def update_content(self):
                if self.message is None:
                    return
                content = self.pages[self.current_page]
                await self.message.edit(content=f"Page {self.current_page + 1}/{len(self.pages)}\n\n{content}", view=self)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary)
            async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return
                await interaction.response.defer()
                if self.current_page > 0:
                    self.current_page -= 1
                    self.update_button_states()
                    await self.update_content()

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary)
            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return
                await interaction.response.defer()
                if self.current_page < len(self.pages) - 1:
                    self.current_page += 1
                    self.update_button_states()
                    await self.update_content()

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary)
            async def sort_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return
                modal = GoToPageModal(len(self.pages), self)
                await interaction.response.send_modal(modal)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger)
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

        class GoToPageModal(discord.ui.Modal):
            def __init__(self, max_pages: int, view):
                super().__init__(title="Go to Page")
                self.view = view
                self.page_number = discord.ui.TextInput(
                    label="Navigate to page",
                    placeholder=f"Enter a page number (1-{max_pages})",
                    min_length=1,
                    max_length=len(str(max_pages)))
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

        await interaction.response.defer(thinking=True)
        user = interaction.user
        is_owner = await check_owner(user.id)
        if not is_owner:
            is_donor = await check_donor(user.id)
            limit = 200 if is_donor else 50
            today = datetime.utcnow().strftime('%Y-%m-%d')
            user_key = f"ocr:{user.id}:{today}"
            user_count = int(await redis_client.get(user_key) or 0)
            if user_count >= limit:
                await interaction.followup.send("You can only OCR 50 images every day, but you can transcribe up to 200 images with **Premium**. </premium buy:1278389799857946700>", ephemeral=True)
                return

        image_url = None
        if message.attachments:
            image_attachment = message.attachments[0]
            if image_attachment.content_type.startswith('image'):
                image_url = image_attachment.url
        elif message.content:
            urls = [word for word in message.content.split() if word.startswith('http')]
            for url in urls:
                parsed_url = urlparse(url)
                if parsed_url.path.endswith('.gif'):
                    await interaction.followup.send("Attachment needs to be an image, GIF files are not supported.", ephemeral=True)
                    return
                if parsed_url.path.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp')):
                    image_url = url
                    break

        if not image_url:
            await interaction.followup.send("No valid image found in the message.", ephemeral=True)
            return

        try:
            async with self.session.get(image_url) as resp:
                if resp.status != 200:
                    await interaction.followup.send("Failed to download the image.", ephemeral=True)
                    return
                image_data = await resp.read()

            if len(image_data) > 1 * 1024 * 1024:
                def process_image(data):
                    image = Image.open(BytesIO(data))
                    image = image.convert("RGB")
                    output = BytesIO()
                    image.save(output, format="JPEG", quality=85)
                    compressed_data = output.getvalue()
                    output.close()
                    return compressed_data

                image_data = await asyncio.to_thread(process_image, image_data)

            api_url = "https://api.ocr.space/parse/image"
            form_data = aiohttp.FormData()
            form_data.add_field('apikey', SPACE_KEY)
            form_data.add_field('language', 'eng')
            form_data.add_field('file', image_data, filename='image.jpg', content_type='image/jpeg')

            async with self.session.post(api_url, data=form_data) as response:
                if response.status != 200:
                    try:
                        def tesseract_fallback(data):
                            image = Image.open(BytesIO(data))
                            return pytesseract.image_to_string(image)

                        text = await asyncio.to_thread(tesseract_fallback, image_data)
                        if not text.strip():
                            await interaction.followup.send("No text could be extracted from the image.", ephemeral=True)
                            return
                    except Exception as e:
                        await interaction.followup.send("OCR service error and fallback failed. Could not process image.", ephemeral=True)
                        return
                else:
                    result = await response.json()
                    parsed_results = result.get('ParsedResults', [])
                    text = parsed_results[0]['ParsedText'] if parsed_results else ''

            if not is_owner:
                await redis_client.incr(user_key)
                await redis_client.expire(user_key, 86400)

            if len(text) <= 10000:
                cache_key = hashlib.md5(image_data).hexdigest()
                await redis_client.setex(cache_key, 300, text)

            pages = []
            for i in range(0, len(text), 500):
                page_text = text[i:i+500]
                if i + 500 < len(text):
                    page_text += "..."
                pages.append(f"{page_text}\n\nPage {i//500 + 1}/{(len(text) - 1)//500 + 1}")

            view = TextView(pages, interaction)
            message = await interaction.followup.send(pages[0], view=view)
            view.message = message

        except Exception as e:
            print(e)
            await error_handler(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def transcribevm(self, interaction: Interaction, message: discord.Message) -> None:
        try:
            if not message.attachments or not message.attachments[0].filename.lower().endswith(('.wav', '.mp3', '.ogg', '.opus')):
                await interaction.response.send_message("The message does not contain a supported voice message format.", ephemeral=True)
                return

            await interaction.response.defer(thinking=True)
            attachment = message.attachments[0]

            user_id = str(interaction.user.id)
            is_donor = await check_donor(interaction.user.id)
            is_owner = await check_owner(interaction.user.id)
            daily_limit = 30 if is_donor else 10
            max_duration = 150000 if is_donor else 30000

            if not is_owner:
                cooldown_key = f"cooldown:transcribe:{user_id}"
                current_count = await self.redis.get(cooldown_key)
                current_count = int(current_count) if current_count else 0

                if current_count >= daily_limit:
                    await interaction.followup.send("You can only transcribe 5 VMs every day, but you can transcribe up to 20 VMs with **Premium**. </premium buy:1278389799857946700>", ephemeral=True)
                    return

                await self.redis.incr(cooldown_key)
                if current_count == 0:
                    await self.redis.expire(cooldown_key, 86400)

            format = attachment.filename.split('.')[-1].lower()
            
            async with self.session.get(attachment.url) as response:
                audio_data = await response.read()

            async def convert_audio(data, fmt):
                if fmt == 'opus':
                    process = await asyncio.create_subprocess_exec(
                        'ffmpeg', '-i', 'pipe:0', '-f', 'wav', '-ac', '1', '-ar', '16000', 'pipe:1',
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate(input=data)
                    if process.returncode != 0:
                        raise Exception(f"FFmpeg error: {stderr.decode()}")
                    return await asyncio.to_thread(lambda: AudioSegment.from_file(io.BytesIO(stdout), format='wav'))
                return await asyncio.to_thread(lambda: AudioSegment.from_file(io.BytesIO(data), format=fmt))

            audio_segment = await convert_audio(audio_data, format)
            audio_duration = len(audio_segment)

            if audio_duration > max_duration:
                audio_segment = audio_segment[:max_duration]
                warning_message = "-# You are limited to 30-second transcriptions per VM, in order to raise this limit check out **Premium**. </premium buy:1278389799857946700>" if not is_donor else "-# You are limited to 150-second transcriptions per VM."
            else:
                warning_message = ""

            async def export_audio(segment):
                audio_wav = io.BytesIO()
                def _export():
                    segment.export(audio_wav, format='wav', parameters=["-ac", "1", "-ar", "16000"])
                    audio_wav.seek(0)
                    return audio_wav
                return await asyncio.to_thread(_export)

            audio_wav = await export_audio(audio_segment)

            data = aiohttp.FormData()
            data.add_field('file', audio_wav, filename='audio.wav', content_type='audio/wav')
            headers = {'X-API-Key': API_KEY}

            async with self.session.post("http://localhost:5094/transcribe", data=data, headers=headers) as response:
                if response.status != 200:
                    await interaction.followup.send("Failed to transcribe audio.", ephemeral=True)
                    return
                data = await response.json()

            transcript = data.get('text', 'No transcription result available.')
            if len(transcript) > 2000:
                transcript = transcript[:1856] + "..." if warning_message else transcript[:1997] + "..."

            await interaction.followup.send(f"{transcript}\n{warning_message}", ephemeral=True)

        except Exception as e:
            await error_handler(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def toimage(self, interaction: Interaction, message: discord.Message) -> None:
        class EmojiView(View):
            def __init__(self, emojis: list, interaction: Interaction):
                super().__init__(timeout=120)
                self.emojis = emojis
                self.current_page = 0
                self.interaction = interaction
                self.message = None
                self.update_button_states()

            def update_button_states(self):
                self.previous_button.disabled = (self.current_page == 0)
                self.next_button.disabled = (self.current_page == len(self.emojis) - 1)

            async def update_content(self):
                if self.message is None:
                    return
                emoji_url = self.emojis[self.current_page]
                content = f"Emoji {self.current_page + 1}/{len(self.emojis)}\n{emoji_url}"
                await self.message.edit(content=content, view=self)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary, custom_id="imageleft")
            async def previous_button(self, interaction: Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return

                if self.current_page > 0:
                    self.current_page -= 1
                    await interaction.response.defer()
                    self.update_button_states()
                    await self.update_content()

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary, custom_id="imageright")
            async def next_button(self, interaction: Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return

                if self.current_page < len(self.emojis) - 1:
                    self.current_page += 1
                    await interaction.response.defer()
                    self.update_button_states()
                    await self.update_content()

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary, custom_id="imageskip")
            async def skip_button(self, interaction: Interaction, button: Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return

                class GoToPageModal(discord.ui.Modal, title="Go to Page"):
                    def __init__(self, view: EmojiView):
                        super().__init__()
                        self.view = view
                        self.page_number = discord.ui.TextInput(
                            label="Navigate to page",
                            placeholder=f"Enter a page number (1-{len(self.view.emojis)})",
                            min_length=1,
                            max_length=len(str(len(self.view.emojis)))
                        )
                        self.add_item(self.page_number)

                    async def on_submit(self, interaction: Interaction):
                        try:
                            page = int(self.page_number.value) - 1
                            if page < 0 or page >= len(self.view.emojis):
                                raise ValueError
                            self.view.current_page = page
                            self.view.update_button_states()
                            await self.view.update_content()
                            await interaction.response.defer()
                        except ValueError:
                            await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

                modal = GoToPageModal(self)
                await interaction.response.send_modal(modal)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger, custom_id="imagedelete")
            async def delete_button(self, interaction: Interaction, button: Button):
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
                    if self.message:
                        await self.message.edit(view=self)
                except discord.NotFound:
                    pass

        async def fetch_image(url: str, session: aiohttp.ClientSession, retries: int = 3) -> bytes:
            for attempt in range(retries):
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.read()
                        elif response.status == 404 and 'cdn.discordapp.com' in url:
                            alt_url = url.replace("cdn.discordapp.com", "media.discordapp.net")
                            return await fetch_image(alt_url, session, retries - 1)
                        response.raise_for_status()
                except (aiohttp.ClientError, aiohttp.ClientResponseError) as e:
                    if attempt == retries - 1:
                        raise
                    await asyncio.sleep(1 + attempt)
            raise Exception(f"Failed to fetch image after {retries} attempts")

        async def process_sticker(sticker: discord.Sticker) -> tuple[BytesIO, str]:
            is_animated = sticker.format in [discord.StickerFormatType.apng, discord.StickerFormatType.gif]
            filename = "sticker.gif" if is_animated else "sticker.png"
            
            async with aiohttp.ClientSession() as session:
                image_data = await fetch_image(sticker.url, session)
                image_io = BytesIO(image_data)
                
                if is_animated:
                    try:
                        with Image.open(image_io) as apng:
                            frames = []
                            durations = []
                            
                            for frame in ImageSequence.Iterator(apng):
                                frames.append(frame.convert("RGBA"))
                                durations.append(frame.info.get('duration', 100))
                            
                            output = BytesIO()
                            frames[0].save(
                                output,
                                format='GIF',
                                save_all=True,
                                append_images=frames[1:],
                                duration=durations,
                                loop=0,
                                disposal=1
                            )
                            output.seek(0)
                            return output, filename
                    except Exception:
                        image_io.seek(0)
                        return image_io, filename
                return image_io, filename

        async def process_emojis(custom_emojis: list[tuple[str, str, str]]) -> None:
            emoji_urls = []
            for animated_flag, emoji_name, emoji_id in custom_emojis:
                is_animated = animated_flag == 'a'
                emoji_url = f'https://cdn.discordapp.com/emojis/{emoji_id}.{"gif" if is_animated else "png"}'
                if not is_animated:
                    emoji_url += "?size=600&quality=lossless"
                if emoji_url not in emoji_urls:
                    emoji_urls.append(emoji_url)

            if not emoji_urls:
                await interaction.followup.send("No valid custom emoji found in the message.", ephemeral=True)
                return

            if len(emoji_urls) > 1:
                view = EmojiView(emoji_urls, interaction)
                view.message = await interaction.followup.send(
                    content=f"Emoji 1/{len(emoji_urls)}\n{emoji_urls[0]}",
                    view=view
                )
            else:
                await interaction.followup.send(content=emoji_urls[0])

        try:
            await interaction.response.defer()

            if message.stickers:
                sticker = message.stickers[0]
                if sticker.format == discord.StickerFormatType.lottie:
                    await interaction.followup.send("Lottie format is not supported.", ephemeral=True)
                    return
                
                image_io, filename = await process_sticker(sticker)
                await interaction.followup.send(file=File(image_io, filename=filename))
                return

            custom_emojis = []
            if message.content:
                custom_emojis.extend(re.findall(r'<(a?):(\w+):(\d+)>', message.content))
            
            if message.embeds:
                for embed in message.embeds:
                    for field in [embed.description, embed.title, 
                                embed.footer.text if embed.footer else None, 
                                embed.author.name if embed.author else None]:
                        if field:
                            custom_emojis.extend(re.findall(r'<(a?):(\w+):(\d+)>', field))
                    
                    if embed.fields:
                        for field in embed.fields:
                            custom_emojis.extend(re.findall(r'<(a?):(\w+):(\d+)>', field.value))

            if custom_emojis:
                await process_emojis(custom_emojis)
                return

            await interaction.followup.send("No sticker or emoji to convert.", ephemeral=True)

        except Exception as e:
            await error_handler(interaction, e)

    class ScreenshotException(Exception):
        pass

    media = app_commands.Group(
        name="media", 
        description="Media-editing related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    selfembed = app_commands.Group(
        name="selfembed", 
        description="Self-Embed related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
   )

    tags = app_commands.Group(
        name="tags", 
        description="Tags related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    website = app_commands.Group(
        name="website", 
        description="Website related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(message="Message to say.", freaky="Make it 𝓯𝓻𝓮𝓪𝓴𝔂?", uwu="Make it UwU?", reverse="Reverse the message?")
    @app_commands.check(permissions.is_blacklisted)
    async def say(self, interaction: Interaction, message: str, freaky: bool = False, uwu: bool = False, reverse: bool = False):
        """Make the bot say something."""
        await interaction.response.defer(thinking=True)

        try:
            if reverse:
                message = message[::-1].replace("@", "@\u200B").replace("&", "&\u200B")

            if uwu:
                flags = uwuify.STUTTER
                message = uwuify.uwu(message, flags=flags)

            if freaky:
                def to_freaky(text):
                    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                    freaky = "𝓐𝓑𝓒𝓓𝓔𝓕𝓖𝓗𝓘𝓙𝓚𝓛𝓜𝓝𝓞𝓟𝓠𝓡𝓢𝓣𝓤𝓿𝓦𝓧𝓨𝓩𝓪𝓫𝓬𝓭𝓮𝓯𝓰𝓱𝓲𝓳𝓴𝓵𝓶𝓷𝓸𝓹𝓺𝓻𝓼𝓽𝓾𝓿𝔀𝔁𝔂𝔃"
                    translation_table = str.maketrans(normal, freaky)

                    translated_text = text.translate(translation_table)

                    wrapped_text = re.sub(r'[^𝓐-𝔃 *]+', lambda match: f"*{match.group(0)}*", translated_text)

                    return wrapped_text

                message = to_freaky(message)

            await interaction.followup.send(message, allowed_mentions=discord.AllowedMentions.none())

        except discord.HTTPException as e:
            await interaction.followup.send("`Command 'say' was blocked by AutoMod.`")

        except Exception as e:
            print(e)
            await interaction.followup.send("An extra 𝓯𝓻𝓮𝓪𝓴𝔂 error occurred..")

    @convert.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(audio="The audio file to send as a VM.")
    @app_commands.check(permissions.is_blacklisted)
    async def audio2voicemessage(self, interaction: Interaction, audio: Attachment):
        "Convert an audio file to a voice message."
        await interaction.response.defer(thinking=True)

        try:
            if not audio.content_type.startswith("audio/"):
                await interaction.followup.send("Please provide a valid audio file.", ephemeral=True)
                return

            async with self.session.get(audio.url) as response:
                if response.status != 200:
                    await interaction.followup.send("Failed to download the audio file.", ephemeral=True)
                    return

                audio_data = await response.read()

            if not audio.filename.endswith(".opus"):
                input_stream = io.BytesIO(audio_data)
                output_stream = io.BytesIO()

                process = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-i", "pipe:0", "-c:a", "libopus", "-b:a", "192k", "-f", "opus", "pipe:1",
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await process.communicate(input=input_stream.read())
                if process.returncode != 0:
                    await interaction.followup.send("❌ Failed to convert audio to Opus format.", ephemeral=True)
                    return

                output_stream.write(stdout)
                output_stream.seek(0)
            else:
                output_stream = io.BytesIO(audio_data)
                output_stream.seek(0)

            try:
                await interaction.followup.send(
                    file=File(output_stream, filename="voice_message.opus"),
                    voice_message=True
                )
            except Forbidden:
                await interaction.followup.send(
                    file=File(output_stream, filename="voice_message.opus"),
                    voice_message=True,
                    ephemeral=True
                )

        except Exception as e:
            await error_handler(interaction, e)
        finally:
            if 'output_stream' in locals():
                output_stream.close()

    @app_commands.command(name="tts", description="Convert your message into audio.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(text="Text to be spoken.", voice="Select a voice.")
    @app_commands.choices(voice=[
        app_commands.Choice(name="Female", value="en_us_001"),
        app_commands.Choice(name="Male", value="en_us_006"),
        app_commands.Choice(name="Male 2", value="en_us_007"),
        app_commands.Choice(name="Ghostface (Char)", value="en_us_ghostface"),
        app_commands.Choice(name="Stormtrooper (Char)", value="en_us_stormtrooper"),
        app_commands.Choice(name="Rocket (Char)", value="en_us_rocket"),
        app_commands.Choice(name="Alto (Singing)", value="en_female_f08_salut_damou"),
        app_commands.Choice(name="Tenor (Singing)", value="en_male_m03_lobby"),
        app_commands.Choice(name="Sunshine Soon (Singing)", value="en_male_m03_sunshine_soon"),
        app_commands.Choice(name="Warmy Breeze (Singing)", value="en_female_f08_warmy_breeze"),
        app_commands.Choice(name="Glorious (Singing)", value="en_female_ht_f08_glorious"),
        app_commands.Choice(name="It Goes Up (Singing)", value="en_male_sing_funny_it_goes_up"),
        app_commands.Choice(name="Chipmunk (Singing)", value="en_male_m2_xhxs_m03_silly"),
        app_commands.Choice(name="Dramatic (Singing)", value="en_female_ht_f08_wonderful_world")
    ])
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def tts(self, interaction: Interaction, text: str, voice: str = None):
        """Convert your message into audio."""

        invalid_chars = {'.', ',', '/', '\\'}
        if set(text) <= invalid_chars:
            await interaction.followup.send("No audio could be generated. Invalid character.", ephemeral=True)
            return
        if len(text) > 300:
            await interaction.followup.send("Text too long. Maximum 300 characters allowed.", ephemeral=True)
            return

        try:
            start_time = time.time()

            headers = {'Content-Type': 'application/json'}
            selected_voice = voice if voice else 'en_us_001'
            json_data = {'text': text, 'voice': selected_voice}

            async with self.session.post(
                'https://tiktok-tts.weilnet.workers.dev/api/generation',
                headers=headers,
                json=json_data
            ) as response:
                data = await response.json()

                if 'data' not in data or data['data'] is None:
                    await interaction.followup.send("API did not return anything. Please try again later.")
                    return

                audio_data = base64.b64decode(data['data'])
                audio_stream = io.BytesIO(audio_data)
                audio_stream.seek(0)

                rnum = random.randint(100, 999)
                filename = f"tts_{rnum}.mp3"

                end_time = time.time()
                duration = end_time - start_time

                embed = await cembed(
                    interaction,
                    description=f"<:audio:1345517095101923439> Audio generated in `{duration:.2f}s`. ",
                )

                if interaction.app_permissions.embed_links:
                    await interaction.followup.send(file=File(audio_stream, filename=filename), embed=embed)
                else:
                    await interaction.followup.send(file=File(audio_stream, filename=filename))

        except Exception as e:
            await error_handler(interaction, e)

        finally:
            if 'audio_stream' in locals():
                audio_stream.close()

    async def get_spotify_access_token(self) -> str:
        auth_str = f"{client_id}:{client_secret}"
        b64_auth_str = base64.b64encode(auth_str.encode()).decode()

        headers = {
            "Authorization": f"Basic {b64_auth_str}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "client_credentials"
        }

        async with self.session.post("https://accounts.spotify.com/api/token", headers=headers, data=data) as response:
            response_data = await response.json()
            return response_data["access_token"]

    async def track_search_autocomplete(self, current: str):
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        params = {"query": current, "type": "track", "limit": 10}
        
        async with self.session.get("https://api.stats.fm/api/v1/search/elastic", headers=headers, params=params) as response:
            data = await response.json()
            tracks = data.get("items", {}).get("tracks", [])
            suggestions = []
            
            for track in tracks:
                name = f"{track['name']} - {track['artists'][0]['name']}"
                spotify_id = track.get("externalIds", {}).get("spotify", [None])[0]
                url = f"https://open.spotify.com/track/{spotify_id}" if spotify_id else None
                if url:
                    suggestions.append({"name": name, "url": url})
            
            return suggestions

    def format_duration(self, duration_ms: int) -> str:
        seconds = (duration_ms // 1000) % 60
        minutes = (duration_ms // 60000) % 60
        return f"{minutes}:{seconds:02}"

    @spotify.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(query="Search query or Spotify track url.")
    @permissions.requires_perms(embed_links=True, attach_files=True)
    @app_commands.check(permissions.is_blacklisted)
    async def track(self, interaction: Interaction, *, query: str):
        """Get information about a song on Spotify."""
        spotify_url_pattern = re.compile(r'https?://(?:open\.)?spotify\.com/track/([a-zA-Z0-9]+)')
        
        match = spotify_url_pattern.match(query)
        if match:
            track_id = match.group(1)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            
            try:
                async with self.session.get(
                    f"https://api.stats.fm/api/v1/search/elastic?query={track_id}&type=track&limit=1",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        await self.search_and_respond(interaction, query, headers)
                        return
                    
                    data = await response.json()
                    tracks = data.get("items", {}).get("tracks", [])
                    
                    if not tracks:
                        await self.search_and_respond(interaction, query, headers)
                        return
                    
                    track_data = tracks[0]
                    await self.send_track_info(interaction, track_data, headers)
                    
            except Exception as e:
                await error_handler(interaction, e)
        else:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            await self.search_and_respond(interaction, query, headers)

    async def search_and_respond(self, interaction: Interaction, query: str, headers: dict):
        async with self.session.get(
            f"https://api.stats.fm/api/v1/search/elastic?query={query}&type=track&limit=1",
            headers=headers
        ) as response:
            if response.status != 200:
                await interaction.followup.send("Could not find any results for that song on Spotify.", ephemeral=True)
                return
            
            data = await response.json()
            tracks = data.get("items", {}).get("tracks", [])
            
            if not tracks:
                await interaction.followup.send("Could not find any results for that song on Spotify.", ephemeral=True)
                return
            
            track_data = tracks[0]
            await self.send_track_info(interaction, track_data, headers)

    async def send_track_info(self, interaction: Interaction, track_data: dict, headers: dict):
        song_name = track_data['name']
        artist_name = track_data['artists'][0]['name']
        album_name = track_data['albums'][0]['name']
        duration_ms = track_data['durationMs']
        cover_url = track_data['albums'][0].get('image')
        
        fduration = self.format_duration(duration_ms)
        spotify_id = track_data.get("externalIds", {}).get("spotify", [None])[0]
        spotify_url = f"https://open.spotify.com/track/{spotify_id}" if spotify_id else None
        artist_id = track_data['artists'][0]['id']
        album_id = track_data['albums'][0]['id']
        artist_url = f"https://stats.fm/artist/{artist_id}"
        album_url = f"https://stats.fm/album/{album_id}"
        preview_url = track_data.get('spotifyPreview') or track_data.get('appleMusicPreview')
        has_audio = preview_url is not None
        
        embed = await cembed(
            interaction,
            title=f"**{song_name}**",
            description=f"-# [{artist_name}]({artist_url}) • [*{album_name}*]({album_url})\n-# `{fduration}`")
        
        if cover_url:
            embed.set_thumbnail(url=cover_url)
        
        embed.set_author(
            name=interaction.user.name,
            icon_url=interaction.user.display_avatar.url)
        
        if spotify_url:
            embed.url = spotify_url
        
        embed.set_footer(text="spotify.com", icon_url="https://git.cursi.ng/spotify_logo.png")
        
        class TrackView(discord.ui.View):
            def __init__(self, interaction: discord.Interaction, session: aiohttp.ClientSession, has_audio: bool, preview_url: str, spotify_url: str):
                super().__init__(timeout=240)
                self.interaction = interaction
                self.message = None
                self.session = session
                self.has_audio = has_audio
                self.preview_url = preview_url
                self.spotify_url = spotify_url
                
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
                    custom_id="trackaudio",
                    disabled=not self.has_audio,
                    row=0
                ))
            
            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.data["custom_id"] == "trackaudio":
                    await self.audio_button(interaction)
                return True
            
            async def audio_button(self, interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)
                
                if self.preview_url:
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
            
            async def on_timeout(self):
                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                        item.disabled = True
                
                try:
                    await self.message.edit(view=self)
                except discord.NotFound:
                    pass
        
        view = TrackView(interaction, self.session, has_audio, preview_url, spotify_url)
        message = await interaction.followup.send(embed=embed, view=view)
        view.message = message

    @spotify.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @permissions.requires_perms(embed_links=True)
    @app_commands.check(permissions.is_blacklisted)
    async def player(self, interaction: Interaction):
        "Used for Spotify API review — not for public use yet."
        user_id = str(interaction.user.id)
        
        async with get_db_connection() as conn:
            spotify_data = await conn.fetchrow(
                "SELECT access_token, refresh_token, expires_at FROM spotify_auth WHERE user_id = $1", 
                user_id
            )
            
            if not spotify_data:
                await interaction.followup.send(
                    f"<:warning:1350239604925530192> {interaction.user.mention}: You need to login to Spotify first. Use </spotify login:1348042860188139665> to authorize.",
                    ephemeral=True
                )
                return
        
        headers = {
            "Authorization": f"Bearer {spotify_data['access_token']}",
            "Content-Type": "application/json"
        }
        
        async def get_current_track():
            async with self.session.get(
                "https://api.spotify.com/v1/me/player/currently-playing",
                headers=headers
            ) as response:
                if response.status == 200:
                    return await response.json()
            return None
        
        current_track = await get_current_track()
        track_info = "Nothing is currently playing."
        album_cover_url = None
        if current_track and current_track.get('item'):
            track_name = current_track['item']['name']
            artist_name = current_track['item']['artists'][0]['name']
            track_info = f"{track_name} - {artist_name}"
            if current_track['item'].get('album') and current_track['item']['album'].get('images'):
                album_cover_url = current_track['item']['album']['images'][0]['url']
        
        embed = await cembed(interaction,
            description="### <:spotify:1274904265114124308> Spotify Control Panel <:spotify:1274904265114124308>\n\n-# **Use the buttons below to control the playback:**\n"
                    "<:rright:1282516005385404466> **Back**: Go to the previous track.\n"
                    "<:rright:1282516005385404466> **Pause**: Pause or resume the track.\n"
                    "<:rright:1282516005385404466> **Skip**: Skip to the next track.\n"
                    "<:rright:1282516005385404466> **Search**: Add a new song to the queue.\n"
                    "<:rright:1282516005385404466> **Lyrics**: Get the lyrics of the current track.")
        embed.set_author(name=f"Controlled by {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
        embed.set_thumbnail(url="https://git.cursi.ng/spotify_logo_green.png?e")
        if album_cover_url:
            embed.set_footer(text=f"Currently playing: {track_info}", icon_url=album_cover_url)
        else:
            embed.set_footer(text=f"Currently playing: {track_info}")
        
        class GoToPageModal(discord.ui.Modal):
            def __init__(self, max_pages: int, view) -> None:
                super().__init__(title="Go to Page")
                self.view = view
                self.page_number = discord.ui.TextInput(
                    label="Navigate to page",
                    placeholder=f"Enter a page number (1-{max_pages})",
                    min_length=1,
                    max_length=len(str(max_pages)))
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
                embed = await cembed(
                    self.interaction,
                    title=f"{self.title} - {self.artist}",
                    description=f"```yaml\n{content}```",
                    url=self.genius_url
                )
                embed.set_author(name=f"{self.interaction.user.name}", icon_url=self.interaction.user.avatar.url if self.interaction.user.avatar else self.interaction.user.default_avatar.url)
                embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)} • {footer}", icon_url="https://git.cursi.ng/genius_logo.png")
                embed.set_thumbnail(url=self.cover_image)
                await self.message.edit(embed=embed, view=self)

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
                query = f"{self.title} {self.artist}"
                async with self.session.get(f"https://api.stats.fm/api/v1/search/elastic?query={query}%20{self.artist}&type=track&limit=5", headers=headers) as response:
                    if response.status != 200:
                        await interaction.followup.send("Failed to fetch track data.", ephemeral=True)
                        return
                    
                    data = await response.json()
                    tracks = data.get("items", {}).get("tracks", [])

                    if not tracks:
                        await interaction.followup.send("No tracks found.", ephemeral=True)
                        return

                    genius_title = self.title.lower().strip()
                    genius_artist = self.artist.lower().strip()

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

        class SearchModal(discord.ui.Modal):
            def __init__(self, session: aiohttp.ClientSession, user_id: str, player_view):
                super().__init__(title="Spotify Search")
                self.session = session
                self.user_id = user_id
                self.player_view = player_view
                self.query = discord.ui.TextInput(
                    label="Song name or URL",
                    placeholder="Enter song name or Spotify URL...",
                    max_length=100
                )
                self.add_item(self.query)
            
            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)
                query = self.query.value
                
                headers = await self.player_view.get_headers()
                if not headers:
                    await interaction.followup.send("Your Spotify session has expired. Please login again.", ephemeral=True)
                    return
                
                if "open.spotify.com/track/" in query:
                    track_id = query.split("track/")[1].split("?")[0]
                    async with self.session.get(
                        f"https://api.spotify.com/v1/tracks/{track_id}",
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            track_data = await response.json()
                            tracks = [track_data]
                        else:
                            await interaction.followup.send("Couldn't find that track.", ephemeral=True)
                            return
                else:
                    params = {"q": query, "type": "track", "limit": 10}
                    async with self.session.get(
                        "https://api.spotify.com/v1/search",
                        headers=headers,
                        params=params
                    ) as response:
                        if response.status != 200:
                            await interaction.followup.send("Search failed.", ephemeral=True)
                            return
                        data = await response.json()
                        tracks = data.get('tracks', {}).get('items', [])
                
                if not tracks:
                    await interaction.followup.send("No results found.", ephemeral=True)
                    return
                
                options = []
                track_info = {}
                for track in tracks[:10]:
                    name = f"{track['name']} - {track['artists'][0]['name']}"
                    if len(name) > 100:
                        name = name[:97] + "..."
                    options.append(discord.SelectOption(label=name, value=track['uri']))
                    track_info[track['uri']] = {
                        'name': track['name'],
                        'artist': track['artists'][0]['name']
                    }
                
                class TrackSelect(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=120)
                        self.selected = None
                    
                    @discord.ui.select(placeholder="Select a track to play", options=options)
                    async def select_callback(self, select_interaction: discord.Interaction, select: discord.ui.Select):
                        if select_interaction.user.id != interaction.user.id:
                            await select_interaction.response.send_message("This isn't your search!", ephemeral=True)
                            return
                        self.selected = select.values[0]
                        self.stop()
                    
                    async def on_timeout(self):
                        try:
                            await interaction.delete_original_response()
                        except:
                            pass
                
                view = TrackSelect()
                await interaction.followup.send("Results from Spotify:", view=view, ephemeral=True)
                await view.wait()
                
                if view.selected:
                    track_name = track_info[view.selected]['name']
                    artist_name = track_info[view.selected]['artist']
                    async with self.session.put(
                        "https://api.spotify.com/v1/me/player/play",
                        headers=headers,
                        json={"uris": [view.selected]}
                    ) as response:
                        if response.status == 204:
                            await interaction.followup.send(f"Now playing: **{track_name}** by **{artist_name}**", ephemeral=True)
                            await asyncio.sleep(1)
                            await self.player_view.update_player()
                        else:
                            await interaction.followup.send("Failed to play track.", ephemeral=True)
        
        class PlayerView(discord.ui.View):
            def __init__(self, interaction: discord.Interaction, session: aiohttp.ClientSession, user_id: str):
                super().__init__(timeout=300)
                self.interaction = interaction
                self.session = session
                self.user_id = user_id
                self.message = None
            
            async def get_headers(self):
                async with get_db_connection() as conn:
                    spotify_data = await conn.fetchrow(
                        "SELECT access_token, refresh_token, expires_at FROM spotify_auth WHERE user_id = $1", 
                        self.user_id
                    )
                    if not spotify_data:
                        return None
                    
                    if spotify_data['expires_at'] < datetime.now():
                        new_token = await self.refresh_token(spotify_data['refresh_token'])
                        if not new_token:
                            return None
                        return {
                            "Authorization": f"Bearer {new_token}",
                            "Content-Type": "application/json"
                        }
                    
                    return {
                        "Authorization": f"Bearer {spotify_data['access_token']}",
                        "Content-Type": "application/json"
                    }
            
            async def refresh_token(self, refresh_token: str):
                async with self.session.post(
                    "https://accounts.spotify.com/api/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": client_id,
                        "client_secret": client_secret
                    }
                ) as response:
                    data = await response.json()
                    if response.status != 200:
                        return None
                    async with get_db_connection() as conn:
                        await conn.execute(
                            "UPDATE spotify_auth SET access_token = $1, expires_at = $2 WHERE user_id = $3",
                            data['access_token'],
                            datetime.now() + timedelta(seconds=data['expires_in']),
                            self.user_id
                        )
                    return data['access_token']
            
            async def get_current_track(self):
                headers = await self.get_headers()
                if not headers:
                    return None
                
                async with self.session.get(
                    "https://api.spotify.com/v1/me/player/currently-playing",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                return None
            
            async def update_player(self):
                current_track = await self.get_current_track()
                track_info = "Nothing is currently playing."
                album_cover_url = None
                if current_track and current_track.get('item'):
                    track_name = current_track['item']['name']
                    artist_name = current_track['item']['artists'][0]['name']
                    track_info = f"{track_name} - {artist_name}"
                    if current_track['item'].get('album') and current_track['item']['album'].get('images'):
                        album_cover_url = current_track['item']['album']['images'][0]['url']
                
                embed = await cembed(self.interaction,
                    description="### <:spotify:1274904265114124308> Spotify Control Panel <:spotify:1274904265114124308>\n\n-# **Use the buttons below to control the playback:**\n"
                            "<:rright:1282516005385404466> **Back**: Go to the previous track.\n"
                            "<:rright:1282516005385404466> **Pause**: Pause or resume the track.\n"
                            "<:rright:1282516005385404466> **Skip**: Skip to the next track.\n"
                            "<:rright:1282516005385404466> **Search**: Add a new song to the queue.\n"
                            "<:rright:1282516005385404466> **Lyrics**: Get the lyrics of the current track.")
                embed.set_author(name=f"Controlled by {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
                embed.set_thumbnail(url="https://git.cursi.ng/spotify_logo_green.png?e")
                if album_cover_url:
                    embed.set_footer(text=f"Currently playing: {track_info}", icon_url=album_cover_url)
                else:
                    embed.set_footer(text=f"Currently playing: {track_info}")
                await self.message.edit(embed=embed)
            
            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:playbackrewind:1361765413972742236>"), style=discord.ButtonStyle.red)
            async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return
                
                headers = await self.get_headers()
                if not headers:
                    await interaction.response.send_message("Your Spotify session has expired. Please login again.", ephemeral=True)
                    return
                
                async with self.session.post(
                    "https://api.spotify.com/v1/me/player/previous",
                    headers=headers
                ) as response:
                    if response.status == 401:
                        new_token = await self.refresh_token()
                        if new_token:
                            headers["Authorization"] = f"Bearer {new_token}"
                            await self.session.post(
                                "https://api.spotify.com/v1/me/player/previous",
                                headers=headers
                            )
                    await interaction.response.defer()
                    await asyncio.sleep(1)
                    await self.update_player()
            
            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:playbackresume:1361765446973390888>"), style=discord.ButtonStyle.blurple)
            async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return
                
                headers = await self.get_headers()
                if not headers:
                    await interaction.response.send_message("Your Spotify session has expired. Please login again.", ephemeral=True)
                    return
                
                async with self.session.get(
                    "https://api.spotify.com/v1/me/player",
                    headers=headers
                ) as response:
                    if response.status == 401:
                        new_token = await self.refresh_token()
                        if new_token:
                            headers["Authorization"] = f"Bearer {new_token}"
                            await self.session.get(
                                "https://api.spotify.com/v1/me/player",
                                headers=headers
                            )
                    
                    if response.status == 200:
                        player_data = await response.json()
                        is_playing = player_data.get('is_playing', False)
                        
                        endpoint = "pause" if is_playing else "play"
                        async with self.session.put(
                            f"https://api.spotify.com/v1/me/player/{endpoint}",
                            headers=headers
                        ) as put_response:
                            if put_response.status == 401:
                                new_token = await self.refresh_token()
                                if new_token:
                                    headers["Authorization"] = f"Bearer {new_token}"
                                    await self.session.put(
                                        f"https://api.spotify.com/v1/me/player/{endpoint}",
                                        headers=headers
                                    )
                    await interaction.response.defer()
                    await asyncio.sleep(1)
                    await self.update_player()
            
            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:playbacknext:1361765424534130748>"), style=discord.ButtonStyle.green)
            async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return
                
                headers = await self.get_headers()
                if not headers:
                    await interaction.response.send_message("Your Spotify session has expired. Please login again.", ephemeral=True)
                    return
                
                async with self.session.post(
                    "https://api.spotify.com/v1/me/player/next",
                    headers=headers
                ) as response:
                    if response.status == 401:
                        new_token = await self.refresh_token()
                        if new_token:
                            headers["Authorization"] = f"Bearer {new_token}"
                            await self.session.post(
                                "https://api.spotify.com/v1/me/player/next",
                                headers=headers
                            )
                    await interaction.response.defer()
                    await asyncio.sleep(1)
                    await self.update_player()
            
            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:playbacksearch:1361765434424033290>"), style=discord.ButtonStyle.gray)
            async def search(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return
                
                modal = SearchModal(self.session, self.user_id, self)
                await interaction.response.send_modal(modal)
            
            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:playbacklyrics:1361765438119215434>"), style=discord.ButtonStyle.gray)
            async def lyrics(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return
                
                await interaction.response.defer(ephemeral=True)
                
                current_track = await self.get_current_track()
                if not current_track or not current_track.get('item'):
                    await interaction.followup.send("Nothing is currently playing.", ephemeral=True)
                    return
                
                track_name = current_track['item']['name']
                artist_name = current_track['item']['artists'][0]['name']
                song_query = f"{track_name} {artist_name}"
                
                async def fetch_lyrics(song: str):
                    try:
                        loop = asyncio.get_running_loop()
                        genius = Genius(GENIUS_KEY)
                        genius.remove_section_headers = True
                        genius.skip_non_songs = True
                        genius.excluded_terms = ["(Remix)", "(Live)"]
                        song_obj = await loop.run_in_executor(None, genius.search_song, song)
                        if song_obj and song_obj.lyrics:
                            lyrics = song_obj.lyrics
                            if "Lyrics" in lyrics:
                                lyrics = lyrics[lyrics.index("Lyrics") + len("Lyrics"):].strip()
                            return lyrics, song_obj.title, song_obj.artist, song_obj.url, song_obj.song_art_image_url
                        return None, None, None, None, None
                    except Exception:
                        return None, None, None, None, None
                
                def split_lyrics(lyrics: str):
                    if not lyrics:
                        return []
                    paragraphs = lyrics.split("\n\n")
                    paragraphs = [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]
                    return paragraphs
                
                lyrics, title, artist, genius_url, cover_image = await fetch_lyrics(song_query)
                if not lyrics:
                    await interaction.followup.send("Couldn't find lyrics for this song.", ephemeral=True)
                    return
                
                pages = split_lyrics(lyrics)
                if not pages:
                    await interaction.followup.send("Lyrics not found.", ephemeral=True)
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
                view = LyricsView(pages, interaction, session=self.session, use_embeds=True, has_audio=has_audio)
                view.title = title
                view.artist = artist
                view.genius_url = genius_url
                view.cover_image = cover_image
                
                embed = await cembed(
                    interaction,
                    title=f"{title} - {artist}",
                    description=f"```yaml\n{pages[0]}```",
                    url=genius_url
                )
                embed.set_author(name=f"{interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
                embed.set_footer(text=f"Page 1/{len(pages)} • {footer}", icon_url="https://git.cursi.ng/genius_logo.png")
                embed.set_thumbnail(url=cover_image)
                message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)

                view.message = message
            
            async def on_timeout(self):
                for item in self.children:
                    item.disabled = True
                try:
                    await self.message.edit(view=self)
                except discord.NotFound:
                    pass
        
        view = PlayerView(interaction, self.session, user_id)
        await interaction.followup.send(embed=embed, view=view)
        view.message = await interaction.original_response()

    @spotify.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def link(self, interaction: Interaction):
        "Used for Spotify API review — not for public use yet."
        state = str(uuid.uuid4())
        auth_url = f"https://accounts.spotify.com/authorize?response_type=code&client_id={client_id}&scope=user-read-private%20user-read-email%20user-read-playback-state%20user-modify-playback-state&redirect_uri={redirect_uri}&state={state}"
        
        async with get_db_connection() as conn:
            await conn.execute(
                "INSERT INTO spotify_auth_states (user_id, state) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET state = $2",
                str(interaction.user.id), state
            )
        
        await interaction.response.send_message(
            f"**You will NOT be able to authorize right now, this command is only public so Spotify staff can review and allow us to use their API.**\nThank you for your understanding.\n\nClick [here]({auth_url}) to authorize Spotify access. This link will expire in 5 minutes.",
            ephemeral=True
        )

    @track.autocomplete("query")
    async def track_autocomplete(self, interaction: Interaction, current: str):
        suggestions = await self.track_search_autocomplete(current)
        filtered_suggestions = []
        
        for suggestion in suggestions:
            name = suggestion['name']
            if len(name) > 100:
                name = name[:100 - 3] + '...'
            
            filtered_suggestions.append(app_commands.Choice(name=name, value=suggestion['url']))
        
        await interaction.response.autocomplete(filtered_suggestions)

    @soundcloud.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(query="Search query or track url.", stats="Show track statistics?")
    @app_commands.choices(stats=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")])
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def track(self, interaction: Interaction, *, query: str, stats: str = "yes"):
        """Get information about a SoundCloud track."""
        soundcloud_url_pattern = re.compile(r'^https?://(?:www\.|on\.|m\.)?soundcloud\.com/[\w-]+/[\w-]+(?:\?.*si=[\w-]+.*)?$|^https?://(?:www\.|on\.|m\.)?soundcloud\.com/.+$')
        
        if not soundcloud_url_pattern.match(query) and not query.startswith('https://'):
            try:
                search_opts = {'extractor_args': {'soundcloud': {'client_id': 'f1TFyuaI8LX1Ybd1zvQRX8GpsNYcQ3Y5'}}, 'quiet': True, 'no_warnings': True, 'simulate': True, 'skip_download': True}
                loop = asyncio.get_event_loop()
                search_info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(search_opts).extract_info(f"scsearch1:{query}", download=False))
                if not search_info or not search_info.get('entries'):
                    await interaction.followup.send("No results found.", ephemeral=True)
                    return
                first_track = None
                for entry in search_info['entries']:
                    url = entry.get('webpage_url')
                    if not ('/sets/' in url or '?set=' in url):
                        first_track = entry
                        break
                if not first_track:
                    await interaction.followup.send("No valid tracks found.", ephemeral=True)
                    return
                query = first_track['webpage_url']
            except Exception as e:
                await interaction.followup.send("An error occurred.", ephemeral=True)
                return

        if '/sets/' in query or '?set=' in query:
            await interaction.followup.send("Sets and playlists are not supported.", ephemeral=True)
            return

        url_match = re.search(r'(https?://(?:www\.|on\.|m\.)?soundcloud\.com/[\w-]+/[\w-]+)', query)
        if url_match:
            query = url_match.group(1)
        
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'simulate': True,
                'skip_download': True,
                'extractor_args': {'soundcloud': {'client_id': 'WllBIfHWzyw4mw9twqR3EKDn7JYmhQbX'}}}
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(query, download=False))
            title = info.get('title')
            artist = info.get('uploader')
            artist_url = info.get('uploader_url')
            track_cover = max(info['thumbnails'], key=lambda x: x.get('width', 0)).get('url')
            plays = info.get('view_count')
            likes = info.get('like_count')
            reposts = info.get('repost_count')
            upload_date = info.get('upload_date')
            duration = info.get('duration', 0)

            audio_url = None
            if info.get('formats'):
                formats = info.get('formats', [])
                for fmt in formats:
                    if fmt.get('acodec') != 'none' and fmt.get('url'):
                        audio_url = fmt.get('url')
                        break
            if not audio_url and info.get('url'):
                audio_url = info.get('url')
            if not audio_url:
                await interaction.followup.send("Failed to get audio stream URL.", ephemeral=True)
                return

            async with self.session.get(audio_url) as response:
                if response.status != 200:
                    await interaction.followup.send("Failed to fetch audio stream.", ephemeral=True)
                    return
                hls_content = await response.text()
                fragment_urls = re.findall(r'https?://[^\s]+', hls_content)
                combined_audio = io.BytesIO()
                for fragment_url in fragment_urls:
                    async with self.session.get(fragment_url) as fragment_response:
                        if fragment_response.status == 200:
                            combined_audio.write(await fragment_response.read())
                combined_audio.seek(0)

            td = timedelta(seconds=duration)
            durationf = "{:02d}:{:02d}".format(td.seconds // 60, td.seconds % 60)

            fdate = ""
            if upload_date:
                try:
                    date_obj = datetime.strptime(upload_date, '%Y%m%d')
                    fdate = date_obj.strftime("%d/%m/%Y")
                except Exception:
                    fdate = upload_date

            sanitized_title = re.sub(r'[<>:"/\\|?*]', '', title)
            file = File(fp=combined_audio, filename=f"{sanitized_title}.mp3")

            def format_number(num):
                if num >= 1_000_000:
                    return f"{num/1_000_000:.1f}M"
                elif num >= 1_000:
                    return f"{num/1_000:.1f}k"
                return str(num)

            try:
                if stats.lower() == "yes":
                    desc = ""
                    if durationf:
                        desc = f"-# By [**{artist}**]({artist_url})\n-# Duration: **`{durationf}`**"
                    embed = await cembed(interaction, title=title, description=desc, url=query)
                    embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar)
                    embed.set_footer(text=f"❤️ {format_number(likes)} • 👁️ {format_number(plays)} • 🔄 {format_number(reposts)} | {fdate}", icon_url="https://git.cursi.ng/soundcloud_logo.png?")
                    embed.set_thumbnail(url=track_cover)
                    if interaction.app_permissions.embed_links:
                        await interaction.followup.send(file=file, embed=embed)
                    else:
                        await interaction.followup.send(file=file)
                else:
                    await interaction.followup.send(file=file)
            except discord.Forbidden:
                await interaction.followup.send(file=file, ephemeral=True)
            finally:
                file.close()
        except Exception as e:
            await interaction.followup.send("An error occurred.", ephemeral=True)

    @track.autocomplete("query")
    async def track_autocomplete(self, interaction: Interaction, current: str):
        if not current:
            return []

        ydl_opts = {
            'extractor_args': {'soundcloud': {'client_id': 'f1TFyuaI8LX1Ybd1zvQRX8GpsNYcQ3Y5'}},
            'quiet': True,
            'no_warnings': True,
            'simulate': True,
            'skip_download': True,
            'extract_flat': True,
            'format': 'hls_opus/bestaudio/best',
            'match_filter': lambda x: None if '/sets/' not in x['webpage_url'] else 'Playlist detected',
            'force_generic_extractor': False
        }

        try:
            with ThreadPoolExecutor() as pool:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    loop = asyncio.get_event_loop()
                    info = await loop.run_in_executor(pool, lambda: ydl.extract_info(f"scsearch3:{current}", download=False))

            suggestions = []
            if info and 'entries' in info:
                for entry in info['entries'][:3]:
                    url = entry.get('webpage_url')
                    if '/sets/' in url or '?set=' in url:
                        continue
                    title = entry.get('title')
                    uploader = entry.get('uploader')
                    turl = url[:100]
                    namef = f"{title[:50]} - {uploader[:40]}".strip()
                    suggestions.append(app_commands.Choice(name=namef, value=turl))

            return suggestions
        except Exception as e:
            print(f"Error during autocomplete: {e}")
            return []

    # @soundcloud.command()
    # @app_commands.allowed_installs(guilds=True, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    # @app_commands.describe(query="Search query or track url.", stats="Show track statistics?")
    # @app_commands.choices(stats=[
    #     app_commands.Choice(name="Yes", value="yes"),
    #     app_commands.Choice(name="No", value="no")])
    # @app_commands.check(permissions.is_blacklisted)
    # @permissions.requires_perms(attach_files=True)
    # async def track(self, interaction: Interaction, *, query: str, stats: str = "yes"):
    #     """Get information about a SoundCloud track."""
        
    #     soundcloud_url_pattern = re.compile(
    #         r'^https?://(?:www\.|on\.|m\.)?soundcloud\.com/[\w-]+/[\w-]+(?:\?.*si=[\w-]+.*)?$|^https?://(?:www\.|on\.|m\.)?soundcloud\.com/.+$'
    #     )
        
    #     if not soundcloud_url_pattern.match(query) and not query.startswith('https://'):
    #         try:
    #             search_opts = {
    #                 'extractor_args': {
    #                     'soundcloud': {'client_id': 'WllBIfHWzyw4mw9twqR3EKDn7JYmhQbX'}
    #                 },
    #                 'quiet': True,
    #                 'no_warnings': True,
    #                 'simulate': True,
    #                 'skip_download': True,
    #             }
    #             loop = asyncio.get_event_loop()
    #             search_info = await loop.run_in_executor(
    #                 None, 
    #                 lambda: yt_dlp.YoutubeDL(search_opts).extract_info(f"scsearch1:{query}", download=False)
    #             )
                
    #             if not search_info or not search_info.get('entries'):
    #                 await interaction.followup.send("No results found.", ephemeral=True)
    #                 return
                    
    #             first_track = None
    #             for entry in search_info['entries']:
    #                 url = entry.get('webpage_url')
    #                 if not ('/sets/' in url or '?set=' in url):
    #                     first_track = entry
    #                     break
                        
    #             if not first_track:
    #                 await interaction.followup.send("No valid tracks found.", ephemeral=True)
    #                 return
                    
    #             query = first_track['webpage_url']
    #         except Exception as e:
    #             await error_handler(interaction, e)
    #             return

    #     if '/sets/' in query or '?set=' in query:
    #         await interaction.followup.send("Sets and playlists are not supported.", ephemeral=True)
    #         return

    #     url_match = re.search(r'(https?://(?:www\.|on\.|m\.)?soundcloud\.com/[\w-]+/[\w-]+)', query)
    #     if url_match:
    #         query = url_match.group(1)
        
    #     try:
    #         ydl_opts = {
    #             'format': 'bestaudio/best',
    #             'outtmpl': os.path.join(tempfile.gettempdir(), '%(id)s.%(ext)s'),
    #             'noplaylist': True,
    #             'retries': 3,
    #             'fragment_retries': 3,
    #             'skip_unavailable_fragments': True,
    #             'concurrent_fragment_downloads': 10,
    #             'postprocessors': [{
    #                 'key': 'FFmpegExtractAudio',
    #                 'preferredcodec': 'mp3',
    #                 'preferredquality': '192',
    #             }]
    #         }
            
    #         loop = asyncio.get_event_loop()
    #         info = await loop.run_in_executor(
    #             None, 
    #             lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(query, download=True))
    #         title = info.get('title')
    #         artist = info.get('uploader')
    #         artist_url = info.get('uploader_url')
    #         track_cover = max(info['thumbnails'], key=lambda x: x.get('width', 0)).get('url')
    #         plays = info.get('view_count')
    #         likes = info.get('like_count')
    #         reposts = info.get('repost_count')
    #         audio_url = info.get('url')
    #         upload_date = info.get('upload_date')
    #         duration = info.get('duration')

    #         td = timedelta(seconds=duration)
    #         durationf = "{:02d}:{:02d}".format(td.seconds // 60, td.seconds % 60)

    #         if upload_date:
    #             try:
    #                 date_obj = datetime.strptime(upload_date, '%Y%m%d')
    #                 fdate = date_obj.strftime("%d/%m/%Y")
    #             except Exception:
    #                 fdate = upload_date

    #         sanitized_title = re.sub(r'[<>:"/\\|?*]', '', title)
    #         filename = f"{info['id']}.mp3"
    #         temp = os.path.join(tempfile.gettempdir(), filename)
            
    #         def format_number(num):
    #             if num >= 1_000_000:
    #                 return f"{num/1_000_000:.1f}M"
    #             elif num >= 1_000:
    #                 return f"{num/1_000:.1f}k"
    #             return str(num)

    #         async with aiofiles.open(temp, mode='rb') as f:
    #             file_content = await f.read()
            
    #         file = File(fp=io.BytesIO(file_content), filename=f"{sanitized_title}.mp3")
            
    #         try:
    #             if stats.lower() == "yes":
    #                 desc = ""
    #                 if durationf:
    #                     desc = f"-# By [**{artist}**]({artist_url})\n-# Duration: **`{durationf}`**"
    #                 embed = await cembed(interaction, title=title, description=desc, url=query)
    #                 embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar)
                    
    #                 embed.set_footer(text=f"❤️ {format_number(likes)} • 👁️ {format_number(plays)} • 🔄 {format_number(reposts)} | {fdate}", icon_url="https://git.cursi.ng/soundcloud_logo.png?")
    #                 embed.set_thumbnail(url=track_cover)
    #                 if interaction.app_permissions.embed_links:
    #                     await interaction.followup.send(file=file, embed=embed)
    #                 else:
    #                     await interaction.followup.send(file=file)
    #             else:
    #                 await interaction.followup.send(file=file)
    #         except discord.Forbidden:
    #             await interaction.followup.send(file=file, ephemeral=True)
    #         finally:
    #             file.close()
    #             await loop.run_in_executor(None, os.remove, temp)
        
    #     except Exception as e:
    #         await error_handler(interaction, e)

    # @track.autocomplete("query")
    # async def track_autocomplete(self, interaction: Interaction, current: str):
    #     if not current:
    #         return []

    #     ydl_opts = {
    #         'extractor_args': {
    #             'soundcloud': {
    #                 'client_id': 'WllBIfHWzyw4mw9twqR3EKDn7JYmhQbX',
    #             }
    #         },
    #         'quiet': True,
    #         'no_warnings': True,
    #         'simulate': True,
    #         'skip_download': True,
    #         'extract_flat': True,
    #         'format': 'hls_opus/bestaudio/best',
    #         'match_filter': lambda x: None if '/sets/' not in x['webpage_url'] else 'Playlist detected',
    #         'force_generic_extractor': False
    #     }
        
    #     with ThreadPoolExecutor() as pool:
    #         with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    #             info = await asyncio.get_event_loop().run_in_executor(
    #                 pool,
    #                 lambda: ydl.extract_info(f"scsearch3:{current}", download=False)
    #             )
        
    #     suggestions = []
    #     if info and 'entries' in info:
    #         for entry in info['entries'][:3]:
    #             url = entry.get('webpage_url')
    #             if '/sets/' in url or '?set=' in url:
    #                 continue
    #             title = entry.get('title')
    #             uploader = entry.get('uploader')
    #             turl = url[:100]
                
    #             namef = f"{title[:50]} - {uploader[:40]}".strip()
    #             suggestions.append(app_commands.Choice(name=namef, value=turl))
        
    #     return suggestions

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(audio="Audio file to be recognized.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def shazam(self, interaction: Interaction, audio: Attachment):
        "Recognize a song using Shazam."

        async def recognize_song():
            try:
                file_extension = audio.filename.split('.')[-1].lower()
                if file_extension not in SUPPORTED_EXTENSIONS:
                    await interaction.followup.send("This file format is not supported.", ephemeral=True)
                    return

                file_path = f"temp_{audio.filename}"
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(await audio.read())

                shazam = Shazam()
                result = await shazam.recognize(file_path)

                await aiofiles.os.remove(file_path)

                if result and 'track' in result:
                    track = result['track']
                    title = track.get('title', 'Unknown Title')
                    artist = track.get('subtitle', 'Unknown Artist')

                    apple_music_url = None
                    spotify_url = None
                    apple_music_image = None
                    spotify_image = None

                    if 'hub' in track and track['hub'].get('type') == 'APPLEMUSIC':
                        for action in track['hub'].get('actions', []):
                            if action.get('type') == 'applemusicplay':
                                apple_music_url = action.get('uri')
                            if action.get('type') == 'uri' and 'image' in action:
                                apple_music_image = action.get('image')

                    if 'providers' in track:
                        for provider in track['providers']:
                            if provider.get('type') == 'SPOTIFY':
                                for action in provider.get('actions', []):
                                    if action.get('type') == 'uri':
                                        spotify_url = action.get('uri')
                                if 'images' in provider:
                                    spotify_image = provider['images'].get('default')

                    shazam_image = track.get('images', {}).get('coverart', 'https://i.imgur.com/3sgezz7.png')

                    thumbnail_url = apple_music_image or spotify_image or shazam_image

                    description_parts = [f"Song: **{title}**\nArtist(s): **{artist}**"]
                    if apple_music_url:
                        description_parts.append(f"[Listen on Apple Music]({apple_music_url})")
                    if spotify_url:
                        description_parts.append(f"[Listen on Spotify]({spotify_url})")

                    description = '\n'.join(description_parts)
                    embed = await cembed(
                        interaction,
                        title="✅ Song has been found!",
                        description=description or "No additional links available.",
                    )
                    if thumbnail_url:
                        embed.set_thumbnail(url=thumbnail_url)
                    embed.set_footer(text=f"{footer}", icon_url="https://git.cursi.ng/shazam_logo.png")
                    if interaction.app_permissions.embed_links:
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send(f"Song: **{title}**\nArtist(s): **{artist}**\n-# Missing the `Embed Links` permission in this server, so no embed for you.")
                else:
                    await interaction.followup.send("Could not recognize this song.", ephemeral=True)

            except Exception as e:
                await error_handler(interaction, e)

        await recognize_song()

    @aitools.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(image="The image to locate.")
    @app_commands.check(permissions.is_donor)
    @app_commands.check(permissions.is_blacklisted)
    async def locate(self, interaction: Interaction, image: Attachment):
        """✨ Use AI to locate an image."""
        if not image.content_type.startswith('image/'):
            await interaction.response.send_message("Only image files are allowed.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=False)
        await interaction.followup.send(f"<a:loading:1269644867047260283> {interaction.user.mention}: processing.. (10-15 seconds)")

        try:
            async with self.session.get(image.url) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"Failed to download image. Status code: {resp.status}")
                    return
                image_data = await resp.read()

            form_data = aiohttp.FormData()
            form_data.add_field('file', image_data, filename='image.png', content_type='image/png')
            async with self.session.post('http://34.208.149.115:8889/locate', data=form_data) as api_resp:
                if api_resp.status != 200:
                    await interaction.followup.send(f"API request failed. Status code: {api_resp.status}")
                    return
                result = await api_resp.json()

            location = result.get("result", "Unknown location")
            confidence = result.get("confidence", "0%")
            response_text = f"The image was taken in **{location}**. ({confidence} confidence)"

            await interaction.edit_original_response(content=response_text)

        except Exception as e:
            await error_handler(interaction, e)

    @media.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(image="The image to blur.", togif="Make the image a gif?")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def blur(self, interaction: Interaction, image: Attachment, togif: bool = False):
        """Apply a blur effect to an image."""

        if not image.content_type.startswith('image/'):
            await interaction.followup.send("Only image and GIF files are allowed.", ephemeral=True)
            return

        try:
            async with self.session.get(image.url) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"Failed to download image. Status code: {resp.status}")
                    return
                
                image_data = io.BytesIO()
                async for chunk in resp.content.iter_chunked(8192):
                    image_data.write(chunk)
                image_data.seek(0)

            img = await asyncio.to_thread(Image.open, image_data)
            original_format = await asyncio.to_thread(lambda: img.format)
            is_gif = original_format == 'GIF'

            if is_gif:
                frames = await asyncio.to_thread(lambda: [frame.copy().convert('RGB') for frame in ImageSequence.Iterator(img)])
                durations = await asyncio.to_thread(lambda: [frame.info.get('duration', 100) for frame in ImageSequence.Iterator(img)])
            else:
                frames = [await asyncio.to_thread(img.convert, "RGB")]

            processed_frames = []
            for frame in frames:
                blurred = await asyncio.to_thread(lambda: frame.filter(ImageFilter.GaussianBlur(10)))
                processed_frames.append(blurred)
            
            output = io.BytesIO()
            if is_gif or (togif and len(processed_frames) > 1):
                await asyncio.to_thread(
                    lambda: processed_frames[0].save(
                        output,
                        format='GIF',
                        save_all=True,
                        append_images=processed_frames[1:],
                        duration=durations if is_gif else 100,
                        loop=0
                    )
                )
                file_extension = "gif"
            else:
                await asyncio.to_thread(processed_frames[0].save, output, format=original_format)
                file_extension = "gif" if togif else original_format.lower()

            output.seek(0)
            await interaction.followup.send(file=File(output, filename=f'heist.{file_extension}'))

        except Exception as e:
            await error_handler(interaction, e)

    @media.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(image="The image to add a speech bubble to.", togif="Make the image a gif?")
    @permissions.requires_perms(attach_files=True)
    async def speechbubble(self, interaction: Interaction, image: Attachment, togif: bool = False):
        "Add a speech bubble to an image."

        if not image.content_type.startswith('image/'):
            await interaction.followup.send("Only image files and GIF files are allowed.", ephemeral=True)
            return

        try:
            async with self.session.get(image.url) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"Failed to download image. Status code: {resp.status}")
                    return

                image_data = io.BytesIO()
                async for chunk in resp.content.iter_chunked(8192):
                    image_data.write(chunk)
                image_data.seek(0)

            img = await asyncio.to_thread(Image.open, image_data)
            original_format = await asyncio.to_thread(lambda: img.format)
            is_gif = original_format == 'GIF'

            if is_gif:
                frames = await asyncio.to_thread(lambda: [frame.copy().convert('RGBA') for frame in ImageSequence.Iterator(img)])
                durations = await asyncio.to_thread(lambda: [frame.info.get('duration', 100) for frame in ImageSequence.Iterator(img)])
            else:
                frames = [await asyncio.to_thread(img.convert, "RGBA")]

            speech_bubble_path = "/heist/structure/assets/speech_bubble.png"
            if not await asyncio.to_thread(os.path.exists, speech_bubble_path):
                await interaction.followup.send("Speech bubble asset not found.", ephemeral=True)
                return

            speech_bubble = await asyncio.to_thread(Image.open, speech_bubble_path)
            speech_bubble = await asyncio.to_thread(speech_bubble.convert, "RGBA")

            processed_frames = []
            for frame in frames:
                resized_bubble = await asyncio.to_thread(lambda: speech_bubble.resize(frame.size, Image.Resampling.LANCZOS))
                split_channels = await asyncio.to_thread(resized_bubble.split)
                bubble_data = split_channels[3]

                result = await asyncio.to_thread(Image.new, "RGBA", frame.size, (0, 0, 0, 0))
                await asyncio.to_thread(lambda: result.paste(frame, (0, 0)))
                await asyncio.to_thread(lambda: result.putalpha(ImageChops.subtract(result.split()[3], bubble_data)))
                processed_frames.append(result)

            output = io.BytesIO()
            if is_gif or (togif and len(processed_frames) > 1):
                await asyncio.to_thread(
                    lambda: processed_frames[0].save(
                        output,
                        format='GIF',
                        save_all=True,
                        append_images=processed_frames[1:],
                        duration=durations if is_gif else 100,
                        loop=0
                    )
                )
                file_extension = "gif"
            else:
                save_format = 'PNG' if original_format == 'JPEG' else original_format
                await asyncio.to_thread(processed_frames[0].save, output, format=save_format)
                file_extension = "gif" if togif else save_format.lower()

            output.seek(0)
            await interaction.followup.send(file=File(output, filename=f'heist.{file_extension}'))

        except Exception as e:
            await error_handler(interaction, e)

    @media.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(image="Image to add a caption to.", caption="The caption to add to the image.", togif="Make the image a gif?")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def caption(self, interaction: Interaction, image: Attachment, caption: str, togif: bool = False):
        "Add a caption to your image."

        if not image.content_type.startswith('image/'):
            await interaction.followup.send("Only image and GIF files are allowed.", ephemeral=True)
            return

        image_data = await image.read()
        if len(image_data) > 10 * 1024 * 1024:
            await interaction.followup.send("Image size exceeds the maximum allowed size (10 MB).", ephemeral=True)
            return

        async def process_image():
            output = io.BytesIO()
            pil_image = None
            frames = []
            processed_frames = []
            
            try:
                pil_image = await asyncio.to_thread(Image.open, io.BytesIO(image_data))
                original_format = await asyncio.to_thread(lambda: pil_image.format)
                is_gif = original_format == 'GIF'

                if is_gif:
                    frames = await asyncio.to_thread(lambda: [frame.copy().convert('RGBA') for frame in ImageSequence.Iterator(pil_image)])
                    durations = await asyncio.to_thread(lambda: [frame.info.get('duration', 100) for frame in ImageSequence.Iterator(pil_image)])
                else:
                    frames = await asyncio.to_thread(lambda: [pil_image.copy().convert('RGBA')])

                async def process_frame(frame):
                    try:
                        caption_height = await asyncio.to_thread(lambda: min(max(int(frame.height * 0.25), 50), 150))
                        new_image = await asyncio.to_thread(lambda: Image.new('RGBA', (frame.width, frame.height + caption_height), color='white'))
                        await asyncio.to_thread(lambda: new_image.paste(frame, (0, caption_height)))
                        
                        canvas = await asyncio.to_thread(lambda: Canvas.from_image(new_image))
                        font = await asyncio.to_thread(FontDB.Query, "futura")
                        max_width = await asyncio.to_thread(lambda: frame.width * 0.9)
                        max_height = await asyncio.to_thread(lambda: caption_height * 0.85)
                        font_size = await asyncio.to_thread(_get_font_size_for_text_sync, caption, max_width, max_height, font)
                        
                        await asyncio.to_thread(
                            lambda: draw_text_wrapped(
                                canvas=canvas,
                                text=caption,
                                x=new_image.width / 2,
                                y=caption_height / 2,
                                ax=0.5, ay=0.5,
                                size=font_size,
                                width=max_width,
                                font=font,
                                fill=Paint.Color((0, 0, 0, 255)),
                                align=TextAlign.Center,
                                draw_emojis=True,
                                wrap_style=WrapStyle.Word
                            )
                        )
                        
                        result = await asyncio.to_thread(lambda: canvas.to_image())
                        await asyncio.to_thread(new_image.close)
                        return result
                    except Exception as e:
                        print(f"Error processing frame: {e}")
                        return None

                def _get_font_size_for_text_sync(text, max_width, max_height, font):
                    size = min(int(max_width * 0.2), 100)
                    while size > 10:
                        text_width, text_height = text_size_multiline(
                            lines=text_wrap(
                                text=text,
                                width=int(max_width),
                                size=size,
                                wrap_style=WrapStyle.Word,
                                font=font,
                                draw_emojis=True
                            ),
                            size=size,
                            font=font,
                            draw_emojis=True
                        )
                        if text_width <= max_width * 0.95 and text_height <= max_height * 0.9:
                            return size
                        size -= 2
                    return 20

                processed_frames = await asyncio.gather(*[process_frame(frame) for frame in frames])
                processed_frames = [f for f in processed_frames if f is not None]

                if not processed_frames:
                    raise Exception("Failed to process image frames.")

                if is_gif or (togif and len(processed_frames) > 1):
                    await asyncio.to_thread(
                        lambda: processed_frames[0].save(
                            output,
                            format='GIF',
                            save_all=True,
                            append_images=processed_frames[1:],
                            loop=0,
                            duration=durations if is_gif else 100,
                            optimize=True,
                            disposal=2
                        )
                    )
                    file_extension = "gif"
                else:
                    if original_format == 'JPEG':
                        processed_frames[0] = await asyncio.to_thread(lambda: processed_frames[0].convert('RGB'))
                    await asyncio.to_thread(lambda: processed_frames[0].save(output, format=original_format))
                    file_extension = "gif" if togif else original_format.lower()

                output.seek(0)
                await interaction.followup.send(file=File(output, filename=f'heist.{file_extension}'))

            except Exception as e:
                await error_handler(interaction, e)
            
            finally:
                if pil_image:
                    await asyncio.to_thread(pil_image.close)
                
                for frame in frames:
                    try:
                        await asyncio.to_thread(frame.close)
                    except:
                        pass
                        
                for frame in processed_frames:
                    try:
                        await asyncio.to_thread(frame.close)
                    except:
                        pass

                if output:
                    await asyncio.to_thread(output.close)
                
                frames.clear()
                processed_frames.clear()

        await process_image()

    @convert.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(image="The image to convert to a GIF.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def image2gif(self, interaction: Interaction, image: Attachment):
        """Convert an image into a GIF."""
        if not image.content_type.startswith('image/'):
            await interaction.followup.send("Only image and GIF files are allowed.", ephemeral=True)
            return
        
        try:
            buffer = BytesIO(await image.read())
            
            buffer.seek(0)
            await interaction.followup.send(file=File(buffer, filename='heist.gif'))
            buffer.close()
        except Exception as e:
            await error_handler(interaction, e)
        
    @aitools.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(prompt="The prompt for the AI.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def llama(self, interaction: Interaction, prompt: str):
        """Ask LLaMA-3.1-8b-instant a question."""
        for _ in range(3):
            try:
                headers = {
                    'X-API-Key': API_KEY,
                    'Content-Type': 'application/json'
                }
                
                async with self.session.post(
                    'http://127.0.0.1:5094/chat',
                    json={'prompt': prompt, 'model': 'llama-3.1-8b-instant'},
                    headers=headers,
                    timeout=30
                ) as response:
                    if response.status != 200:
                        continue
                    
                    result = await response.json()
                    if result.get('status') == 'error':
                        continue
                        
                    ai_response = result['response']
                
                if len(prompt) > 40:
                    tprompt = prompt[:40] + ".."
                else:
                    tprompt = prompt

                prompt_message = f"* Prompt:\n```yaml\n{tprompt}```"
                full_message = f"{prompt_message}\n> **`Response ⬎`**\n{ai_response}"

                if len(full_message) > 4000:
                    full_message = full_message[:3997] + "..."
                
                embed = await cembed(interaction, description=f"{full_message}")
                embed.set_author(name="LLaMA Says", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url)
                embed.set_footer(text=footer, icon_url="https://git.cursi.ng/heist.png?c")
                embed.set_thumbnail(url="https://git.cursi.ng/meta_logo.png")
                await interaction.followup.send(embed=embed)
                return
            except:
                continue
        
        await interaction.followup.send("This AI model seems to be down at the moment. Try another one or try again later.")

    @aitools.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(prompt="The prompt for the AI.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def chatgpt(self, interaction: Interaction, prompt: str):
        """Ask ChatGPT a question (Internet access)."""
        for _ in range(3):
            try:
                url = f'https://text.pollinations.ai/prompt={prompt}?model=searchgpt'
                
                async with self.session.get(url, timeout=30) as response:
                    if response.status != 200:
                        continue
                    ai_response = await response.text()
                
                if len(prompt) > 40:
                    tprompt = prompt[:40] + ".."
                else:
                    tprompt = prompt

                prompt_message = f"* Prompt:\n```yaml\n{tprompt}```"
                full_message = f"{prompt_message}\n> **`Response ⬎`**\n{ai_response}"

                if len(full_message) > 4000:
                    full_message = full_message[:3997] + "..."
                
                embed = await cembed(interaction, description=f"{full_message}")
                embed.set_author(name="ChatGPT Says", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url)
                embed.set_footer(text=footer, icon_url="https://git.cursi.ng/heist.png?c")
                embed.set_thumbnail(url="https://git.cursi.ng/openai_logo.png")
                await interaction.followup.send(embed=embed)
                return
            except:
                continue
        
        await interaction.followup.send("This AI model seems to be down at the moment. Try another one or try again later.")

    @aitools.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(prompt="The prompt for the AI.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def claude(self, interaction: Interaction, prompt: str):
        """Ask Claude a question."""
        for _ in range(3):
            try:
                url = f'https://text.pollinations.ai/prompt={prompt}?model=claude-hybridspace'
                
                async with self.session.get(url, timeout=30) as response:
                    if response.status != 200:
                        continue
                    ai_response = await response.text()
                
                if len(prompt) > 40:
                    tprompt = prompt[:40] + ".."
                else:
                    tprompt = prompt

                prompt_message = f"* Prompt:\n```yaml\n{tprompt}```"
                full_message = f"{prompt_message}\n> **`Response ⬎`**\n{ai_response}"

                if len(full_message) > 4000:
                    full_message = full_message[:3997] + "..."
                
                embed = await cembed(interaction, description=f"{full_message}")
                embed.set_author(name="Claude Says", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url)
                embed.set_footer(text=footer, icon_url="https://git.cursi.ng/heist.png?c")
                embed.set_thumbnail(url="https://git.cursi.ng/anthropic_logo.png")
                await interaction.followup.send(embed=embed)
                return
            except:
                continue
        
        await interaction.followup.send("This AI model seems to be down at the moment. Try another one or try again later.")

    # @aitools.command()
    # @app_commands.allowed_installs(guilds=True, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    # @app_commands.describe(prompt="The prompt for the AI.", model="The model to use for the prompt.")
    # @app_commands.choices(model=[
    #     app_commands.Choice(name="deepseek", value="deepseek"),
    #     app_commands.Choice(name="deepseek-r1", value="deepseek-r1"),
    #     app_commands.Choice(name="deepseek-reasoner", value="deepseek-reasoner")
    # ])
    # @app_commands.check(permissions.is_blacklisted)
    # @permissions.requires_perms(embed_links=True)
    # async def deepseek(self, interaction: Interaction, prompt: str, model: str = "deepseek"):
    #     """Ask DeepSeek a question."""
    #     for _ in range(3):
    #         try:
    #             url = f'https://text.pollinations.ai/prompt={prompt}?model={model}'
                
    #             async with aiohttp.ClientSession() as session:
    #                 async with session.get(url, timeout=30) as response:
    #                     if response.status != 200:
    #                         continue
    #                     ai_response = await response.text()
                
    #             if len(prompt) > 40:
    #                 tprompt = prompt[:40] + ".."
    #             else:
    #                 tprompt = prompt

    #             prompt_message = f"* Prompt:\n```yaml\n{tprompt}```"
    #             full_message = f"{prompt_message}\n> **`Response ⬎`**\n{ai_response}"

    #             if len(full_message) > 4000:
    #                 full_message = full_message[:3997] + "..."
                
    #             embed = await cembed(interaction, description=f"{full_message}")
    #             embed.set_author(name=f"DeepSeek ({model}) Says", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url)
    #             embed.set_footer(text=footer, icon_url="https://git.cursi.ng/heist.png?c")
    #             embed.set_thumbnail(url="https://git.cursi.ng/deepseek_logo.png")
    #             await interaction.followup.send(embed=embed)
    #             return
    #         except:
    #             continue
        
    #     await interaction.followup.send("This AI model seems to be down at the moment. Try another one or try again later.")

    @aitools.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(prompt="The prompt for the AI.")
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.check(permissions.is_donor)
    @permissions.requires_perms(embed_links=True)
    async def destroylonely(self, interaction: Interaction, prompt: str):
        """✨ Ask rapper Destroy Lonely a question. (Unfiltered)"""
        for _ in range(3):
            try:
                system_prompt = "Respond like american rapper destroy lonely would, all lowercase, slangs like yo wassup, 00p1um, yvl, my vamp etc. feel free to press people a lil too."
                url = f'https://text.pollinations.ai/prompt={system_prompt} {prompt}?model=evil'
                
                async with self.session.get(url, timeout=30) as response:
                    if response.status != 200:
                        continue
                    ai_response = await response.text()
                
                if len(prompt) > 40:
                    tprompt = prompt[:40] + ".."
                else:
                    tprompt = prompt

                prompt_message = f"* Prompt:\n```yaml\n{tprompt}```"
                full_message = f"{prompt_message}\n> **`Response ⬎`**\n{ai_response}"

                if len(full_message) > 4000:
                    full_message = full_message[:3997] + "..."
                
                embed = await cembed(interaction, description=f"{full_message}")
                embed.set_author(name="Destroy Lonely Says", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url)
                embed.set_footer(text=footer, icon_url="https://git.cursi.ng/heist.png?c")
                embed.set_thumbnail(url="https://git.cursi.ng/destroy_lonely.png")
                await interaction.followup.send(embed=embed)
                return
            except:
                continue
        
        await interaction.followup.send("This AI model seems to be down at the moment. Try another one or try again later.")

    @aitools.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(prompt="The prompt to generate the image from.", model="The model to use for image generation.")
    @app_commands.choices(model=[
        app_commands.Choice(name="Flux (Quality)", value="flux"),
        #app_commands.Choice(name="Any-Dark", value="any-dark"),
        app_commands.Choice(name="Turbo (Fastest)", value="turbo")
    ])
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.check(permissions.is_donor)
    @permissions.requires_perms(attach_files=True)
    async def imagine(self, interaction: Interaction, prompt: str, model: str = "flux"):
        """✨ Generate an image based on the given prompt."""

        if not prompt.strip():
            await interaction.followup.send("Please provide a prompt to generate an image.", ephemeral=True)
            return
        
        start_time = time.time()

        try:
            await interaction.followup.send(f"<a:loading:1269644867047260283> {interaction.user.mention}: processing..")
            image_data, footer = await self.flux_gen(prompt, model)

            buffer = io.BytesIO(image_data)
            
            end_time = time.time()
            duration = end_time - start_time
            embed = await cembed(interaction, description=f"**Prompt:**\n> {prompt}\n\nImage generated in `{duration:.2f}s`.")
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar if interaction.user.avatar else interaction.user.default_avatar.url)
            embed.set_footer(text=f"{footer}", icon_url="https://git.cursi.ng/heist.png?c")

            if interaction.app_permissions.embed_links:
                await interaction.edit_original_response(content=None, embed=embed, attachments=[File(buffer, filename="heist.jpg")])
            else:
                await interaction.edit_original_response(
                    content=f"**Prompt:**\n> {prompt}\n\nImage generated in `{duration:.2f}s`.",
                    attachments=[File(buffer, filename="heist.jpg")]
                )

        except Exception as e:
            await error_handler(interaction, e)

    async def flux_gen(self, prompt, model):
        api_url = f"https://image.pollinations.ai/prompt/{prompt}?model={model}&nologo=true"
        
        async def fetch_and_process_image(api_url, model):
            async with self.session.get(api_url) as resp:
                if resp.status == 200:
                    image_data = await resp.read()

                    def process_image(image_data, model):
                        with Image.open(io.BytesIO(image_data)) as img:
                            width, height = img.size

                            if model != "flux":
                                crop_amount = int(height * 0.03)
                                img = img.crop((0, 0, width, height - crop_amount))
                                offset = 40
                            else:
                                offset = 20

                            draw = ImageDraw.Draw(img)
                            font_path = "structure/fonts/futura.otf"
                            font = ImageFont.truetype(font_path, 30)
                            text = "heist.lol"

                            text_bbox = draw.textbbox((0, 0), text, font=font)
                            text_width = text_bbox[2] - text_bbox[0]
                            text_height = text_bbox[3] - text_bbox[1]

                            position = (width - text_width - 10, height - text_height - offset)
                            draw.text(position, text, font=font, fill=(255, 255, 255))

                            output_buffer = io.BytesIO()
                            img.save(output_buffer, format='JPEG')
                            output_buffer.seek(0)
                            return output_buffer.getvalue()

                    image_data = await asyncio.to_thread(process_image, image_data, model)
                    return image_data, f"heist.lol - {model.lower()}"
                else:
                    raise Exception(f"API request failed with status {resp.status}. Please try again with another model or later.")
        
        try:
            return await fetch_and_process_image(api_url, model)
        except Exception as e:
            raise Exception(f"Failed to generate image: {str(e)}")

    @google.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(query="The query to search.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def search(self, interaction: Interaction, query: str):
        """Search for results on Google."""

        async def fetch_search_results():
            try:
                url = f"http://127.0.0.1:1118/search/google/v2"
                params = {"query": query}
                async with self.session.get(url, params=params, headers={"X-API-Key": API_KEY}) as response:
                    if response.status != 200:
                        return None, None
                    data = await response.json()
                    return data.get("results", []), data.get("finish_time", "N/A")
            except Exception as e:
                print(e)
                return None, None

        class SearchView(View):
            def __init__(self, results: list, interaction: Interaction, time_taken: str):
                super().__init__(timeout=120)
                self.results = results
                self.interaction = interaction
                self.message = None
                self.time_taken = time_taken
                self.create_dropdown()

            def create_dropdown(self):
                options = []
                for index, result in enumerate(self.results):
                    title = result.get("title", "Untitled")
                    if not title:
                        continue
                    if len(title) > 100:
                        title = title[:97] + "..."
                    
                    description = result.get("body", "No description available.")
                    if not description:
                        description = "No description available."
                    if len(description) > 100:
                        description = description[:97] + "..."
                    
                    options.append(discord.SelectOption(
                        label=title,
                        description=description,
                        value=str(index)
                    ))

                self.dropdown = Select(
                    placeholder="Select a result...",
                    options=options
                )
                self.dropdown.callback = self.dropdown_callback
                self.add_item(self.dropdown)

            async def dropdown_callback(self, interaction: Interaction):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.followup.send("You cannot interact with someone else's command.", ephemeral=True)
                    return

                selected_index = int(self.dropdown.values[0])
                if 0 <= selected_index < len(self.results):
                    await interaction.response.defer()
                    selected_result = self.results[selected_index]

                    embed = await cembed(
                        interaction,
                        title=selected_result.get("title", "Untitled"),
                        description=f"```fix\n{query}\n```\n{selected_result.get('body', 'No description available')}"
                    )

                    href = selected_result.get("href", "")
                    if href.startswith(("http://", "https://")):
                        embed.url = href

                    domain = selected_result.get("simple_domain", "unavailable")
                    icon_url = selected_result.get("thumbnail", "")
                    if icon_url.startswith(("http://", "https://")):
                        embed.set_author(name=domain, icon_url=icon_url)
                    else:
                        embed.set_author(name=domain)

                    embed.set_footer(text=f"Result {selected_index + 1}/{len(self.results)} • heist.lol", icon_url="https://git.cursi.ng/google_logo.png")
                    await interaction.edit_original_response(embed=embed, view=self)
                else:
                    await interaction.followup.send("Selected result not found.", ephemeral=True)

            async def on_timeout(self):
                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                        item.disabled = True

                try:
                    await self.interaction.edit_original_response(view=self)
                except discord.NotFound:
                    pass

        results, time_taken = await fetch_search_results()
        if results:
            view = SearchView(results, interaction, time_taken)
            first_result = results[0] if results else None

            embed = await cembed(
                interaction,
                title=first_result.get("title", "Untitled"),
                description=f"```fix\n{query}\n```\n{first_result.get('body', 'No description available')}",
            )

            href = first_result.get("href", "")
            if href.startswith(("http://", "https://")):
                embed.url = href

            domain = first_result.get("simple_domain", "unavailable")
            icon_url = first_result.get("thumbnail", "")
            if icon_url.startswith(("http://", "https://")):
                embed.set_author(name=domain, icon_url=icon_url)
            else:
                embed.set_author(name=domain)

            embed.set_footer(text=f"Result 1/{len(results)} • heist.lol", icon_url="https://git.cursi.ng/google_logo.png")
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message
        else:
            await interaction.followup.send("Umm... We are currently being ratelimited.....")

    @google.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(image="The image to search using Google Lens.")
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.check(permissions.is_disabled)
    async def lens(self, interaction: Interaction, image: Attachment):
        "Reverse search an image with Google Lens."
        await interaction.response.defer()

        if not image.content_type.startswith("image"):
            await interaction.followup.send("Please upload a valid image file.")
            return

        try:
            image_data = await image.read()
            async with aiofiles.open("heist.jpg", "wb") as f:
                await f.write(image_data)

            print(f"Image saved as heist.jpg. Size: {len(image_data)} bytes")

            search_results = self.lens.search_by_file("heist.jpg")
            print(f"Raw Search Results: {search_results}")

            if not search_results or not isinstance(search_results, list):
                print("No results found or invalid response from Google Lens.")
                await interaction.followup.send("No results found or invalid response from Google Lens.")
                return

            results_per_page = 5
            result_pages = []
            for i in range(0, len(search_results), results_per_page):
                page = search_results[i:i + results_per_page]
                result_pages.append(page)

            class LensView(discord.ui.View):
                def __init__(self, interaction: Interaction, result_pages: list):
                    super().__init__(timeout=240)
                    self.interaction = interaction
                    self.result_pages = result_pages
                    self.current_page = 0
                    self.update_button_states()

                def update_button_states(self):
                    self.previous_button.disabled = self.current_page == 0
                    self.next_button.disabled = self.current_page == len(self.result_pages) - 1

                async def update_content(self):
                    page = self.result_pages[self.current_page]
                    embed = await cembed(self.interaction, title="Google Lens")

                    for result in page:
                        title = result.get("title", "No Title")
                        description = result.get("description", "No Description")
                        url = result.get("url", "")

                        if url:
                            value = f"[`{description[:100]}...`]({url})" if description else "No Description"
                        else:
                            value = f"`{description[:100]}...`" if description else "No Description"

                        embed.add_field(name=title, value=value, inline=False)

                    embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.result_pages)} • heist.lol", icon_url="https://git.cursi.ng/google_logo.png")
                    await self.interaction.edit_original_response(embed=embed, view=self)

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary, custom_id="lensleft")
                async def previous_button(self, interaction: Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.followup.send("You cannot interact with someone else's message.", ephemeral=True)
                        return

                    if self.current_page > 0:
                        self.current_page -= 1
                        await interaction.response.defer()
                        self.update_button_states()
                        await self.update_content()

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary, custom_id="lensright")
                async def next_button(self, interaction: Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.followup.send("You cannot interact with someone else's message.", ephemeral=True)
                        return

                    if self.current_page < len(self.result_pages) - 1:
                        self.current_page += 1
                        await interaction.response.defer()
                        self.update_button_states()
                        await self.update_content()

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary, custom_id="lenssort")
                async def sort_button(self, interaction: Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's message.", ephemeral=True)
                        return

                    class GoToPageModal(discord.ui.Modal, title="Go to Page"):
                        def __init__(self, view):
                            super().__init__()
                            self.view = view
                            self.page_number = discord.ui.TextInput(
                                label="Navigate to page",
                                placeholder=f"Enter a page number (1-{len(self.view.result_pages)})",
                                min_length=1,
                                max_length=len(str(len(self.view.result_pages)))
                            )
                            self.add_item(self.page_number)

                        async def on_submit(self, interaction: Interaction):
                            try:
                                page = int(self.page_number.value) - 1
                                if page < 0 or page >= len(self.view.result_pages):
                                    raise ValueError
                                self.view.current_page = page
                                self.view.update_button_states()
                                await self.view.update_content()
                                await interaction.response.defer()
                            except ValueError:
                                await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

                    modal = GoToPageModal(self)
                    await interaction.response.send_modal(modal)

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger, custom_id="lensdelete")
                async def delete_button(self, interaction: Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's message.", ephemeral=True)
                        return

                    await interaction.response.defer()
                    await interaction.delete_original_response()

            view = LensView(interaction, result_pages)
            await view.update_content()

        except Exception as e:
            await error_handler(interaction, e)

    @brave.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(query="The query for the image search.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def image(self, interaction: Interaction, query: str):
        """Search for an image on Brave."""

        safe_search = True
        if interaction.guild:
            if interaction.channel.is_nsfw():
                safe_search = False
        else:
            safe_search = True

        try:
            result = await self.client.socials.brave.search_images(query, safe_search)
            
            if not result.image_urls:
                await interaction.followup.send("No images found.")
                return

            class ImageView(View):
                def __init__(self, images: list, titles: list, sources: list, interaction: Interaction, use_embed: bool):
                    super().__init__(timeout=120)
                    self.images = images
                    self.titles = titles
                    self.sources = sources
                    self.current_page = 0
                    self.interaction = interaction
                    self.message = None
                    self.use_embed = use_embed
                    self.update_button_states()

                def update_button_states(self):
                    self.previous_button.disabled = (self.current_page == 0)
                    self.next_button.disabled = (self.current_page == len(self.images) - 1)

                async def update_content(self):
                    if self.message is None:
                        return

                    image_url = self.images[self.current_page]
                    title = self.titles[self.current_page] or "No title"
                    source = self.sources[self.current_page]
                    
                    source_url = f"https://{source}" if source and not source.startswith(('http://', 'https://')) else source
                    if not source_url or not self._is_valid_url(source_url):
                        source_url = None

                    if self.use_embed:
                        embed_title = f"{title[:200]}" + (f" | {source}" if source else "")
                        embed = Embed(title=embed_title[:256])
                        if source_url:
                            embed.url = source_url
                        embed.set_image(url=image_url)
                        embed.set_author(
                            name=f"{self.interaction.user.name}",
                            icon_url=self.interaction.user.display_avatar.url
                        )
                        embed.set_footer(
                            text=f"Page {self.current_page + 1}/{len(self.images)} • brave.com",
                            icon_url="https://git.cursi.ng/brave_logo.png"
                        )
                        await self.message.edit(embed=embed, view=self)
                    else:
                        content_text = f"Query: **`{query}`**\nPage **`{self.current_page + 1}/{len(self.images)}`**"
                        if not self.use_embed:
                            content_text += "\n-# Missing the `Embed Links` permission in this server, so no embed for you."
                        async with self.session.get(image_url) as response:
                            image_bytes = await response.read()
                        await self.message.edit(content=content_text, attachments=[File(io.BytesIO(image_bytes), filename="heist.png")], view=self)

                def _is_valid_url(self, url: str) -> bool:
                    try:
                        result = urlparse(url)
                        return all([result.scheme, result.netloc])
                    except:
                        return False

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary, custom_id="imageleft")
                async def previous_button(self, interaction: Interaction, button: Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.followup.send("You cannot interact with someone else's command.", ephemeral=True)
                        return

                    if self.current_page > 0:
                        self.current_page -= 1
                        await interaction.response.defer()
                        self.update_button_states()
                        await self.update_content()

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary, custom_id="imageright")
                async def next_button(self, interaction: Interaction, button: Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.followup.send("You cannot interact with someone else's command.", ephemeral=True)
                        return

                    if self.current_page < len(self.images) - 1:
                        self.current_page += 1
                        await interaction.response.defer()
                        self.update_button_states()
                        await self.update_content()

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary, custom_id="imageskip")
                async def skip_button(self, interaction: Interaction, button: Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                        return

                    modal = GoToPageModal(len(self.images))
                    await interaction.response.send_modal(modal)
                    await modal.wait()
                    
                    if modal.page_number.value:
                        try:
                            page = int(modal.page_number.value) - 1
                            if 0 <= page < len(self.images):
                                self.current_page = page
                                self.update_button_states()
                                await self.update_content()
                        except ValueError:
                            pass

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger, custom_id="imagedelete")
                async def delete_button(self, interaction: Interaction, button: Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                        return

                    await interaction.response.defer()
                    await interaction.delete_original_response()

            class GoToPageModal(discord.ui.Modal):
                def __init__(self, max_pages: int):
                    super().__init__(title="Go to Page")
                    self.max_pages = max_pages
                    self.page_number = discord.ui.TextInput(
                        label="Navigate to page",
                        placeholder=f"Enter a page number (1-{max_pages})",
                        min_length=1,
                        max_length=len(str(max_pages)))
                    self.add_item(self.page_number)

                async def on_submit(self, interaction: Interaction):
                    await interaction.response.defer()

            use_embed = interaction.app_permissions.embed_links
            view = ImageView(result.image_urls, result.titles, result.sources, interaction, use_embed)

            first_title = result.titles[0] if result.titles and result.titles[0] else "No title"
            first_source = result.sources[0] if result.sources and result.sources[0] else None
            source_url = f"https://{first_source}" if first_source and not first_source.startswith(('http://', 'https://')) else first_source
            if not source_url or not view._is_valid_url(source_url):
                source_url = None

            if use_embed:
                embed = Embed(title=first_title[:256])
                if source_url:
                    embed.url = source_url
                    embed.description = f"> **{first_source}**"
                embed.set_image(url=result.image_urls[0])
                embed.set_author(
                    name=f"{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url
                )
                embed.set_footer(text=f"Page 1/{len(result.image_urls)} • brave.com", icon_url="https://git.cursi.ng/brave_logo.png")
                message = await interaction.followup.send(embed=embed, view=view)
            else:
                content_text = f"Query: **`{query}`**\nPage **`1/{len(result.image_urls)}`**\n-# Missing the `Embed Links` permission in this server, so no embed for you."
                async with self.session.get(result.image_urls[0]) as response:
                    image_bytes = await response.read()
                message = await interaction.followup.send(content=content_text, file=File(io.BytesIO(image_bytes), filename="image.png"), view=view)

            view.message = await interaction.original_response()
        except Exception as e:
            await error_handler(interaction, e)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user to fetch reviews for.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def reviewdb(self, interaction: Interaction, user: discord.User = None):
        """View someone's reviews on ReviewDB."""
        user = user or interaction.user
        user_id = str(user.id)

        class ReviewView(View):
            def __init__(self, reviews, interaction):
                super().__init__(timeout=120)
                self.reviews = [
                    review for review in reviews
                    if review["sender"].get("username", "") != "Warning"
                ]
                self.current_page = 0
                self.interaction = interaction
                self.message = None
                
                self.previous_button = Button(
                    emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"),
                    style=discord.ButtonStyle.primary,
                    custom_id="reviewleft"
                )
                self.next_button = Button(
                    emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"),
                    style=discord.ButtonStyle.primary,
                    custom_id="reviewright"
                )
                self.skip_button = Button(
                    emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"),
                    style=discord.ButtonStyle.secondary,
                    custom_id="reviewskip"
                )
                self.delete_button = Button(
                    emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"),
                    style=discord.ButtonStyle.danger,
                    custom_id="reviewdelete"
                )
                
                self.previous_button.callback = self.previous_button_callback
                self.next_button.callback = self.next_button_callback
                self.skip_button.callback = self.skip_button_callback
                self.delete_button.callback = self.delete_button_callback
                
                self.add_item(self.previous_button)
                self.add_item(self.next_button)
                self.add_item(self.skip_button)
                self.add_item(self.delete_button)
                
                self.update_button_states()

            def update_button_states(self):
                total_pages = (len(self.reviews) + 9) // 10
                self.previous_button.disabled = (self.current_page == 0)
                self.next_button.disabled = (self.current_page >= total_pages - 1)

            async def on_timeout(self):
                for item in view.children:
                    if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                        item.disabled = True

                try:
                    await interaction.edit_original_response(view=view)
                except discord.NotFound:
                    pass

            async def update_embed(self):
                start = self.current_page * 10
                end = start + 10
                review_page = self.reviews[start:end]

                review_strings = []
                for review in review_page:
                    sender = review["sender"]
                    username = sender.get("username", "Deleted User")
                    comment = review["comment"]
                    timestamp = review["timestamp"]
                    date = datetime.utcfromtimestamp(timestamp).strftime("%m/%d/%Y")
                    review_string = f"**{username}** ({date}): {comment}"
                    review_strings.append(review_string)

                review_text = "\n".join(review_strings) or "No reviews available."
                embed = await cembed(
                    interaction,
                    title=f"Reviews [{len(self.reviews)}]",
                    description=review_text
                )
                
                embed.set_author(name=f"{user.name} ({user.id})", icon_url=user.display_avatar.url)
                embed.set_thumbnail(url=user.display_avatar.url)
                
                total_pages = (len(self.reviews) + 9) // 10
                embed.set_footer(text=f"Page {self.current_page + 1}/{total_pages} - {footer}", icon_url="https://git.cursi.ng/heist.png?c")

                if self.message is None:
                    self.message = await self.interaction.followup.send(embed=embed, view=self)
                else:
                    await self.message.edit(embed=embed, view=self)

            async def previous_button_callback(self, interaction: Interaction):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return

                await interaction.response.defer()
                if self.current_page > 0:
                    self.current_page -= 1
                    self.update_button_states()
                    await self.update_embed()

            async def next_button_callback(self, interaction: Interaction):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return

                await interaction.response.defer()
                if self.current_page < (len(self.reviews) - 1) // 10:
                    self.current_page += 1
                    self.update_button_states()
                    await self.update_embed()

            async def skip_button_callback(self, interaction: Interaction):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return

                class GoToPageModal(discord.ui.Modal, title="Go to Page"):
                    page_number = discord.TextInput(label="Navigate to page", placeholder=f"Enter a page number (1-{len(self.reviews) // 10 + 1})", min_length=1, max_length=len(str(len(self.reviews) // 10 + 1)))

                    async def on_submit(self, interaction: Interaction):
                        try:
                            page = int(self.page_number.value) - 1
                            if page < 0 or page >= len(self.view.reviews) // 10 + 1:
                                raise ValueError
                            self.view.current_page = page
                            self.view.update_button_states()
                            await self.view.update_embed()
                            await interaction.response.defer()
                        except ValueError:
                            await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

                modal = GoToPageModal()
                modal.view = self
                await interaction.response.send_modal(modal)

            async def delete_button_callback(self, interaction: Interaction):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                    return

                await interaction.response.defer()
                await interaction.delete_original_response()

        try:
            url = f"https://manti.vendicated.dev/api/reviewdb/users/{user_id}/reviews"
            async with self.session.get(url) as response:
                data = await response.json()

                if not data.get("success"):
                    return await interaction.followup.send("Error: " + data.get("message", "Unknown error occurred"))

                reviews = data.get("reviews", [])
                if not reviews:
                    return await interaction.followup.send("No reviews found.")

                view = ReviewView(reviews, interaction)
                await view.update_embed()

        except Exception as e:
            await error_handler(interaction, e)

    #@app_commands.command()
    #@app_commands.allowed_installs(guilds=True, users=True)
    #@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    #@app_commands.describe(ip="The IP address to look up.")
    #@app_commands.check(permissions.is_blacklisted)
    #@permissions.requires_perms(embed_links=True)
    async def iplookup(self, interaction: Interaction, ip: str):
        """Lookup an IP address."""

        if ip in {".", "localhost", "127.0.0.1"}:
            await interaction.followup.send("nuh uh.")
            return

        IP_REGEX = re.compile(r'^(?!0)(?!.*\.$)(?!.*\.\.)(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?:(?:/[\d]{1,2})|(?:#[\w-]*)?)?$')
        if not IP_REGEX.match(ip):
            await interaction.followup.send("The IP address is not valid. Please enter a valid IPv4 address.")
            return

        try:
            url = f"http://ip-api.com/json/{ip}?fields=status,message,continent,continentCode,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,mobile,proxy"
            async with self.session.get(url) as response:
                data = await response.json()

                if data.get("status") != "success":
                    return await interaction.followup.send("You cannot do this because: " + data.get("message", "Unknown error occurred"))

                continent = f"{data['continent']} ({data['continentCode']})"
                country = f"{data['country']} ({data['countryCode']})"
                region = f"{data['regionName']} ({data['region']})"
                city = data['city']
                zip_code = data['zip']
                latitude = data['lat']
                longitude = data['lon']
                timezone = data['timezone']
                isp = data['isp']
                organization = data['org']
                as_number = data['as']
                mobile = "Yes" if data['mobile'] else "No"
                proxy = "Yes" if data['proxy'] else "No"
                embed = await cembed(interaction, title=f"IP Lookup: {ip}")
                embed.add_field(name="Continent", value=continent, inline=True)
                embed.add_field(name="Country", value=country, inline=True)
                embed.add_field(name="Region", value=region, inline=True)
                embed.add_field(name="City", value=city, inline=True)
                embed.add_field(name="Zip Code", value=zip_code, inline=True)
                embed.add_field(name="Latitude", value=latitude, inline=True)
                embed.add_field(name="Longitude", value=longitude, inline=True)
                embed.add_field(name="Timezone", value=timezone, inline=True)
                embed.add_field(name="ISP", value=isp, inline=True)
                embed.add_field(name="Organization", value=organization, inline=True)
                embed.add_field(name="AS Number", value=as_number, inline=True)
                embed.add_field(name="Proxy", value=proxy, inline=True)
                embed.set_author(name=f"{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
                embed.set_footer(text=f"{footer}", icon_url="https://git.cursi.ng/heist.png?c")

                await interaction.followup.send(embed=embed)

        except Exception as e:
            await error_handler(interaction, e)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        title="The title of the embed",
        description="The description of the embed",
        author="The author of the embed",
        footer="The footer of the embed",
        footer_image="The image for the footer",
        image="The image for the embed",
        thumbnail="The thumbnail for the embed",
        color="The color of the embed (in HEX format)"
    )
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def embed(self, interaction: Interaction, title: str = "", description: str = "", author: str = "", footer: str = "", footer_image: Attachment = None, image: Attachment = None, thumbnail: Attachment = None, color: str = "0x3b3b3b"):
        """Create a custom embed."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        title_field = title.replace("{timestamp}", timestamp)
        description_field = description.replace("{timestamp}", timestamp).replace("\\n", "\n")
        footer_field = footer.replace("{timestamp}", timestamp) if footer else ""
        author_field = author.replace("{timestamp}", timestamp) if author else ""

        if not title and not description:
            await interaction.followup.send("You need to provide either a title or a description. Use </embedusage:1278389799857946703> to learn more.", ephemeral=True)
            return
        
        try:
            if color.startswith("#"):
                color_int = int(color[1:], 16)
            else:
                color_int = int(color, 16)
            if not 0 <= color_int <= 0xffffff:
                raise ValueError("Invalid color. Only HEX values are accepted.")
        except ValueError:
            color_int = 0x3b3b3b

        max_newlines = 20
        description_lines = description_field.split("\n")
        description_field = "\n".join(description_lines[:max_newlines]) + ("\n" if len(description_lines) > max_newlines else "")

        embed = Embed(title=title_field, description=description_field, color=color_int)
        
        if author_field:
            embed.set_author(name=author_field)

        if footer_image:
            embed.set_footer(text=footer_field, icon_url=footer_image.url)
        else:
            embed.set_footer(text=footer_field, icon_url="")

        if thumbnail:
            embed.set_thumbnail(url=thumbnail.url)

        if image:
            embed.set_image(url=image.url)

        await interaction.followup.send(embed=embed)

    @selfembed.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def builder(self, interaction: Interaction):
        "Create a self-embed."
        is_donor = await check_donor(interaction.user.id)
        user_id = str(interaction.user.id)
        async with get_db_connection() as conn:
            current_presets = await conn.fetchval(
                "SELECT COUNT(*) FROM embed_presets WHERE user_id = $1",
                user_id
            )
            
            max_presets = 10 if is_donor else 5
            
            if current_presets >= max_presets:
                message = (
                    f"You've reached your maximum limit of {max_presets} embed presets. "
                    "To create more, you'll need to delete some existing presets.."
                )
                
                if not is_donor:
                    message += " or upgrade to Premium for 5 additional preset slots! </premium buy:1278389799857946700>"
                
                await interaction.response.send_message(message, ephemeral=True)
                return
                
            remaining_slots = max_presets - current_presets
            footer_text = f"Use the buttons below to customise the embed.\nYou have {remaining_slots} preset slot{'s' if remaining_slots != 1 else ''} remaining."
            view = EmbedBuilderView(interaction.user.id, footer_text)
            
            initial_embed = view.embed
            
            await interaction.response.send_message(embed=initial_embed, view=view, ephemeral=True)

    @selfembed.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.describe(preset="The name of the preset you want to load.")
    async def load(self, interaction: Interaction, preset: str):
        "Load a self-embed preset."
        async with get_db_connection() as conn:
            try:
                embed_data = await conn.fetchrow(
                    "SELECT * FROM embed_presets WHERE user_id = $1 AND preset_name = $2",
                    str(interaction.user.id), preset
                )
                
                if not embed_data:
                    await interaction.response.send_message(f"No preset found with name '{preset}'.", ephemeral=True)
                    return

                embed = Embed()
                
                if embed_data['color']:
                    embed.color = int(embed_data['color'][1:], 16)
                    
                if embed_data['description']:
                    embed.description = embed_data['description']
                            
                if embed_data['title']:
                    embed.title = embed_data['title']
                
                if embed_data['author']:
                    embed.set_author(
                        name=embed_data['author'],
                        icon_url=embed_data['author_image'] if embed_data['author_image'] else None
                    )
                if embed_data['footer']:
                    embed.set_footer(
                        text=embed_data['footer'],
                        icon_url=embed_data['footer_image'] if embed_data['footer_image'] else None
                    )
                if embed_data['image']:
                    embed.set_image(url=embed_data['image'])
                if embed_data['thumbnail']:
                    embed.set_thumbnail(url=embed_data['thumbnail'])
                if embed_data['timestamp']:
                    embed.timestamp = datetime.utcnow()
                
                await interaction.response.send_message(embed=embed)
                
            except Exception as e:
                await error_handler(interaction, e)

    @selfembed.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(preset="The name of the preset you want to edit.")
    @app_commands.check(permissions.is_blacklisted)
    async def edit(self, interaction: Interaction, preset: str):
        "Edit a self-embed preset."
        async with get_db_connection() as conn:
            preset_data = await conn.fetchrow(
                """SELECT * FROM embed_presets 
                WHERE user_id = $1 AND preset_name = $2""",
                str(interaction.user.id), preset
            )
            
            if not preset_data:
                await interaction.response.send_message("Preset not found.", ephemeral=True)
                return

            view = EditEmbedBuilderView(interaction.user.id, preset_data['id'], preset)
            view.embed_data = {
                "title": preset_data['title'],
                "description": preset_data['description'],
                "footer": preset_data['footer'],
                "author": preset_data['author'],
                "footer_image": preset_data['footer_image'],
                "image": preset_data['image'],
                "thumbnail": preset_data['thumbnail'],
                "author_image": preset_data['author_image'],
                "color": preset_data['color'],
                "timestamp": preset_data['timestamp']
            }
            await view.update_embed()
            await interaction.response.send_message(embed=view.embed, view=view, ephemeral=True)

    @selfembed.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.describe(preset="The name of the preset you want to delete.")
    async def delete(self, interaction: Interaction, preset: str):
        "Delete a self-embed preset."
        try:
            async with get_db_connection() as conn:
                deleted_count = await conn.execute(
                    "DELETE FROM embed_presets WHERE user_id = $1 AND preset_name = $2",
                    str(interaction.user.id),
                    preset
                )
                
                if deleted_count:
                    await interaction.response.send_message(
                        messages.success(interaction.user, f"Successfully deleted preset: `{preset}`"),
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        messages.warn(interaction.user, f"No preset found with name: `{preset}`\nUse </selfembed list:1298023579224637511> to see your saved presets."),
                        ephemeral=True
                    )
                
        except Exception as e:
            await error_handler(interaction, e)

    @selfembed.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def list(self, interaction: Interaction):
        "List of your self-embed presets."
        try:
            async with get_db_connection() as conn:
                presets = await conn.fetch(
                    """SELECT preset_name, title, description 
                    FROM embed_presets 
                    WHERE user_id = $1 
                    """,
                    (str(interaction.user.id))
                )
                
                if not presets:
                    await interaction.response.send_message(
                        "❌ You don't have any saved embed presets. Use </selfembed builder:1298023579224637511> to create one!",
                        ephemeral=True
                    )
                    return

                embed = await cembed(
                    interaction,
                    title="📋 Self-Embed presets",
                    description=f"You have **{len(presets)}** saved presets."
                )

                for i, preset in enumerate(presets, 1):
                    title = preset['title'] or 'No title'
                    description = preset['description'] or 'No description'
                    
                    preset_info = f"**Title:** {title[:50]}{'...' if len(title) > 50 else ''}\n"
                    preset_info += f"**Description:** {description[:100]}{'...' if len(description) > 100 else ''}\n"
                    
                    embed.add_field(
                        name=f"{i}. {preset['preset_name']}",
                        value=preset_info,
                        inline=False
                    )

                embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
                embed.set_footer(text="Use /selfembed delete to remove a preset.", icon_url="https://git.cursi.ng/heist.png?c")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await error_handler(interaction, e)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def discordstatus(self, interaction: Interaction):
        """Get the current status of Discord."""
        async def fetch_discord_status(attempt: int = 1):
            try:
                async with self.session.get('https://discordstatus.com/api/v2/summary.json', timeout=aiohttp.ClientTimeout(total=3)) as response:
                    response.raise_for_status()
                    data = await response.json()
            except aiohttp.ClientError as e:
                if attempt < 3:
                    await asyncio.sleep(1)
                    return await fetch_discord_status(attempt + 1)
                else:
                    raise aiohttp.ClientError(f"Failed to fetch Discord status after {attempt} attempts: {e}")
            return data

        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            data = await fetch_discord_status()
            embed = await cembed(interaction, title="Discord Status")
            components = {component['name']: component['status'] for component in data['components']}
            embed.add_field(
                name="System Status",
                value="\n".join([
                    f"{name}: {components.get(name, 'unknown')}" for name in [
                        'API', 'CloudFlare', 'Gateway', 'Desktop', 'Web', 'Android', 'iOS'
                    ]
                ]),
                inline=False
            )
            if data.get("incidents"):
                embed.add_field(name="Current Incidents", value="\n".join(incident['name'] for incident in data["incidents"]), inline=False)
            else:
                embed.add_field(name="Current Incidents", value="No Ongoing Incidents", inline=False)
            await interaction.followup.send(embed=embed)
        except aiohttp.ClientError as e:
            print(f"{e}")
            await interaction.followup.send(f"Error: Failed to fetch Discord status ({e})")
        except KeyError as e:
            print(f"{e}")
            await interaction.followup.send(f"Error: Malformed JSON data ({e})")
        except Exception as e:
            await error_handler(interaction, e)

    @google.command()
    @app_commands.allowed_installs(guilds=True, users=True) 
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(to="Text to translate to.", text="Text to translate.")
    @app_commands.check(permissions.is_blacklisted)
    async def translate(self, interaction: Interaction, to: str, text: str):
        """Translate text with Google."""
        async def call_after():
            try:
                normalized_to = to.capitalize()

                if normalized_to not in real_languages:
                    await interaction.followup.send("That language is not available. Request it [here](<https://discord.gg/4XJJvhzwVn>).\nYou can use `/askheist` as an alternative.", ephemeral=True)
                    return

                detected_lang = self.translator.detect(text)
                detected_lang_name = LANGUAGES.get(detected_lang.lang, detected_lang.lang.title()).capitalize()
                translated = self.translator.translate(text, dest=normalized_to)

                if translated is None:
                    await interaction.followup.send("Translation failed. Please try again.", ephemeral=True)
                    return
                
                to_lang_name = normalized_to
                embed = await cembed(interaction, description=f"**Original ({detected_lang_name}):** {text}\n**Translation ({to_lang_name}):** {translated.text}")
                embed.set_author(name="Translation", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url)
                embed.set_footer(text=f"{footer}", icon_url="https://git.cursi.ng/translate_logo.png")
                if interaction.app_permissions.embed_links:
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"**Original ({detected_lang_name}):** {text}\n**Translation ({to_lang_name}):** {translated.text}\n-# Missing the `Embed Links` permission in this server, so no embed for you.")

            except Exception as e:
                await error_handler(interaction, e)

        await interaction.response.defer(thinking=True)
        await call_after()

    @translate.autocomplete("to")
    async def translate_autocomplete(self, interaction: Interaction, current: str):
        filtered_languages = [app_commands.Choice(name=lang, value=lang) for lang in valid_languages if current.lower() in lang.lower()]
        return filtered_languages

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(pick="The emoji to get information on.")
    @permissions.requires_perms(embed_links=True)
    async def emoji(self, interaction: Interaction, pick: str):
        """Get information about an emoji"""
        async def call_after():
            try:
                custom_emoji_regex = re.compile(r'<(a)?:([A-Za-z0-9_]+):(\d+)>')
                match = custom_emoji_regex.match(pick)

                if match:
                    animated, name, id = match.groups()
                    animated = bool(animated)

                    snowflake_id = int(id)
                    timestamp = (snowflake_id >> 22) + 1420070400000
                    creation_date = datetime.utcfromtimestamp(timestamp / 1000.0)
                    embed = await cembed(interaction, title="Custom Emoji Information")
                    embed.add_field(name="Name", value=name, inline=True)
                    embed.add_field(name="ID", value=id, inline=True)
                    embed.add_field(name="Created", value=f"<t:{int(creation_date.timestamp())}:f> (<t:{int(creation_date.timestamp())}:R>)")
                    embed.add_field(name="Direct Link", value=f"https://cdn.discordapp.com/emojis/{id}.{'gif' if animated else 'png'}")
                    embed.set_image(url=f"https://cdn.discordapp.com/emojis/{id}.{'gif' if animated else 'png'}")
                    embed.set_footer(text=f"{footer}", icon_url="https://git.cursi.ng/heist.png?c")
                    await interaction.followup.send(embed=embed, ephemeral=False)
                else:
                    await interaction.followup.send("Invalid emoji format. Please provide a custom emoji.")
            except Exception as e:
                await error_handler(interaction, e)

        await call_after()

    # @app_commands.command()
    # @app_commands.allowed_installs(guilds=True, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    # @app_commands.check(permissions.is_blacklisted)
    # async def wikipedia(self, interaction: Interaction, query: str):
    #     """Searches Wikipedia for your requested query."""
    #     async def call_after():
    #         wikipedia_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.strip().replace(' ', '_')}"

    #         async with aiohttp.ClientSession() as session:
    #             async with session.get(wikipedia_url) as response:
    #                 if response.status == 200:
    #                     data = await response.json()
    #                     if 'extract' in data:
    #                         embed = Embed(title=data['title'], description=f"```{data['extract'][:4090]}```", url=data['content_urls']['desktop']['page'], color=0x000000)
    #                         if 'thumbnail' in data:
    #                             embed.set_thumbnail(url=data['thumbnail']['source'])
    #                         embed.set_footer(text=f"{footer}", icon_url="https://git.cursi.ng/wikipedia_logo.png")
    #                         if interaction.app_permissions.embed_links:
    #                             try:
    #                                 await interaction.followup.send(embed=embed)
    #                             except Exception as e:
    #                                 await error_handler(interaction, e)
    #                         else:
    #                             await interaction.followup.send("-# Missing the `Embed Links` permission in this server.", ephemeral=True)
    #                     else:
    #                         await interaction.followup.send(f"No results found for {query}.")
    #                 else:
    #                     await interaction.followup.send(f"No results found for {query}.")

    #     await interaction.response.defer(thinking=True)
    #     await call_after()

    # @website.command()
    # @app_commands.allowed_installs(guilds=True, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    # @app_commands.describe(url="The URL of the website.")
    # @permissions.requires_perms(embed_links=True)
    # async def preview(self, interaction: Interaction, url: str):
    #     """Preview metadata of a website."""

    #     if not url.startswith(('http://', 'https://')):
    #         url = 'https://' + url

    #     try:
    #         headers = {
    #             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    #         }
    #         timeout = aiohttp.ClientTimeout(total=10)

    #         async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
    #             try:
    #                 async with session.get(url) as response:
    #                     if response.status == 200:
    #                         html = await response.text()
    #                         soup = BeautifulSoup(html, 'html.parser')
                            
    #                         title = soup.title.string if soup.title else "No Title"
                            
    #                         description = ""
    #                         og_description = soup.find("meta", property="og:description")
    #                         if og_description and og_description.get("content"):
    #                             description = og_description.get("content")
    #                         else:
    #                             meta_description = soup.find("meta", attrs={"name": "description"})
    #                             if meta_description and meta_description.get("content"):
    #                                 description = meta_description.get("content")
                            
    #                         twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
    #                         twitter_image_url = twitter_image.get("content") if twitter_image else None

    #                         og_image = soup.find("meta", property="og:image")
    #                         og_image_url = og_image.get("content") if og_image else None

    #                         def make_absolute(image_url):
    #                             if image_url and image_url.startswith('/'):
    #                                 parsed_url = urlparse(url)
    #                                 return f"{parsed_url.scheme}://{parsed_url.netloc}{image_url}"
    #                             return image_url

    #                         twitter_image_url = make_absolute(twitter_image_url)
    #                         og_image_url = make_absolute(og_image_url)

    #                         theme_color = soup.find("meta", attrs={"name": "theme-color"})
    #                         theme_color = theme_color.get("content") if theme_color else None

    #                         if theme_color:
    #                             theme_color = theme_color.strip().lower()
                                
    #                             if theme_color.startswith('0x'):
    #                                 theme_color = theme_color[2:]
                                
    #                             if theme_color.startswith('#'):
    #                                 if len(theme_color) == 7:
    #                                     try:
    #                                         embed_color = int(theme_color[1:], 16)
    #                                     except ValueError:
    #                                         embed_color = None
    #                                 else:
    #                                     embed_color = None
    #                             else:
    #                                 embed_color = None
    #                         else:
    #                             embed_color = None
                            
    #                         embed = await cembed(
    #                             interaction,
    #                             title=title,
    #                             description=description,
    #                             url=url,
    #                             color=embed_color
    #                         )
                            
    #                         if twitter_image_url:
    #                             embed.set_image(url=twitter_image_url)
                            
    #                         if og_image_url and og_image_url != twitter_image_url:
    #                             embed.set_thumbnail(url=og_image_url)
                            
    #                         domain = urlparse(url).netloc
    #                         favicon_url = f"https://www.google.com/s2/favicons?sz=64&domain={url}"
    #                         try:
    #                             async with session.get(favicon_url) as favicon_response:
    #                                 if favicon_response.status != 200:
    #                                     favicon_url = "https://git.cursi.ng/globe.png"
    #                         except:
    #                             favicon_url = "https://git.cursi.ng/globe.png"
                            
    #                         embed.set_author(
    #                             name=domain,
    #                             icon_url=favicon_url,
    #                             url=f"https://{domain}"
    #                         )
    #                         await interaction.followup.send(embed=embed)
    #                     else:
    #                         await interaction.followup.send("Can't fetch metadata, probably Cloudflare.")
    #             except aiohttp.ClientError as e:
    #                 await interaction.followup.send(f"The website is invalid or unreachable. Error: {str(e)}")
    #             except asyncio.TimeoutError:
    #                 await interaction.followup.send("The request timed out. The website may be too slow or unavailable.")
    #     except Exception as e:
    #         print(e)
    #         await error_handler(interaction, e)

    @website.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="The URL you want to take a screenshot from.", delay="Seconds to allocate for loading the website.")
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.check(permissions.is_tester)
    @permissions.requires_perms(attach_files=True)
    async def screenshot(self, interaction: Interaction, url: str, delay: str = "0"):
        """✨ Take a screenshot of any website."""

        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        try:
            delay = int(delay)
            if delay > 15:
                raise ValueError("Delay cannot be more than 15 seconds.")
        except ValueError as ve:
            await interaction.followup.send(f"Invalid delay input: {ve}", ephemeral=True)
            return

        if delay == 0:
            initial_message = "Screenshotting now.."
        else:
            timestamp = int(time.time()) + delay
            relative_time = f"<t:{timestamp}:R>"
            initial_message = f"Screenshotting {relative_time}.."

        await interaction.followup.send(initial_message)
        screenshot_api_url = f"http://127.0.0.1:5008/screenshot?url={url}&delay={delay}"
        async def update_message():
            if delay > 0:
                await asyncio.sleep(delay)
                await interaction.edit_original_response(content="Screenshotting now..")

        async def fetch_screenshot():
            async with self.session.get(screenshot_api_url) as response:
                if response.status == 200:
                    screenshot_bytes = await response.read()
                    screenshot_file = File(BytesIO(screenshot_bytes), filename="screenshot.png")
                    await interaction.edit_original_response(content=None, attachments=[screenshot_file])
                else:
                    await interaction.edit_original_response(content=f"Failed to fetch screenshot: {response.status} - {response.reason}")

        await asyncio.gather(update_message(), fetch_screenshot())

    # @website.command()
    # @app_commands.allowed_installs(guilds=True, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    # @app_commands.describe(url="The URL of the website to download.")
    # @app_commands.check(permissions.is_blacklisted)
    # @app_commands.check(permissions.is_donor)
    # @permissions.requires_perms(attach_files=True)
    # async def skid(self, interaction: Interaction, url: str):
    #     """✨ Skid a website."""

    #     if not url.startswith(('http://', 'https://')):
    #         url = 'https://' + url

    #     if 'localhost' in url:
    #         await interaction.followup.send("You can't download from local or private addresses.")
    #         return

    #     try:
    #         async with aiohttp.ClientSession() as session:
    #             api_url = f"http://34.208.149.115:5008/download?url={url}"
    #             async with session.get(api_url) as response:
    #                 if response.status == 200:
    #                     zip_data = await response.read()
    #                     await interaction.followup.send(file=File(io.BytesIO(zip_data), filename="website.zip"))
    #                 else:
    #                     error_message = await response.text()
    #                     await interaction.followup.send(f"Error: {error_message}")
    #     except Exception as e:
    #         await interaction.followup.send(f"An error occurred: {str(e)}")

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="The URL you want to bypass.")
    @app_commands.check(permissions.is_blacklisted)
    @cooldown(default=10, donor=5)
    async def bypass(self, interaction: Interaction, url: str):
        """Bypass annoying URL shorteners."""
        await interaction.response.defer(thinking=True)

        fluxus = r'flux\.li'
        api = "http://localhost:1117/api/fluxus"

        if re.search(fluxus, url):
            try:
                async with self.session.get(f"{api}?link={url}") as response:
                    data = await response.json()

                if data['status'] == 'success':
                    key = data['key']
                    if interaction.app_permissions.embed_links:
                        embed = await cembed(
                            interaction,
                            title="✅ Bypassed Fluxus Key",
                        )
                        embed.add_field(name="🔑 Key:", value=f"**{key}**", inline=False)
                        embed.add_field(name="🌐 URL Provided:", value=f"{url}", inline=False)
                        embed.set_thumbnail(url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url)
                        embed.set_footer(text=footer, icon_url="https://git.cursi.ng/heist.png?c")
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send(
                            f"**Key**: {key}\n-# Missing the `Embed Links` permission in this server, so no embed for you."
                        )
                else:
                    await interaction.followup.send(
                        f"❌ Failed to bypass Fluxus."
                    )

            except Exception as e:
                await error_handler(interaction, e)

        else:
            api_url = f"https://api.bypass.vip/premium/bypass?url={url}"

            if not url.startswith("http://") and not url.startswith("https://"):
                url = f"https://{url}"

            headers = {
                "x-api-key": "6d7dda3f-1658-4083-8e3c-b25ee7c12496"
            }

            try:
                async with self.session.get(api_url, headers=headers) as response:
                    data = await response.json()

                if data['status'] == 'success':
                    bypassed_url = data['result']
                    if interaction.app_permissions.embed_links:
                        embed = await cembed(
                            interaction,
                            title="✅ Bypassed URL",
                        )
                        embed.add_field(name="🏹 Leads to:", value=f"{bypassed_url}", inline=False)
                        embed.add_field(name="🌐 URL Provided:", value=f"{url}", inline=False)
                        embed.set_thumbnail(url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url)
                        embed.set_footer(text="bypass.vip", icon_url="https://git.cursi.ng/heist.png?c")
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send(
                            f"{bypassed_url}\n-# Missing the `Embed Links` permission in this server, so no embed for you."
                        )
                else:
                    await interaction.followup.send(
                        f"❌ Failed to bypass URL."
                    )

            except Exception as e:
                await error_handler(interaction, e)
                    
    @bitcoin.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(address="Bitcoin address.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def address(self, interaction: Interaction, address: str):
        "Lookup a Bitcoin address."

        def btc_validity(address: str) -> bool:
            return bool(re.match(r'^(1|3|bc1)[a-zA-Z0-9]{25,40}$', address))

        if not btc_validity(address):
            await interaction.followup.send("Invalid Bitcoin address format.", ephemeral=True)
            return

        async with self.session.get(f'https://api.blockchair.com/bitcoin/dashboards/address/{address}?key={BLOCKCHAIR_KEY}') as response:
            if response.status != 200:
                await interaction.followup.send("Failed to fetch address data.", ephemeral=True)
                return
            data = await response.json()

        async with self.session.get('https://api.blockchair.com/bitcoin/stats') as price_response:
            if price_response.status != 200:
                await interaction.followup.send("Failed to fetch price data.", ephemeral=True)
                return
            price_data = await price_response.json()

        if 'data' not in data or address not in data['data']:
            await interaction.followup.send("Invalid Bitcoin address.", ephemeral=True)
            return

        btc_usd_rate = price_data['data']['market_price_usd']
        address_data = data['data'][address]
        address_info = address_data['address']

        type = address_info['type']
        balance = address_info['balance'] / 1e8
        balance_usd = balance * btc_usd_rate
        received = address_info['received'] / 1e8
        received_usd = received * btc_usd_rate
        spent = address_info['spent'] / 1e8
        spent_usd = spent * btc_usd_rate

        first_appearance_str = address_info.get('first_seen_receiving')
        if first_appearance_str:
            first_appearance_dt = datetime.strptime(first_appearance_str, '%Y-%m-%d %H:%M:%S')
            first_appearance_timestamp = int(first_appearance_dt.timestamp())
            fad = datetime.utcfromtimestamp(first_appearance_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        else:
            fad = "never before"

        last_seen_str = address_info.get('last_seen_receiving')
        if last_seen_str:
            last_seen_dt = datetime.strptime(last_seen_str, '%Y-%m-%d %H:%M:%S')
            last_seen_timestamp = int(last_seen_dt.timestamp())
            lsd = datetime.utcfromtimestamp(last_seen_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            lsdf = f"• last seen {lsd}"
        else:
            lsdf = ""

        embed = await cembed(
            interaction,
            title="Bitcoin Address",
            url=f"https://blockchair.com/bitcoin/address/{address}",
            description=address
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar)

        embed.add_field(
            name="Funds",
            value=(
                f"* Type: **`{type}`**\n"
                f"* Balance: **`{balance:.8f}`** BTC (**{balance_usd:.2f}** USD)\n"
                f"* Received: **`{received:.8f}`** BTC (**{received_usd:.2f}** USD)\n"
                f"* Spent: **`{spent:.8f}`** BTC (**{spent_usd:.2f}** USD)"
            ),
            inline=False
        )

        embed.set_footer(text=f"first seen {fad} {lsdf}")
        embed.set_thumbnail(url="https://git.cursi.ng/bitcoin.png?")

        await interaction.followup.send(embed=embed)

    @ethereum.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(address="Ethereum address.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def address(self, interaction: Interaction, address: str):
        "Lookup an Ethereum address."
        def eth_validity(address: str) -> bool:
            if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
                return False
            
            try:
                checksum_address = to_checksum_address(address)
                return checksum_address == address
            except ValueError:
                return False

        if not eth_validity(address):
            await interaction.followup.send("Invalid Ethereum address format.", ephemeral=True)
            return

        async with self.session.get(f'https://api.blockchair.com/ethereum/dashboards/address/{address}?key=G___pLdUH6Zkg9YlUDbuIENcdfbbKF8l') as response:
            if response.status != 200:
                await interaction.followup.send("Failed to fetch address data.", ephemeral=True)
                return
            data = await response.json()

        async with self.session.get('https://api.blockchair.com/ethereum/stats') as price_response:
            if price_response.status != 200:
                await interaction.followup.send("Failed to fetch price data.", ephemeral=True)
                return
            price_data = await price_response.json()

        if 'data' not in data or address not in data['data']:
            await interaction.followup.send("Invalid Ethereum address.", ephemeral=True)
            return

        eth_usd_rate = price_data['data']['market_price_usd']
        address_data = data['data'][address]
        address_info = data['data'][address]['address']

        received = float(address_info.get('received_approximate', 0)) / 1e18
        received_usd = received * eth_usd_rate
        spent = float(address_info.get('spent_approximate', 0)) / 1e18
        spent_usd = spent * eth_usd_rate
        balance = float(address_info.get('balance', 0)) / 1e18
        balance_usd = balance * eth_usd_rate

        first_appearance_str = address_info.get('first_seen_receiving')
        if first_appearance_str:
            first_appearance_dt = datetime.strptime(first_appearance_str, '%Y-%m-%d %H:%M:%S')
            first_appearance_timestamp = int(first_appearance_dt.timestamp())
            fad = datetime.utcfromtimestamp(first_appearance_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        else:
            fad = "never before"

        last_seen_str = address_info.get('last_seen_receiving')
        if last_seen_str:
            last_seen_dt = datetime.strptime(last_seen_str, '%Y-%m-%d %H:%M:%S')
            last_seen_timestamp = int(last_seen_dt.timestamp())
            lsd = datetime.utcfromtimestamp(last_seen_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            lsdf = f"• last seen {lsd}"
        else:
            lsdf = ""

        calls = data['data'][address].get('calls', [])
        last_transaction = None

        for call in calls:
            if call.get('recipient', '').lower() == address.lower():
                value = float(call.get('value', 0))
                if value > 0:
                    last_transaction = {
                        'type': 'Received',
                        'amount': value / 1e18,
                        'amount_usd': (value / 1e18) * eth_usd_rate,
                        'recipient': address,
                        'tx_hash': call['transaction_hash']
                    }
                    break
            elif call.get('sender', '').lower() == address.lower():
                value = float(call.get('value', 0))
                if value > 0:
                    last_transaction = {
                        'type': 'Sent',
                        'amount': value / 1e18,
                        'amount_usd': (value / 1e18) * eth_usd_rate,
                        'recipient': call.get('recipient', 'Unknown'),
                        'tx_hash': call['transaction_hash']
                    }
                    break

        embed = await cembed(
            interaction,
            title="Ethereum Address",
            url=f"https://blockchair.com/ethereum/address/{address}",
            description=address
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar)

        embed.add_field(
            name="Funds",
            value=(
                f"* Balance: **`{balance:.8f}`** ETH (**{balance_usd:.2f}** USD)\n"
                f"* Received: **`{received:.8f}`** ETH (**{received_usd:.2f}** USD)\n"
                f"* Spent: **`{spent:.8f}`** ETH (**{spent_usd:.2f}** USD)"
            ),
            inline=False
        )

        if last_transaction:
            embed.add_field(
                name="Last Transaction",
                value=(
                    f"{last_transaction['type']} [{last_transaction['amount']:.8f}](https://blockchair.com/ethereum/transaction/{last_transaction['tx_hash']}) "
                    f"ETH (**{last_transaction['amount_usd']:.2f}** USD)"
                ),
                inline=False
            )
        else:
            embed.add_field(
                name="Last Transaction",
                value="No recent transactions found. (lol)",
                inline=False
            )

        embed.set_footer(text=f"first seen {fad} {lsdf}")
        embed.set_thumbnail(url="https://git.cursi.ng/ethereum.png?")

        await interaction.followup.send(embed=embed)

    @litecoin.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(address="Litecoin address.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def address(self, interaction: Interaction, address: str):
        "Lookup a Litecoin address."

        def ltc_validity(address: str) -> bool:
            return bool(re.match(r'^(L|M|ltc1)[a-zA-Z0-9]{25,40}$', address))

        if not ltc_validity(address):
            await interaction.followup.send("Invalid Litecoin address format.", ephemeral=True)
            return

        async with self.session.get(f'https://api.blockchair.com/litecoin/dashboards/address/{address}?key=G___pLdUH6Zkg9YlUDbuIENcdfbbKF8l') as response:
            if response.status != 200:
                await interaction.followup.send("Failed to fetch address data.", ephemeral=True)
                return
            data = await response.json()

        async with self.session.get('https://api.blockchair.com/litecoin/stats') as price_response:
            if price_response.status != 200:
                await interaction.followup.send("Failed to fetch price data.", ephemeral=True)
                return
            price_data = await price_response.json()

        if 'data' not in data or address not in data['data']:
            await interaction.followup.send("Invalid Litecoin address.", ephemeral=True)
            return

        ltc_usd_rate = price_data['data']['market_price_usd']
        address_data = data['data'][address]
        address_info = address_data['address']

        balance = address_info['balance'] / 1e8
        balance_usd = balance * ltc_usd_rate
        received = address_info['received'] / 1e8
        received_usd = received * ltc_usd_rate
        spent = address_info['spent'] / 1e8
        spent_usd = spent * ltc_usd_rate

        first_appearance_str = address_info.get('first_seen_receiving')
        if first_appearance_str:
            first_appearance_dt = datetime.strptime(first_appearance_str, '%Y-%m-%d %H:%M:%S')
            first_appearance_timestamp = int(first_appearance_dt.timestamp())
            fad = datetime.utcfromtimestamp(first_appearance_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        else:
            fad = "Unknown"

        last_seen_str = address_info.get('last_seen_receiving')
        if last_seen_str:
            last_seen_dt = datetime.strptime(last_seen_str, '%Y-%m-%d %H:%M:%S')
            last_seen_timestamp = int(last_seen_dt.timestamp())
            lsd = datetime.utcfromtimestamp(last_seen_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            lsdf = f"• last seen {lsd}"
        else:
            lsdf = ""

        transactions = address_data.get('transactions', [])
        last_transaction = None

        if transactions:
            latest_tx_hash = transactions[0]
            print(latest_tx_hash)
            async with self.session.get(f'https://api.blockchair.com/litecoin/raw/transaction/{latest_tx_hash}?key={BLOCKCHAIR_KEY}') as tx_response:
                if tx_response.status == 200:
                    tx_data = await tx_response.json()
                    if 'data' in tx_data and latest_tx_hash in tx_data['data']:
                        transaction = tx_data['data'][latest_tx_hash]['decoded_raw_transaction']
                        
                        for output in transaction['vout']:
                            output_addresses = output.get('scriptPubKey', {}).get('addresses', [])
                            if any(addr == address for addr in output_addresses):
                                last_transaction = {
                                    'amount': output['value'],
                                    'amount_usd': output['value'] * ltc_usd_rate,
                                    'recipient': address,
                                    'tx_hash': latest_tx_hash
                                }
                                break

        embed = await cembed(
            interaction,
            title="Litecoin Address",
            url=f"https://blockchair.com/litecoin/address/{address}",
            description=address
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar)

        embed.add_field(
            name="Funds",
            value=(
                f"* Balance: **`{balance:.8f}`** LTC (**{balance_usd:.2f}** USD)\n"
                f"* Received: **`{received:.8f}`** LTC (**{received_usd:.2f}** USD)\n"
                f"* Spent: **`{spent:.8f}`** LTC (**{spent_usd:.2f}** USD)"
            ),
            inline=False
        )

        if last_transaction:
            embed.add_field(
                name="Last Transaction",
                value=(
                    f"Received [{last_transaction['amount']:.8f}](https://blockchair.com/litecoin/transaction/{last_transaction['tx_hash']}) "
                    f"LTC (**{last_transaction['amount_usd']:.2f}** USD)"
                ),
                inline=False
            )
        else:
            embed.add_field(
                name="Last Transaction",
                value="No recent transactions found. (lol)",
                inline=False
            )

        embed.set_footer(text=f"first seen {fad} {lsdf}")
        embed.set_thumbnail(url="https://git.cursi.ng/litecoin.png?")

        await interaction.followup.send(embed=embed)

    @bitcoin.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def price(self, interaction: Interaction):
        """Get the current price of Bitcoin."""
        await interaction.response.defer(thinking=True)

        async with self.session.get('https://api.blockchair.com/bitcoin/stats') as response:
            if response.status != 200:
                await interaction.response.send_message("Failed to fetch price data.", ephemeral=True)
                return
            data = await response.json()

        btc = data['data']['market_price_usd']

        if btc == int(btc):
            btcf = f"{int(btc):,}"
        else:
            btcf = f"{btc:,.2f}".rstrip('0').rstrip('.')

        await interaction.followup.send(f"<:btc:1317320391672332411> is currently valued at **`{btcf}`** USD.")

    @ethereum.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def price(self, interaction: Interaction):
        """Get the current price of Ethereum."""
        await interaction.response.defer(thinking=True)

        async with self.session.get('https://api.blockchair.com/ethereum/stats') as response:
            if response.status != 200:
                await interaction.response.send_message("Failed to fetch price data.", ephemeral=True)
                return
            data = await response.json()

        eth = data['data']['market_price_usd']

        if eth == int(eth):
            ethf = f"{int(eth):,}"
        else:
            ethf = f"{eth:,.2f}".rstrip('0').rstrip('.')

        await interaction.followup.send(f"<:eth:1317321708318752790> is currently valued at **`{ethf}`** USD.")

    @litecoin.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def price(self, interaction: Interaction):
        """Get the current price of Litecoin."""
        await interaction.response.defer(thinking=True)

        async with self.session.get('https://api.blockchair.com/litecoin/stats') as response:
            if response.status != 200:
                await interaction.response.send_message("Failed to fetch price data.", ephemeral=True)
                return
            data = await response.json()

        ltc = data['data']['market_price_usd']

        if ltc == int(ltc):
            ltcf = f"{int(ltc):,}"
        else:
            ltcf = f"{ltc:,.2f}".rstrip('0').rstrip('.')

        await interaction.followup.send(f"<:ltc:1317315167671025684> is currently valued at **`{ltcf}`** USD.")

    @base64.command()
    @app_commands.describe(string="The string to encode.")
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def encode(self, interaction: discord.Interaction, string: str):
        """Encode a string to Base64."""
        try:
            encoded_bytes = await asyncio.to_thread(base64.b64encode, string.encode("utf-8"))
            encoded_string = encoded_bytes.decode("utf-8")

            await interaction.response.send_message(f"{encoded_string}")
        except Exception as e:
            await error_handler(interaction, e)

    @base64.command()
    @app_commands.describe(string="The Base64 string to decode.")
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def decode(self, interaction: discord.Interaction, string: str):
        """Decode a Base64 string."""
        try:
            missing_padding = len(string) % 4
            if missing_padding:
                string += "=" * (4 - missing_padding)
            
            decoded_string = await asyncio.to_thread(base64.b64decode, string.encode("utf-8"))
            decoded_string = decoded_string.decode("utf-8")

            await interaction.response.send_message(f"{decoded_string}")
        except base64.binascii.Error:
            await interaction.response.send_message("Invalid Base64 input. Please check the string and try again.", ephemeral=True)
        except Exception as e:
            await error_handler(interaction, e)

    async def timezone_autocomplete(self, interaction: discord.Interaction, current: str):
        popular_timezones = [
            "Europe/Berlin",
            "Europe/Madrid",
            "Europe/Warsaw",
            "Europe/Bucharest",
            "Europe/Paris",
            "Europe/London",
            "Europe/Rome",
            "America/New_York",
            "America/Los_Angeles",
            "America/Chicago",
            "Asia/Shanghai",
            "Asia/Tokyo",
            "Asia/Dubai",
        ]

        country2capital = {
            "Afghanistan": "Asia/Kabul", "Albania": "Europe/Tirane", "Algeria": "Africa/Algiers", "Andorra": "Europe/Andorra",
            "Angola": "Africa/Luanda", "Antigua and Barbuda": "America/Antigua", "Argentina": "America/Argentina/Buenos_Aires",
            "Armenia": "Asia/Yerevan", "Australia": "Australia/Sydney", "Austria": "Europe/Vienna", "Azerbaijan": "Asia/Baku",
            "Bahamas": "America/Nassau", "Bahrain": "Asia/Bahrain", "Bangladesh": "Asia/Dhaka", "Barbados": "America/Barbados",
            "Belarus": "Europe/Minsk", "Belgium": "Europe/Brussels", "Belize": "America/Belize", "Benin": "Africa/Porto-Novo",
            "Bhutan": "Asia/Thimphu", "Bolivia": "America/La_Paz", "Bosnia and Herzegovina": "Europe/Sarajevo",
            "Botswana": "Africa/Gaborone", "Brazil": "America/Sao_Paulo", "Brunei": "Asia/Brunei", "Bulgaria": "Europe/Sofia",
            "Burkina Faso": "Africa/Ouagadougou", "Burundi": "Africa/Bujumbura", "Cabo Verde": "Atlantic/Cape_Verde",
            "Cambodia": "Asia/Phnom_Penh", "Cameroon": "Africa/Douala", "Canada": "America/Toronto",
            "Central African Republic": "Africa/Bangui", "Chad": "Africa/Ndjamena", "Chile": "America/Santiago",
            "China": "Asia/Shanghai", "Colombia": "America/Bogota", "Comoros": "Indian/Comoro", "Congo": "Africa/Brazzaville",
            "Costa Rica": "America/Costa_Rica", "Croatia": "Europe/Zagreb", "Cuba": "America/Havana", "Cyprus": "Asia/Nicosia",
            "Czech Republic": "Europe/Prague", "Denmark": "Europe/Copenhagen", "Djibouti": "Africa/Djibouti",
            "Dominica": "America/Dominica", "Dominican Republic": "America/Santo_Domingo", "Ecuador": "America/Guayaquil",
            "Egypt": "Africa/Cairo", "El Salvador": "America/El_Salvador", "Equatorial Guinea": "Africa/Malabo",
            "Eritrea": "Africa/Asmara", "Estonia": "Europe/Tallinn", "Eswatini": "Africa/Mbabane", "Ethiopia": "Africa/Addis_Ababa",
            "Fiji": "Pacific/Fiji", "Finland": "Europe/Helsinki", "France": "Europe/Paris", "Gabon": "Africa/Libreville",
            "Gambia": "Africa/Banjul", "Georgia": "Asia/Tbilisi", "Germany": "Europe/Berlin", "Ghana": "Africa/Accra",
            "Greece": "Europe/Athens", "Grenada": "America/Grenada", "Guatemala": "America/Guatemala", "Guinea": "Africa/Conakry",
            "Guinea-Bissau": "Africa/Bissau", "Guyana": "America/Guyana", "Haiti": "America/Port-au-Prince",
            "Honduras": "America/Tegucigalpa", "Hungary": "Europe/Budapest", "Iceland": "Atlantic/Reykjavik",
            "India": "Asia/Kolkata", "Indonesia": "Asia/Jakarta", "Iran": "Asia/Tehran", "Iraq": "Asia/Baghdad",
            "Ireland": "Europe/Dublin", "Israel": "Asia/Jerusalem", "Italy": "Europe/Rome", "Jamaica": "America/Jamaica",
            "Japan": "Asia/Tokyo", "Jordan": "Asia/Amman", "Kazakhstan": "Asia/Almaty", "Kenya": "Africa/Nairobi",
            "Kiribati": "Pacific/Tarawa", "Korea, North": "Asia/Pyongyang", "Korea, South": "Asia/Seoul", "Kosovo": "Europe/Belgrade",
            "Kuwait": "Asia/Kuwait", "Kyrgyzstan": "Asia/Bishkek", "Laos": "Asia/Vientiane", "Latvia": "Europe/Riga",
            "Lebanon": "Asia/Beirut", "Lesotho": "Africa/Maseru", "Liberia": "Africa/Monrovia", "Libya": "Africa/Tripoli",
            "Liechtenstein": "Europe/Vaduz", "Lithuania": "Europe/Vilnius", "Luxembourg": "Europe/Luxembourg",
            "Madagascar": "Indian/Antananarivo", "Malawi": "Africa/Blantyre", "Malaysia": "Asia/Kuala_Lumpur",
            "Maldives": "Indian/Maldives", "Mali": "Africa/Bamako", "Malta": "Europe/Malta", "Marshall Islands": "Pacific/Majuro",
            "Mauritania": "Africa/Nouakchott", "Mauritius": "Indian/Mauritius", "Mexico": "America/Mexico_City",
            "Micronesia": "Pacific/Pohnpei", "Moldova": "Europe/Chisinau", "Monaco": "Europe/Monaco", "Mongolia": "Asia/Ulaanbaatar",
            "Montenegro": "Europe/Podgorica", "Morocco": "Africa/Casablanca", "Mozambique": "Africa/Maputo", "Myanmar": "Asia/Yangon",
            "Namibia": "Africa/Windhoek", "Nauru": "Pacific/Nauru", "Nepal": "Asia/Kathmandu", "Netherlands": "Europe/Amsterdam",
            "New Zealand": "Pacific/Auckland", "Nicaragua": "America/Managua", "Niger": "Africa/Niamey", "Nigeria": "Africa/Lagos",
            "North Macedonia": "Europe/Skopje", "Norway": "Europe/Oslo", "Oman": "Asia/Muscat", "Pakistan": "Asia/Karachi",
            "Palau": "Pacific/Palau", "Panama": "America/Panama", "Papua New Guinea": "Pacific/Port_Moresby", "Paraguay": "America/Asuncion",
            "Peru": "America/Lima", "Philippines": "Asia/Manila", "Poland": "Europe/Warsaw", "Portugal": "Europe/Lisbon",
            "Qatar": "Asia/Qatar", "Romania": "Europe/Bucharest", "Russia": "Europe/Moscow", "Rwanda": "Africa/Kigali",
            "Saint Kitts and Nevis": "America/St_Kitts", "Saint Lucia": "America/St_Lucia", "Saint Vincent and the Grenadines": "America/St_Vincent",
            "Samoa": "Pacific/Apia", "San Marino": "Europe/San_Marino", "Sao Tome and Principe": "Africa/Sao_Tome", "Saudi Arabia": "Asia/Riyadh",
            "Senegal": "Africa/Dakar", "Serbia": "Europe/Belgrade", "Seychelles": "Indian/Mahe", "Sierra Leone": "Africa/Freetown",
            "Singapore": "Asia/Singapore", "Slovakia": "Europe/Bratislava", "Slovenia": "Europe/Ljubljana", "Solomon Islands": "Pacific/Guadalcanal",
            "Somalia": "Africa/Mogadishu", "South Africa": "Africa/Johannesburg", "South Sudan": "Africa/Juba", "Spain": "Europe/Madrid",
            "Sri Lanka": "Asia/Colombo", "Sudan": "Africa/Khartoum", "Suriname": "America/Paramaribo", "Sweden": "Europe/Stockholm",
            "Switzerland": "Europe/Zurich", "Syria": "Asia/Damascus", "Taiwan": "Asia/Taipei", "Tajikistan": "Asia/Dushanbe",
            "Tanzania": "Africa/Dar_es_Salaam", "Thailand": "Asia/Bangkok", "Timor-Leste": "Asia/Dili", "Togo": "Africa/Lome",
            "Tonga": "Pacific/Tongatapu", "Trinidad and Tobago": "America/Port_of_Spain", "Tunisia": "Africa/Tunis", "Turkey": "Europe/Istanbul",
            "Turkmenistan": "Asia/Ashgabat", "Tuvalu": "Pacific/Funafuti", "Uganda": "Africa/Kampala", "Ukraine": "Europe/Kiev",
            "United Arab Emirates": "Asia/Dubai", "United Kingdom": "Europe/London", "United States": "America/New_York", "Uruguay": "America/Montevideo",
            "Uzbekistan": "Asia/Tashkent", "Vanuatu": "Pacific/Efate", "Vatican City": "Europe/Vatican", "Venezuela": "America/Caracas",
            "Vietnam": "Asia/Ho_Chi_Minh", "Yemen": "Asia/Aden", "Zambia": "Africa/Lusaka", "Zimbabwe": "Africa/Harare"
        }

        if not current:
            return [app_commands.Choice(name=tz, value=tz) for tz in sorted(popular_timezones)]

        all_timezones = pytz.all_timezones
        filtered_timezones = [tz for tz in all_timezones if current.lower() in tz.lower()]

        country_matches = [country for country in country2capital.keys() if current.lower() in country.lower()]
        for country in country_matches:
            capital_timezone = country2capital[country]
            if capital_timezone not in filtered_timezones:
                filtered_timezones.append(capital_timezone)

        return [app_commands.Choice(name=tz, value=tz) for tz in sorted(filtered_timezones)[:25]]

    @timezone.command()
    @app_commands.describe(
        timezone="The timezone to get the current time for.",
        user="The user to check the timezone for."
    )
    @app_commands.autocomplete(timezone=timezone_autocomplete)
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def view(self, interaction: discord.Interaction, timezone: str = None, user: discord.User = None):
        """Get the current time in a specific region."""
        if timezone and user:
            await interaction.response.send_message(
                "You cannot specify both a timezone and a user at the same time.",
                ephemeral=True
            )
            return

        if timezone:
            try:
                tz = pytz.timezone(timezone)
                current_time = datetime.now(tz)
                
                formatted_time = current_time.strftime("%I:%M %p")
                formatted_date = current_time.strftime("%d %B, %Y")
                
                await interaction.response.send_message(
                    f"⌚ **{timezone}**: {formatted_time} ({formatted_date})"
                )
            except pytz.UnknownTimeZoneError:
                await interaction.response.send_message("Invalid timezone. Please try again.", ephemeral=True)
            except Exception as e:
                await error_handler(interaction, e)
        else:
            target_user_id = str(user.id) if user else str(interaction.user.id)
            async with get_db_connection() as conn:
                timezone = await conn.fetchval("SELECT timezone FROM settings WHERE user_id = $1", target_user_id)
                
                if timezone:
                    tz = pytz.timezone(timezone)
                    current_time = datetime.now(tz)
                    
                    formatted_time = current_time.strftime("%I:%M %p")
                    formatted_date = current_time.strftime("%d %B, %Y")
                    
                    username = user.display_name if user else interaction.user.display_name
                    await interaction.response.send_message(
                        f"⌚ **{timezone}**: {formatted_time} ({formatted_date})"
                    )
                else:
                    username = user.display_name if user else interaction.user.display_name
                    await interaction.response.send_message(
                        f"{username} doesn't have their timezone set.",
                        ephemeral=True
                    )

    @timezone.command()
    @app_commands.describe(timezone="The timezone to set for your profile.")
    @app_commands.autocomplete(timezone=timezone_autocomplete)
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def set(self, interaction: discord.Interaction, timezone: str):
        """Set your timezone."""
        try:
            tz = pytz.timezone(timezone)
            user_id = str(interaction.user.id)
            async with get_db_connection() as conn:
                await conn.execute("""
                    INSERT INTO settings (user_id, timezone)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id)
                    DO UPDATE SET timezone = EXCLUDED.timezone
                """, user_id, timezone)
            await interaction.response.send_message(f"Your timezone has been set to **{timezone}**.", ephemeral=True)
        except pytz.UnknownTimeZoneError:
            await interaction.response.send_message("Invalid timezone. Please try again.", ephemeral=True)
        except Exception as e:
            await error_handler(interaction, e)

    def format_time(self, delta):
        seconds = int(delta.total_seconds())
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)

        time_str = []
        if days > 0:
            time_str.append(f"{days} day{'s' if days > 1 else ''}")
        if hours > 0:
            time_str.append(f"{hours} hour{'s' if hours > 1 else ''}")
        if minutes > 0:
            time_str.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
        if seconds > 0:
            time_str.append(f"{seconds} second{'s' if seconds > 1 else ''}")

        return ' '.join(time_str)

    async def store_deleted_message(self, channel_id, message):
        key = f"snipe:{channel_id}"
        message_data = {
            'author': message.author.name,
            'author_avatar': str(message.author.display_avatar.url),
            'content': message.content,
            'timestamp': datetime.utcnow().isoformat()
        }
        await redis_client.rpush(key, json.dumps(message_data))
        await redis_client.expire(key, 36000)
        length = await redis_client.llen(key)
        if length > 30:
            await redis_client.lpop(key)

    async def get_deleted_messages(self, channel_id):
        key = f"snipe:{channel_id}"
        messages = await redis_client.lrange(key, 0, -1)
        return [json.loads(msg) for msg in messages]

    # @commands.Cog.listener()
    # async def on_message_delete(self, message):
    #     await self.store_deleted_message(message.channel.id, message)

    # @commands.command(name='snipe', aliases=['s'])
    # @commands.bot_has_permissions(embed_links=True)
    # async def snipe(self, ctx, index: int = 1):
    #     index -= 1
    #     deleted_messages = await self.get_deleted_messages(ctx.channel.id)
    #     if 0 <= index < len(deleted_messages):
    #         message = deleted_messages[-(index + 1)]
    #         author = message['author']
    #         author_avatar = message['author_avatar']
    #         content = message['content'][:500] + ('...' if len(message['content']) > 500 else '')
    #         timestamp = datetime.fromisoformat(message['timestamp'])
    #         time_diff = datetime.utcnow() - timestamp

    #         if time_diff.days > 0:
    #             time_str = f"{time_diff.days} {'day' if time_diff.days == 1 else 'days'} ago"
    #         elif time_diff.seconds >= 3600:
    #             hours = time_diff.seconds // 3600
    #             time_str = f"{hours} {'hour' if hours == 1 else 'hours'} ago"
    #         elif time_diff.seconds >= 60:
    #             minutes = time_diff.seconds // 60
    #             time_str = f"{minutes} {'minute' if minutes == 1 else 'minutes'} ago"
    #         else:
    #             time_str = f"{time_diff.seconds} {'second' if time_diff.seconds == 1 else 'seconds'} ago"

    #         user_id = str(ctx.author.id)
    #         embed_color = await get_embed_color(user_id)
    #         embed = discord.Embed(
    #             description=content,
    #             color=embed_color
    #         )
    #         embed.set_author(name=author, icon_url=author_avatar)
    #         embed.set_footer(text=f"Deleted {time_str} ∙ {index + 1}/{len(deleted_messages)} messages", icon_url=ctx.author.display_avatar.url)
    #         await ctx.send(embed=embed)
    #     else:
    #         await ctx.send("No message to snipe.")

    async def clear_snipe_history(self, channel_id):
        key = f"snipe:{channel_id}"
        count = await redis_client.llen(key)
        await redis_client.delete(key)
        return count

    # @commands.command(name='clearsnipe', aliases=['cs'])
    # @commands.has_permissions(manage_messages=True)
    # async def clearsnipe(self, ctx):
    #     count = await self.clear_snipe_history(ctx.channel.id)
    #     if count > 0:
    #         await ctx.send(f"<a:vericheckg:1301736918794371094> {ctx.author.mention}: Cleared {count} snipe{'s' if count != 1 else ''}.")
    #     else:
    #         await ctx.send(f"<:denied:1301737566264889364> {ctx.author.mention}: No snipes to clear.")

    def generate_usage(self, command, parent_path=""):
        if isinstance(command, app_commands.Group):
            return "Group"

        signature = inspect.signature(command.callback)
        usage_parts = []

        for param in signature.parameters.values():
            if param.name in ['self', 'interaction']:
                continue

            if param.default is param.empty:
                usage_parts.append(f"<{param.name}>")
            else:
                usage_parts.append(f"[{param.name}]")

        full_path = f"{parent_path} {command.name}" if parent_path else command.name
        return f"/{full_path.strip()} {' '.join(usage_parts)}"

    def get_commands_in_cog(self, cog_name: str):
        cog = self.client.get_cog(cog_name)
        if cog:
            commands = []
            for cmd in cog.__cog_app_commands__:
                commands.append(cmd)
                if isinstance(cmd, app_commands.Group):
                    commands.extend(cmd.commands)
            return commands
        return []

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.check(permissions.is_blacklisted)
    @app_commands.check(permissions.is_owner)
    async def dump(self, interaction: Interaction):
        "Strictly for testing purposes."
        await interaction.response.defer(thinking=True)

        all_commands = {}

        for cog_name in self.client.cogs:
            commands = self.get_commands_in_cog(cog_name)
            for cmd in commands:
                if cmd.name == "dump":
                    continue

                if cmd.parent is not None:
                    continue

                command_data = {
                    "name": cmd.name,
                    "description": cmd.description or "No description provided",
                    "usage": self.generate_usage(cmd),
                    "category": cog_name
                }

                if isinstance(cmd, app_commands.Group):
                    all_commands[cmd.name] = self.process_group(cmd, cog_name)
                else:
                    all_commands[cmd.name] = command_data

        commands_json_str = json.dumps(all_commands, indent=4)

        try:
            file = File(io.StringIO(commands_json_str), filename="commands.json")
            await interaction.followup.send("Here are the commands in JSON format:", file=file)
        except Exception as e:
            await interaction.followup.send(f"Error displaying commands: {str(e)}")

    def process_group(self, group, category):
        group_details = {
            "name": group.name,
            "description": group.description or "No description provided",
            "usage": "Group",
            "category": category,
            "subcommands": []
        }

        for subcmd in group.commands:
            subcmd_data = {
                "name": subcmd.name,
                "description": subcmd.description or "No description provided",
                "usage": self.generate_usage(subcmd, group.name),
                "category": category
            }
            if isinstance(subcmd, app_commands.Group):
                subcmd_data["subcommands"] = self.process_group(subcmd, category)["subcommands"]
            group_details["subcommands"].append(subcmd_data)

        return group_details

    async def search_autocomplete(self, interaction: Interaction, current: str):
        if not current:
            return []

        loop = asyncio.get_event_loop()
        try:
            search_results = await loop.run_in_executor(None, lambda: Search(current).results[:5])
        except Exception as e:
            print(f"Error fetching search results: {e}")
            return []

        return [
            app_commands.Choice(name=video.title, value=video.watch_url)
            for video in search_results
        ]

    async def get_video_info(self, video_id: str):
        url = f"http://37.114.46.135:3341/yt/v={video_id}"
        async with self.session.get(url) as response:
            return await response.json()

    @convert.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(query="Search query or video URL.")
    @app_commands.autocomplete(query=search_autocomplete)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def youtube2mp3(self, interaction: discord.Interaction, query: str):
        "Convert a YouTube video to MP3."

        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            try:
                if "youtube.com/watch?v=" in query or "youtu.be/" in query:
                    video_id = query.split("v=")[-1].split("&")[0]
                else:
                    search_results = await asyncio.to_thread(lambda: Search(query).results)
                    if not search_results:
                        await interaction.followup.send("No videos found.")
                        return
                    video_id = search_results[0].watch_url.split("v=")[-1]

                video_info = await self.get_video_info(video_id)
                yt_title = video_info["title"]
                yt_length = video_info["length"]
                yt_stream_url = video_info["streams"][0]["url"] 

                if yt_length > 600:
                    await interaction.followup.send(f"The video is longer than 10 minutes, cannot send audio. [Direct audio download]({yt_stream_url}).")
                    return

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                async with self.session.get(yt_stream_url, headers=headers) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                    else:
                        await interaction.followup.send(f"Could not send audio. [Direct audio download]({yt_stream_url}).")
                        return

                output_mp3 = io.BytesIO()
                ffmpeg_command = [
                    "ffmpeg",
                    "-i", "pipe:0",
                    "-vn",
                    "-acodec", "libmp3lame",
                    "-preset", "ultrafast",
                    "-threads", "0",
                    "-ab", "192k",
                    "-ar", "44100",
                    "-f", "mp3",
                    "pipe:1"
                ]

                process = await asyncio.create_subprocess_exec(
                    *ffmpeg_command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await asyncio.wait_for(process.communicate(input=audio_data), timeout=60)

                if process.returncode == 0:
                    output_mp3.write(stdout)
                    output_mp3.seek(0)
                    safefilename = re.sub(r'[<>:"/\\|?*]', '', yt_title)
                    mp3_file = discord.File(output_mp3, filename=f"{safefilename}.mp3")
                    await interaction.followup.send(file=mp3_file)
                    break
                else:
                    retry_count += 1
                    if retry_count >= max_retries:
                        await interaction.followup.send("Error converting the audio file after multiple attempts.")
                        break

            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    await error_handler(interaction, e)
                    break
                continue

    @convert.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(query="Search query or video URL.")
    @app_commands.autocomplete(query=search_autocomplete)
    @app_commands.check(permissions.is_blacklisted)
    async def youtube2mp4(self, interaction: discord.Interaction, query: str):
        "Convert a YouTube video to MP4."
        await interaction.response.defer()

        if "/shorts/" in query:
            await interaction.followup.send("Detected a short. Use </youtube short:1291217502516416534> instead.")
            return

        try:
            if "youtube.com/watch?v=" in query or "youtu.be/" in query:
                video_id = query.split("v=")[-1].split("&")[0]
            else:
                search_results = await asyncio.to_thread(lambda: Search(query).results)
                if not search_results:
                    await interaction.followup.send("No videos found.")
                    return
                video_id = search_results[0].watch_url.split("v=")[-1]

            video_info = await self.get_video_info(video_id)
            download_url = video_info["streams"][1]["url"]
            
            await interaction.followup.send(f"Download [video](<{download_url}>).")

        except Exception as e:
            await error_handler(interaction, e)

    @convert.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user to get ID of, leave empty to get your own.")
    @app_commands.check(permissions.is_blacklisted)
    async def discorduser2id(self, interaction: discord.Interaction, user: discord.User = None):
        """Get the Discord ID of a user."""
        user = user or interaction.user
        await interaction.response.send_message(user.id)

    @get.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(style="Choose a style for the profile picture.")
    @app_commands.choices(style=[
        app_commands.Choice(name="Cat Pfp", value="cat pfp"),
        app_commands.Choice(name="Aesthetic Pfp", value="aesthetic pfp"),
        app_commands.Choice(name="Dark Pfp", value="dark pfp"),
        app_commands.Choice(name="Couple Pfp", value="couple pfp"),
        app_commands.Choice(name="Anime Pfp", value="anime pfp"),
        app_commands.Choice(name="Eboy Pfp", value="eboy pfp"),
        app_commands.Choice(name="Egirl Pfp", value="egirl pfp"),
        app_commands.Choice(name="Opiumcore Pfp", value="opiumcore pfp"),
        app_commands.Choice(name="Grunge Pfp", value="grunge pfp"),
        app_commands.Choice(name="Cartoon Pfp", value="cartoon pfp"),
        app_commands.Choice(name="Indie Pfp", value="indie pfp")
    ])
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def pfp(self, interaction: discord.Interaction, style: app_commands.Choice[str]):
        """Search for a profile picture."""
        try:            
            style_keywords = {
                "cat pfp": ["cat profile picture", "cute cat avatar", "cat aesthetic", "cat vibe", "kitten pfp", "cat icon", "kitty profile pic", "kitty pfp"],
                "aesthetic pfp": ["aesthetic profile picture", "minimalist avatar", "soft aesthetic", "aesthetic vibe", "pastel pfp", "vintage aesthetic", "aesthetic icon", "aesthetic profile pic"],
                "dark pfp": ["dark profile picture", "gothic avatar", "moody aesthetic", "dark vibe", "edgy pfp", "dark anime", "shadow pfp", "dark gothic", "emo pfp", "vampire aesthetic"],
                "couple pfp": ["couple profile picture", "matching avatars", "relationship aesthetic", "couple vibe", "love pfp", "romantic pfp", "couple icon", "couple type"],
                "anime pfp": ["anime profile picture", "anime avatar", "kawaii anime", "anime vibe", "anime girl pfp", "anime boy pfp", "anime icon", "anime type"],
                "egirl pfp": ["discord egirl profile picture", "discord egirl aesthetic", "discord pastel egirl", "discord egirl vibe", "discord egirl pfp", "discord egirl makeup", "discord egirl fashion", "discord egirl type"],
                "eboy pfp": ["discord eboy profile picture", "discord comboy", "discord eboy", "discord eboy vibe", "discord eboy pfp", "discord eboy fashion", "discord eboy profile pic", "discord eboy style"],
                "opiumcore pfp": ["opiumcore profile picture", "opiumcore aesthetic", "dark edgy avatar", "opiumcore vibe", "opiumcore icon", "opiumcore fashion", "opiumcore profile pic", "opiumcore mood"],
                "grunge pfp": ["grunge profile picture", "grunge aesthetic", "punk avatar", "grunge vibe", "grunge icon", "grunge fashion", "grunge profile pic", "grunge mood"],
                "cartoon pfp": ["cartoon profile picture", "cartoon avatar", "funny cartoon", "cartoon vibe", "cartoon icon", "cartoon type", "cartoon character", "cartoon style"],
                "indie pfp": ["indie profile picture", "indie aesthetic", "vintage avatar", "indie vibe", "indie icon", "indie type", "indie mood", "indie fashion"]
            }

            style_value = style.value
            keywords = style_keywords.get(style_value, [style_value])
            query = random.choice(keywords) + f" {random.randint(1, 100)}"

            image_urls = await self.client.socials.search_pinterest(query)

            if not image_urls:
                await interaction.followup.send(f"No profile pictures found for **{style_value}**.", ephemeral=True)
                return

            async def fetch_image(url):
                try:
                    async with self.session.get(url) as image_response:
                        if image_response.status == 200:
                            image_data = await image_response.read()
                            return (url, image_data, len(image_data))
                except Exception:
                    return None

            image_tasks = [fetch_image(url) for url in image_urls[:12]]
            images = await asyncio.gather(*image_tasks)
            images = [img for img in images if img is not None]

            if not images:
                await interaction.followup.send(f"No profile pictures found for **{style_value}**.", ephemeral=True)
                return

            images.sort(key=lambda x: x[2])
            
            total_size = 0
            MAX_SIZE = 10 * 1024 * 1024
            cutoff_index = 0
            
            for i, (url, data, size) in enumerate(images):
                if total_size + size > MAX_SIZE:
                    break
                total_size += size
                cutoff_index = i + 1
            
            filtered_images = images[:cutoff_index]
            
            if not filtered_images:
                await interaction.followup.send("The profile pictures found are too large to send.", ephemeral=True)
                return

            files = [discord.File(io.BytesIO(data), filename=f"pfp_{i+1}.png") 
                    for i, (url, data, size) in enumerate(filtered_images)]
            
            await interaction.followup.send(f"**{style_value}** (showing {len(files)} of {len(images)} images)", files=files)

        except Exception as e:
            await error_handler(interaction, e)

    @get.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(style="Choose a style for the banner.")
    @app_commands.choices(style=[
        app_commands.Choice(name="Cat Banner", value="cat banner"),
        app_commands.Choice(name="Aesthetic Banner", value="aesthetic banner"),
        app_commands.Choice(name="Dark Banner", value="dark banner"),
        app_commands.Choice(name="Couple Banner", value="couple banner"),
        app_commands.Choice(name="Anime Banner", value="anime banner"),
        app_commands.Choice(name="Eboy Banner", value="eboy banner"),
        app_commands.Choice(name="Egirl Banner", value="egirl banner"),
        app_commands.Choice(name="Opiumcore Banner", value="opiumcore banner"),
        app_commands.Choice(name="Grunge Banner", value="grunge banner"),
        app_commands.Choice(name="Cartoon Banner", value="cartoon banner"),
        app_commands.Choice(name="Indie Banner", value="indie banner")
    ])
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(attach_files=True)
    async def banner(self, interaction: discord.Interaction, style: app_commands.Choice[str]):
        """Search for a banner."""
        try:
            style_keywords = {
                "cat banner": ["cat banner", "cute cat banner", "cat aesthetic banner", "cat vibe banner", "kitten banner", "cat illustration banner", "cat type banner"],
                "aesthetic banner": ["aesthetic banner", "minimalist banner", "soft aesthetic banner", "aesthetic vibe banner", "pastel banner", "vintage aesthetic banner", "aesthetic wallpaper banner"],
                "dark banner": ["dark banner", "gothic banner", "moody aesthetic banner", "dark vibe banner", "edgy banner", "dark anime banner", "shadow banner", "dark gothic banner", "emo banner", "vampire aesthetic banner"],
                "couple banner": ["couple banner", "matching banners", "relationship aesthetic banner", "couple vibe banner", "love banner", "romantic banner", "couple type banner"],
                "anime banner": ["anime banner", "anime vibe banner", "kawaii anime banner", "anime girl banner", "anime boy banner", "anime type banner"],
                "egirl banner": ["discord egirl banner", "discord egirl aesthetic banner", "discord pastel egirl banner", "discord egirl vibe banner", "discord egirl fashion banner", "discord egirl type banner"],
                "eboy banner": ["discord eboy banner", "discord eboy aesthetic banner", "discord dark eboy banner", "discord eboy vibe banner", "discord eboy fashion banner", "discord eboy type banner"],
                "opiumcore banner": ["opiumcore banner", "opiumcore aesthetic banner", "dark edgy banner", "opiumcore vibe banner", "opiumcore fashion banner", "opiumcore drawing banner"],
                "grunge banner": ["grunge banner", "grunge aesthetic banner", "punk banner", "grunge vibe banner", "grunge fashion banner", "grunge type banner"],
                "cartoon banner": ["cartoon banner", "funny cartoon banner", "cartoon vibe banner", "cartoon character banner", "cartoon style banner"],
                "indie banner": ["indie banner", "indie aesthetic banner", "vintage banner", "indie vibe banner", "indie type banner", "indie fashion banner"]
            }

            style_value = style.value
            keywords = style_keywords.get(style_value, [style_value])
            query = random.choice(keywords) + f" {random.randint(1, 100)}"

            image_urls = await self.client.socials.search_pinterest(query)

            if not image_urls:
                await interaction.followup.send(f"No banners found for **{style_value}**.", ephemeral=True)
                return

            async def fetch_image(url):
                try:
                    async with self.session.get(url) as image_response:
                        if image_response.status == 200:
                            image_data = await image_response.read()
                            return (url, image_data, len(image_data))
                except Exception:
                    return None

            image_tasks = [fetch_image(url) for url in image_urls[:12]]
            images = await asyncio.gather(*image_tasks)
            images = [img for img in images if img is not None]

            if not images:
                await interaction.followup.send(f"No banners found for **{style_value}**.", ephemeral=True)
                return

            images.sort(key=lambda x: x[2])
            
            total_size = 0
            MAX_SIZE = 10 * 1024 * 1024
            cutoff_index = 0
            
            for i, (url, data, size) in enumerate(images):
                if total_size + size > MAX_SIZE:
                    break
                total_size += size
                cutoff_index = i + 1
            
            filtered_images = images[:cutoff_index]
            
            if not filtered_images:
                await interaction.followup.send("The banners found are too large to send.", ephemeral=True)
                return

            files = [discord.File(io.BytesIO(data), filename=f"banner_{i+1}.png") 
                    for i, (url, data, size) in enumerate(filtered_images)]
            
            await interaction.followup.send(f"**{style_value}** (showing {len(files)} of {len(images)} images)", files=files)

        except Exception as e:
            await error_handler(interaction, e)

    async def tag_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        user_id = interaction.user.id
        async with get_db_connection() as conn:
            rows = await conn.fetch(
                "SELECT tag_name FROM tags WHERE user_id = $1 AND tag_name ILIKE $2 LIMIT 25",
                user_id, f"%{current}%"
            )
        return [app_commands.Choice(name=row["tag_name"], value=row["tag_name"]) for row in rows]

    @tags.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(tag="The name of the tag.", text="The text to display on the tag.")
    @app_commands.check(permissions.is_blacklisted)
    async def create(self, interaction: discord.Interaction, tag: str, text: str):
        """Create a tag."""
        await interaction.response.defer(ephemeral=True)
        try:
            if len(tag) > 50 or len(text) > 2000:
                await interaction.followup.send("Tag name or text is too long. (Max: 50 chars for name, 2000 chars for text)", ephemeral=True)
                return
            
            text = text.replace(r'\n', '\n')

            user_id = interaction.user.id
            is_donor = await check_donor(interaction.user.id)
            max_tags = 20 if is_donor else 5
            
            async with get_db_connection() as conn:
                tag_count = await conn.fetchval("SELECT COUNT(*) FROM tags WHERE user_id = $1", user_id)
                
                if tag_count >= max_tags:
                    limit_msg = f"You have reached your tag limit ({max_tags}).\nUpgrade to Premium for up to 15 tags. </premium buy:1278389799857946700>" if not is_donor else f"You have reached your maximum tag limit ({max_tags})."
                    await interaction.followup.send(limit_msg, ephemeral=True)
                    return
                    
                cache_key = f"tags:{user_id}:{tag}"
                cached_tag = await redis_client.get(cache_key)
                
                if cached_tag:
                    await interaction.followup.send(f"Tag **{tag}** already exists.", ephemeral=True)
                    return

                try:
                    await conn.execute("INSERT INTO tags (user_id, tag_name, tag_text) VALUES ($1, $2, $3)", user_id, tag, text)
                    await redis_client.set(cache_key, text, ex=604800)
                    await interaction.followup.send(messages.success(interaction.user, f"Tag **{tag}** created successfully."), ephemeral=True)
                except Exception:
                    await interaction.followup.send(messages.warn(interaction.user, f"Tag **{tag}** already exists."), ephemeral=True)
        except Exception as e:
            await error_handler(interaction, e)

    @tags.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(tag="The name of the tag to send.")
    @app_commands.autocomplete(tag=tag_autocomplete)
    @app_commands.check(permissions.is_blacklisted)
    async def send(self, interaction: discord.Interaction, tag: str):
        """Send a tag."""
        await interaction.response.defer()
        try:
            user_id = interaction.user.id
            cache_key = f"tags:{user_id}:{tag}"

            cached_text = await redis_client.get(cache_key)
            if cached_text:
                await interaction.followup.send(cached_text)
                return

            async with get_db_connection() as conn:
                row = await conn.fetchrow(
                    "SELECT tag_text FROM tags WHERE user_id = $1 AND tag_name = $2",
                    user_id, tag
                )
                if not row:
                    await interaction.followup.send(f"Tag **{tag}** does not exist.", ephemeral=True)
                    return

                tag_text = row["tag_text"]
                await redis_client.set(cache_key, tag_text, ex=604800)
                await interaction.followup.send(tag_text)
        except Exception as e:
            await error_handler(interaction, e)

    @tags.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(tag="The name of the tag to delete.")
    @app_commands.autocomplete(tag=tag_autocomplete)
    @app_commands.check(permissions.is_blacklisted)
    async def delete(self, interaction: discord.Interaction, tag: str):
        """Delete a tag."""
        await interaction.response.defer(ephemeral=True)
        try:
            user_id = interaction.user.id
            cache_key = f"tags:{user_id}:{tag}"
            
            async with get_db_connection() as conn:
                result = await conn.execute(
                    "DELETE FROM tags WHERE user_id = $1 AND tag_name = $2",
                    user_id, tag
                )
                if result == "DELETE 0":
                    await interaction.followup.send(messages.warn(interaction.user, f"Tag **{tag}** does not exist."), ephemeral=True)
                    return

                await redis_client.delete(cache_key)
                await interaction.followup.send(messages.success(interaction.user, f"Tag **{tag}** deleted successfully."), ephemeral=True)
        except Exception as e:
            await error_handler(interaction, e)

    @tags.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(tag="The name of the tag to edit.")
    @app_commands.autocomplete(tag=tag_autocomplete)
    @app_commands.check(permissions.is_blacklisted)
    async def edit(self, interaction: discord.Interaction, tag: str):
        """Edit a tag."""
        class TagEditModal(Modal):
            def __init__(self, tag_name: str, tag_text: str):
                super().__init__(title=f"Edit Tag: {tag_name}")
                self.tag_name = tag_name

                self.text_input = TextInput(
                    label="Edit your tag text",
                    default=tag_text,
                    required=True,
                    max_length=2000,
                    style=discord.TextStyle.paragraph,
                )
                self.add_item(self.text_input)

            async def on_submit(self, interaction: discord.Interaction):
                tag_text = self.text_input.value
                user_id = interaction.user.id
                cache_key = f"tags:{user_id}:{self.tag_name}"

                async with get_db_connection() as conn:
                    await conn.execute(
                        "UPDATE tags SET tag_text = $1 WHERE user_id = $2 AND tag_name = $3",
                        tag_text, user_id, self.tag_name
                    )
                    await redis_client.set(cache_key, tag_text, ex=604800)

                await interaction.response.send_message(messages.success(interaction.user, f"Tag **{self.tag_name}** updated successfully!"), ephemeral=True)

        user_id = interaction.user.id

        async with get_db_connection() as conn:
            row = await conn.fetchrow(
                "SELECT tag_text FROM tags WHERE user_id = $1 AND tag_name = $2",
                user_id, tag
            )
            if not row:
                await interaction.response.send_message(messages.warn(interaction.user, f"Tag **{tag}** does not exist."), ephemeral=True)
                return

            tag_text = row["tag_text"]

        modal = TagEditModal(tag_name=tag, tag_text=tag_text)
        await interaction.response.send_modal(modal)

    @tags.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def list(self, interaction: discord.Interaction):
        """List all your tags."""
        await interaction.response.defer(ephemeral=True)
        try:
            user_id = interaction.user.id
            
            async with get_db_connection() as conn:
                rows = await conn.fetch(
                    "SELECT tag_name, tag_text FROM tags WHERE user_id = $1 ORDER BY tag_name",
                    user_id
                )
                
                if not rows:
                    await interaction.followup.send(messages.warn(interaction.user, "You don't have any tags."), ephemeral=True)
                    return
                
                is_donor = await check_donor(interaction.user.id)
                max_tags = 20 if is_donor else 5
                
                description = ""
                for row in rows:
                    tag_name = row["tag_name"]
                    tag_text = row["tag_text"]
                    
                    if len(tag_text) > 20:
                        tag_text = tag_text[:20] + "..."
                    
                    description += f"**{tag_name}** - {tag_text}\n"
                
                embed = await cembed(
                    interaction,
                    description=description,
                )
                
                embed.set_author(
                    name=f"{interaction.user.display_name}'s tags",
                    icon_url=interaction.user.display_avatar.url
                )
                
                embed.set_footer(text=f"Using {len(rows)}/{max_tags} tags" + (" (premium)" if is_donor else ""))
                
                await interaction.followup.send(embed=embed)
        except Exception as e:
            await error_handler(interaction, e)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(image="Upload an image or GIF to find its source.")
    @permissions.requires_perms(embed_links=True, attach_files=True)
    async def saucenao(self, interaction: discord.Interaction, image: discord.Attachment):
        """Find the sauce using SauceNAO."""
        if not image.content_type.startswith(("image/", "gif/")):
            await interaction.followup.send("Please upload an image or GIF.", ephemeral=True)
            return

        cached_result = await redis_client.get(image.url)
        if cached_result:
            results = json.loads(cached_result)
        else:
            api_url = "https://saucenao.com/search.php"
            params = {
                "output_type": 2,
                "api_key": SAUCENAO_KEY,
                "db": 999,
                "numres": 5,
                "url": image.url
            }
            async with self.session.get(api_url, params=params) as resp:
                if resp.status != 200:
                    await interaction.followup.send("Failed to fetch results from SauceNAO.", ephemeral=True)
                    return
                data = await resp.json()
                results = data.get("results", [])
                await redis_client.set(image.url, json.dumps(results), ex=600)

        if not results:
            await interaction.followup.send("No results found.", ephemeral=True)
            return

        embed = await cembed(interaction, title="Sauce Found?")
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        embed.set_thumbnail(url=image.url)
        embed.set_footer(text=f"SauceNAO • {footer}", icon_url="https://git.cursi.ng/saucenao_logo.png")

        description = ""
        for result in results[:5]:
            similarity = result["header"]["similarity"]
            data = result["data"]

            material_name = data.get("material") or data.get("source") or data.get("title") or data.get("eng_name") or result["header"].get("index_name", "Unknown")
            material_link = data.get("ext_urls", [None])[0]

            description += f"[**{material_name}**]({material_link}) • {similarity}% Similarity\n\n" if material_link else f"**{material_name}** • {similarity}% Similarity\n\n"

        embed.description = description
        await interaction.followup.send(embed=embed)

async def setup(client):
    await client.add_cog(Utility(client))
