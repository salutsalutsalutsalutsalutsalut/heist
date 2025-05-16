import discord
from discord import app_commands, Interaction, ui, SelectOption
from discord.ext import commands
from discord.ui import Select, View, Button
import psutil, subprocess, json, time
from utils.lines import count_lines_in_directory, get_loaded_modules
from utils.db import get_db_connection, check_donor, check_owner, check_booster, check_blacklisted
from utils.error import error_handler
from utils.embed import cembed
from utils import permissions
import urllib
from urllib.parse import urlparse
import asyncpg, aiohttp, asyncio, datetime, os, time, requests, io
from dotenv import dotenv_values
import ast
import operator
import platform

config = dotenv_values(".env")
API_KEY = config["HEIST_API_KEY"]
LASTFM_KEY = config["LASTFM_API_KEY"]

footer = "heist.lol"

class Info(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    premium = app_commands.Group(
        name="premium", 
        description="Premium related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
   )

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def invite(self, interaction: Interaction):
        """Authorize the bot."""
        invite = "https://discord.com/oauth2/authorize?client_id=1225070865935368265"
        view = discord.ui.View()
        button = discord.ui.Button(label="invite", url=invite, style=discord.ButtonStyle.link)
        view.add_item(button)
        await interaction.response.send_message(view=view)

    @app_commands.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def ping(self, interaction: Interaction):
        """See the bot's ping."""
        latency = round(self.client.latency * 1000)
        await interaction.response.send_message(f'Pong! Latency is `{latency}` ms.')

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

    def extract_command_details(self, command):
        details = {
            "name": command.name,
            "description": command.description or "No description",
            "parameters": []
        }

        if isinstance(command, app_commands.Command):
            for param in command.parameters:
                param_details = {
                    "name": param.name,
                    "description": param.description or "No description",
                    "required": param.required
                }
                details["parameters"].append(param_details)
        elif isinstance(command, app_commands.Group):
            details["description"] = "Command group, no parameters directly."
            for subcommand in command.commands:
                details["parameters"].append(self.extract_command_details(subcommand))

        return details

    # async def dump_commands(self):
    #     all_commands = {}

    #     for cog_name in self.client.cogs:
    #         commands = self.get_commands_in_cog(cog_name)
    #         all_commands[cog_name] = [self.extract_command_details(cmd) for cmd in commands]

    #     with open("dump.json", "w") as file:
    #         json.dump(all_commands, file, indent=4)

    #@app_commands.command()
    #@app_commands.allowed_installs(users=True)
    #@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    #@app_commands.check(permissions.is_tester)
    #@app_commands.check(permissions.is_blacklisted)
    # async def kencarsongyat(self, interaction: discord.Interaction):
    #     await self.dump_commands()
    #     try:
    #         await interaction.response.send_message("Commands have been dumped to `commands_dump.json`.")
    #     except Exception as e:
    #         print(e)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="Lookup Heist user by Discord ID.", uid="Lookup user by Heist UID.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def me(self, interaction: discord.Interaction, uid: str = None, user: discord.User = None):
        """View your own Heist information."""
        if uid and user:
            await interaction.followup.send("You cannot use both the UID and User parameters.")
            return

        if uid:
            if not uid.isdigit():
                await interaction.followup.send("The provided UID is not a valid integer.")
                return
            if uid == "0":
                uid = "1"
            async with get_db_connection() as conn:
                user_id = await conn.fetchval("SELECT user_id FROM user_data WHERE hid = $1", int(uid))
                if not user_id:
                    await interaction.followup.send("This HID does not belong to anyone.")
                    return
                try:
                    user = await interaction.client.fetch_user(int(user_id))
                except:
                    await interaction.followup.send("Could not fetch user information.")
                    return
        elif user:
            user_id = str(user.id)
            async with get_db_connection() as conn:
                hid = await conn.fetchval("SELECT hid FROM user_data WHERE user_id = $1", user_id)
                if not hid:
                    await interaction.followup.send("User is not in Heist's database. <:angry:1311402645780434994>")
                    return
        else:
            user = interaction.user
            user_id = str(user.id)

        user_name = user.name

        async with get_db_connection() as conn:
            user_exists = await conn.fetchval("SELECT 1 FROM user_data WHERE user_id = $1", user_id)
            if not user_exists:
                await conn.execute("INSERT INTO user_data (user_id) VALUES ($1)", user_id)

            hid = await conn.fetchval("SELECT hid FROM user_data WHERE user_id = $1", user_id)

            fame_status = await conn.fetchval("SELECT Fame FROM user_data WHERE user_id = $1", user_id)

            is_owner = await check_owner(user_id)
            is_donor = await check_donor(user_id)
            is_booster = await check_booster(user.id)
            is_blacklisted = await check_blacklisted(user_id)
            is_founder = user.id == 1363295564133040272

            lastfm_username = None
            lastfm_info = ""
            lastfm_state = None
            try:
                user_id_str = str(user.id)
                result = await conn.fetchrow("SELECT lastfm_username FROM lastfm_usernames WHERE user_id = $1", user_id_str)
                lastfm_username = result['lastfm_username'] if result else None

                visibility_result = await conn.fetchrow("SELECT lastfm_state FROM settings WHERE user_id = $1", user_id_str)
                lastfm_state = visibility_result['lastfm_state'] if visibility_result else 'Show'

                if lastfm_username:
                    api_key = LASTFM_KEY
                    recent_tracks_url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={lastfm_username}&api_key={api_key}&format=json"

                    async with self.session.get(recent_tracks_url) as recent_tracks_response:
                        if recent_tracks_response.status == 200:
                            tracks = (await recent_tracks_response.json())['recenttracks'].get('track', [])

                            if tracks:
                                track = tracks[0]
                                is_now_playing = '@attr' in track and 'nowplaying' in track['@attr'] and track['@attr']['nowplaying'] == 'true'
                                artist_name = track['artist']['#text']
                                track_name = track['name']

                                artistenc = urllib.parse.quote(artist_name)
                                trackenc = urllib.parse.quote(track_name)

                                spotify_url = f"http://127.0.0.1:2053/api/search?lastfm_username={lastfm_username}&track_name={trackenc}&artist_name={artistenc}"
                                headers = {"X-API-Key": f"{API_KEY}"}

                                if is_now_playing:
                                    async with self.session.get(spotify_url, headers=headers) as spotify_response:
                                        if spotify_response.status == 200:
                                            spotify_data = await spotify_response.json()
                                            spotify_track_url = spotify_data.get('spotify_link')

                                            if spotify_track_url:
                                                status = "<:lastfm:1275185763574874134>"
                                                if lastfm_state == 'Show':
                                                    lastfm_info = f"{status} ***[{track_name}]({spotify_track_url})*** ([@{lastfm_username}](https://www.last.fm/user/{lastfm_username}))\n\n" if is_now_playing else f"{status} ***{track_name}***\n\n"
                                                else:
                                                    lastfm_info = f"{status} ***[{track_name}]({spotify_track_url})***\n\n" if is_now_playing else f"{status} ***{track_name}***\n\n"
                                            else:
                                                if lastfm_state == 'Show':
                                                    lastfm_info = f"{status} ***{track_name}*** ([@{lastfm_username}](https://www.last.fm/user/{lastfm_username}))\n\n"
                                                else:
                                                    lastfm_info = f"{status} ***{track_name}***\n\n"
                                        else:
                                            if lastfm_state == 'Show':
                                                lastfm_info = f"{status} ***{track_name}*** ([@{lastfm_username}](https://www.last.fm/user/{lastfm_username}))\n\n"
                                            else:
                                                lastfm_info = f"{status} ***{track_name}***\n\n"
                                else:
                                    if lastfm_state == 'Show':
                                        lastfm_info = f"<:lastfm:1275185763574874134> [@{lastfm_username}](https://www.last.fm/user/{lastfm_username})\n\n"
                                    else:
                                        lastfm_info = ""
                        elif recent_tracks_response.status == 404:
                            lastfm_info = ""
                        else:
                            lastfm_info = ""
                else:
                    lastfm_info = ""
            except Exception as e:
                print(f"Exception: {e}")
                lastfm_info = ""

        if is_blacklisted:
            status_string = "<:bl1:1263853643216584764><:bl2:1263853966618394724><:bl3:1263854236601552907><:bl4:1263854052559552555><:bl5:1263854267228356731>"
        else:
            statuses = []
            if is_owner:
                if is_founder:
                    statuses.append("<a:heistowner:1343768654357205105> **`Heist Owner`**")
                else:
                    statuses.append("<:hstaff:1311070369829883925> **`Heist Admin`**")
            if fame_status:
                statuses.append("<:famous:1311067416251596870> **`Famous`**")
            if is_booster:
                statuses.append("<:boosts:1263854701535821855> **`Booster`**")
            if is_donor:
                statuses.append("<:premium:1311062205650833509> **`Premium`**")
            if not is_donor:
                statuses.append("<:heist:1273999266154811392> **`Standard`**")

            status_string = ", ".join(statuses)

        embed = await cembed(
            interaction,
            description=lastfm_info + status_string
        )
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        embed.set_author(name=f"{user_name} ; uid {hid}", icon_url=user.avatar.url if user.avatar else user.default_avatar.url)
        embed.set_footer(
            text=f"heist.lol • {user.id}",
            icon_url="https://git.cursi.ng/heist.png?"
        )

        try:
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await error_handler(interaction, e)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def about(self, interaction: discord.Interaction):
        """About the bot."""
        process = await asyncio.to_thread(psutil.Process)
        ram_usage = await asyncio.to_thread(lambda: process.memory_full_info().rss / 1024**2)
        cpu_usage = await asyncio.to_thread(psutil.cpu_percent)
        
        if interaction.client.start_time:
            bot_start_time = int(interaction.client.start_time.timestamp())
        else:
            bot_start_time = None

        latency = round(self.client.latency * 1000)
        
        #command_count = sum(1 for _ in self.client.walk_commands())
        cog_count = len(self.client.cogs)
        python_version = await asyncio.to_thread(platform.python_version)
        
        embed = await cembed(interaction)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        
        embed.description = f"> A multipurpose all-in-one, feature-rich Discord App that aims to enhance your chatting experience.\n-# Instance started **<t:{bot_start_time}:R>**\n"
        
        embed.set_thumbnail(url="https://git.cursi.ng/heistbig.png?")

        try:
            async with self.session.get('http://127.0.0.1:5002/getcount') as response:
                if response.status == 200:
                    stats = await response.json()
                    
                    install_count = stats['discord_user_install_count']
                    user_count = stats['user_count']
                    premium_count = stats['premium_count']
                    
                    embed.add_field(
                        name="Client",
                        value=(
                            f"> **Users:** `{user_count:,}`\n"
                            f"> **Installs:** `{install_count:,}`\n"
                            f"> **Guilds:** `{len(self.client.guilds):,}`\n"
                            f"> **Latency:** `{latency} ms`"
                        ),
                        inline=True
                    )
                else:
                    embed.add_field(name="Client", value="*Unable to fetch stats*", inline=True)
        except Exception as e:
            embed.add_field(name="Client", value="*Unable to fetch stats*", inline=True)

        embed.add_field(
            name="System",
            value=(
                f"> **Python:** `{python_version}`\n"
                f"> **CPU:** `{cpu_usage:.1f}%`\n"
                f"> **Memory:** `{ram_usage:.2f} MB`\n"
                f"> **Cogs:** `{cog_count}`"
            ),
            inline=True
        )

        embed.set_footer(text=f"{footer} • discord.gg/heistbot", icon_url="https://git.cursi.ng/heist.png")

        contributors_embed = await cembed(interaction, title="Heist's Team")
        contributors_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        contributors_embed.description = (
            "**Owner**\n"
            "[cosmin](discord://-/users/1363295564133040272): [website](https://cursi.ng), [github](https://github.com/csynholic)\n"
            "**Admin**\n"
            "[hyqos](discord://-/users/465244029475487746): [website](https://guns.lol/hyqos)\n"
            "**Contributors**\n"
            "[lane](discord://-/users/1148257561120878632): [website](https://lane.rest/)\n"
            "[crxa](discord://-/users/920290194886914069): [website](https://crxaw.tech/), [github](https://github.com/sitescript)"
        )
        contributors_embed.set_thumbnail(url="https://git.cursi.ng/heistbig.png?")
        contributors_embed.set_footer(text=f"{footer} • discord.gg/heistbot", icon_url="https://git.cursi.ng/heist.png")

        class AboutView(View):
            def __init__(self):
                super().__init__(timeout=120)
                self.current_embed = embed
                self.contributors_button = Button(label="Team", emoji="<:folder:1339024522007019581>")
                self.contributors_button.callback = self.toggle_embed

                self.authorize_button = Button(label="Authorize Heist", url="https://discord.com/oauth2/authorize?client_id=1225070865935368265", emoji="<:wave:1299179326146609192>")
                self.support_button = Button(label="Support", url="https://discord.gg/6ScZFN3wPA", emoji="<:support:1362140985261297904>")
                self.add_item(self.authorize_button)
                self.add_item(self.support_button)
                self.add_item(self.contributors_button)

            async def toggle_embed(self, interaction: discord.Interaction):
                if self.current_embed == embed:
                    self.current_embed = contributors_embed
                    self.contributors_button.label = "Bot Info"
                else:
                    self.current_embed = embed
                    self.contributors_button.label = "Team"
                await interaction.response.edit_message(embed=self.current_embed, view=self)

            async def on_timeout(self):
                for item in self.children:
                    if isinstance(item, Button) and item.style != discord.ButtonStyle.link:
                        item.disabled = True
                await interaction.edit_original_response(view=self)

        view = AboutView()
        try:
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()
        except Exception as e:
            await error_handler(interaction, e)

    @app_commands.command()
    @app_commands.allowed_installs(users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.check(permissions.is_owner)
    @app_commands.check(permissions.is_blacklisted)
    async def servers(self, interaction: Interaction):
        "Server list for Heist."
        guilds = await asyncio.to_thread(lambda: sorted(self.client.guilds, key=lambda g: g.member_count, reverse=True))
        total_guilds = await asyncio.to_thread(len, guilds)
        response = f"Heist Server List ({total_guilds} total):\n\n"

        for guild in guilds:
            vanity_url = getattr(guild, 'vanity_url', None)
            if vanity_url:
                parsed_url = await asyncio.to_thread(urlparse, vanity_url)
                vanity_code = await asyncio.to_thread(lambda: parsed_url.path.lstrip('/'))
                vanity_url_display = f"/{vanity_code}"
            else:
                vanity_url_display = 'None'
            response += f"{guild.name} (ID: {guild.id}) - Members: {guild.member_count} - Vanity URL: {vanity_url_display}\n"

        file = io.StringIO(response)
        file.seek(0)

        await interaction.response.send_message(
            file=discord.File(file, 'server_info.txt')
        )

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.check(permissions.is_blacklisted)
    async def commandcount(self, interaction: discord.Interaction):
        """Heist command count."""
        commands = await asyncio.to_thread(len, self.client.tree.get_commands())
        
        context_menu_items = await asyncio.to_thread(
            lambda: len([cmd for cmd in self.client.tree.get_commands() if isinstance(cmd, app_commands.ContextMenu)])
        )
        
        embed = await cembed(interaction, title="Heist Command Count")
        embed.add_field(name="Commands", value=commands, inline=True)
        embed.add_field(name="Context Menu Items", value=context_menu_items, inline=True)
        embed.set_footer(text=footer, icon_url="https://git.cursi.ng/heist.png")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="Learn how to use the bot.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def help(self, interaction: Interaction):
        """Learn how to use the bot."""
        embed = await cembed(
            interaction,
            description="[Commands](https://heist.lol/commands) • [Premium](https://heist.lol/premium) • [Support](https://discord.gg/6ScZFN3wPA)\n\n-# You can use </settings:1278389799681527967> to manage your personal settings.",
        )
        embed.set_author(name=self.client.user.name, icon_url="https://git.cursi.ng/heist.png?c")
        embed.set_thumbnail(url=self.client.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def pm2(self, interaction: Interaction):
        """Displays all PM2 services running and their stats."""
        try:
            process = await asyncio.create_subprocess_exec(
                'pm2', 'jlist',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return await interaction.response.send_message(f"Error: Unable to retrieve PM2 services. {stderr.decode()}")

            pm2_processes = json.loads(stdout.decode())

            if not pm2_processes:
                return await interaction.response.send_message("No PM2 services running.")

            current_time = time.time()
            embed = await cembed(interaction, title="PM2 stats")
            embed.set_author(name=f"{interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)

            for process in pm2_processes:
                name = process['name']
                cpu = process['monit']['cpu']
                memory = process['monit']['memory'] / (1024 * 1024)
                start_time = process['pm2_env'].get('created_at')
                if start_time is not None:
                    start_time = start_time / 1000
                    uptime_seconds = current_time - start_time
                    uptime_minutes = uptime_seconds / 60  
                else:
                    uptime_minutes = 0

                embed.add_field(name=name, value=f"**Uptime**: {uptime_minutes:.2f}min \n**CPU**: {cpu}%\n**RAM**: {memory:.2f} MB", inline=True)

            embed.set_footer(text=footer, icon_url="https://git.cursi.ng/heist.png")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await error_handler(interaction, e)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def support(self, interaction: Interaction):
        """The bot's support Discord server."""
        await interaction.response.send_message("[Join server](https://discord.gg/6ScZFN3wPA)", ephemeral=True)

    @premium.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def perks(self, interaction: Interaction):
        "Discover the perks of Heist Premium."
        is_donor = await check_donor(interaction.user.id)
        embed_color = 0xfbab74
        class PremiumView(View):
            def __init__(self, user: discord.User):
                super().__init__(timeout=300)
                self.user = user
                self.current_page = 1
                self.total_pages = 7
                self.update_button_states()

            def update_button_states(self):
                self.children[0].disabled = self.current_page == 1
                self.children[1].disabled = self.current_page == self.total_pages

            async def update_page(self, interaction: discord.Interaction):
                embed = self.get_embed_for_page(self.current_page)
                await interaction.response.edit_message(embed=embed, view=self)

            def get_embed_for_page(self, page: int) -> discord.Embed:
                if page == 1:
                    embed = discord.Embed(
                        title="Reduced cooldowns and limits!",
                        description=(
                            "With [**`Heist Premium`**](https://heist.cursi.ng/premium), you will have your limits reduced as follows:\n\n"
                            "* </discord user:1278389799857946699>:\n"
                            "> Usage: **`30s`** to **`10s`**.\n"
                            "* </tags create:1349131511772745782>:\n"
                            "> Max tags: **`5`** to **`20`**.\n"
                            "* **Transcribe VM (Menu)**:\n"
                            "> Transcription limit (Per VM): **`30s`** to **`2m30s`**.\n"
                            "> Daily usage limit: **`10`** to **`30`**.\n"
                            "* **Image to Text (Menu)**:\n"
                            "> Daily usage limit: **`50`** to **`200`**.\n"
                        ),
                        color=embed_color
                    )
                if page == 2:
                    embed = discord.Embed(
                        title="</ask locate:1345486046065987604>",
                        description="Locate any image you wish, with the power of **AI**.",
                        color=embed_color
                    )
                    embed.set_image(url="https://images.guns.lol/TvZo8wkHHl.png")
                if page == 3:
                    embed = discord.Embed(
                        title="</ask destroylonely:1345486046065987604>",
                        description="Speak with Destroy Lonely, completely unfiltered.",
                        color=embed_color
                    )
                    embed.set_image(url="https://images.guns.lol/0aCDOcljc9.png")
                if page == 4:
                    embed = discord.Embed(
                        title="</ask imagine:1345486046065987604>",
                        description="Generate anything your heart desires, with the power of **AI**.",
                        color=embed_color
                    )
                    embed.set_image(url="https://images.guns.lol/YvvjwJqA5L.png")
                elif page == 5:
                    embed = discord.Embed(
                        title="</discord2roblox:1282374008003629062> & </roblox2discord:1282374008003629061>",
                        description="Find someone's [**`Roblox`**](https://roblox.com) thru Discord and vice versa.",
                        color=embed_color
                    )
                    embed.set_image(url="https://images.guns.lol/f7fpTOO3ne.png")
                elif page == 6:
                    embed = discord.Embed(
                        title="</website screenshot:1292614351731036281>",
                        description="Take a screenshot of any website you want.",
                        color=embed_color
                    )
                    embed.set_image(url="https://images.guns.lol/tIgZsZzOeM.png")
                elif page == 7:
                    embed = discord.Embed(
                        title="And even more!",
                        description="Discover all of Heist's features on [heist.lol](https://heist.cursi.ng/commands)..\nWho knows, there might even be hidden perks.",
                        color=embed_color
                    )

                embed.set_author(name=self.user.name, icon_url=self.user.avatar.url if self.user.avatar else None)
                embed.set_thumbnail(url="https://git.cursi.ng/sparkles.png")
                embed.set_footer(text=f"Page {page}/{self.total_pages} - heist.lol", icon_url="https://git.cursi.ng/heist.png")
                return embed

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.secondary)
            async def prev_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page = max(1, self.current_page - 1)
                self.update_button_states()
                await self.update_page(interaction)

            @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.secondary)
            async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page = min(self.total_pages, self.current_page + 1)
                self.update_button_states()
                await self.update_page(interaction)

        class InitialView(View):
            def __init__(self, user: discord.User):
                super().__init__(timeout=300)
                self.user = user

            @discord.ui.button(label="Get Premium", emoji=discord.PartialEmoji.from_str("<:premstar:1311062009055285289>"), style=discord.ButtonStyle.secondary)
            async def get_premium_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if is_donor:
                    await interaction.response.send_message("You already have Premium.", ephemeral=True)
                else:
                    embed = await cembed(
                        interaction,
                        title="Heist Premium",
                        url="https://heist.cursi.ng/premium",
                        description=(
                            f"Get Heist's **Premium** plan and unlock a variety of new features.\nHaving issues or wanna use Crypto? Open a ticket [here](https://discord.gg/6ScZFN3wPA).\n\n-# **Product Unavailable?** Purchase from a Desktop client instead.\n-# For a full list, use </premium perks:1278389799857946700> or view on [**web**](<https://heist.cursi.ng/premium>)."
                        )
                    )
                    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
                    embed.set_author(name=f"{interaction.user.name}", icon_url=interaction.user.display_avatar.url)

                    sku = discord.ui.Button(style=discord.ButtonStyle.premium, sku_id="1315790785500942357")
                    
                    crypto_button = discord.ui.Button(
                        style=discord.ButtonStyle.secondary,
                        label="Crypto / Others",
                        emoji="<:crypto:1324215914702569572>",
                        custom_id="crypto_button"
                    )

                    async def crypto_button_callback(interaction: discord.Interaction):
                        await interaction.response.send_message("Make a ticket in https://discord.gg/6ScZFN3wPA", ephemeral=True)

                    crypto_button.callback = crypto_button_callback
    

                    view = discord.ui.View(timeout=500)
                    view.add_item(sku)
                    view.add_item(crypto_button)
    

                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                    return
                    
            @discord.ui.button(label="View Perks", emoji=discord.PartialEmoji.from_str("<:sparkles2:1299136124991705219>"), style=discord.ButtonStyle.secondary)
            async def view_perks_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                view = PremiumView(self.user)
                embed = view.get_embed_for_page(1)
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        initial_embed = discord.Embed(
            title="Premium Perks",
            description=(
                "> Get access to **exclusive benefits** with [**`Heist Premium`**](https://heist.cursi.ng/premium)!\n"
                "> From **no cooldowns** at all, to other **powerful features**.\n"
                "> Discover all the perks below."
            ),
            color=embed_color
        )
        initial_embed.set_thumbnail(url="https://git.cursi.ng/premium2.gif")
        initial_embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        initial_embed.set_footer(text="heist.lol", icon_url="https://git.cursi.ng/heist.png?c")

        initial_view = InitialView(interaction.user)
        await interaction.followup.send(embed=initial_embed, view=initial_view)

    @premium.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def buy(self, interaction: Interaction): 
        """Purchase Heist Premium."""
        is_donor = await check_donor(interaction.user.id)

        if is_donor:
            await interaction.followup.send("You already have Premium, you can check the perks on [heist.lol](<https://heist.cursi.ng/premium>).", ephemeral=True)
            return
        else:
            embed = await cembed(
                interaction,
                title="Heist Premium",
                url="https://heist.cursi.ng/premium",
                description=(
                    f"Get Heist's **Premium** plan and unlock a variety of new features.\nHaving issues or wanna use Crypto? Open a ticket [here](https://discord.gg/6ScZFN3wPA).\n\n-# **Product Unavailable?** Purchase from a Desktop client instead.\n-# For a full list, use </premium perks:1278389799857946700> or view on [**web**](<https://heist.cursi.ng/premium>)."
                ),
            )
            embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
            embed.set_author(name=f"{interaction.user.name}", icon_url=interaction.user.display_avatar.url)

            sku = discord.ui.Button(style=discord.ButtonStyle.premium, sku_id="1315790785500942357")
            
            crypto_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Crypto / Others",
                emoji="<:crypto:1324215914702569572>",
                custom_id="crypto_button"
            )

            async def crypto_button_callback(interaction: discord.Interaction):
                await interaction.response.send_message("Make a ticket in https://discord.gg/6ScZFN3wPA", ephemeral=True)

            crypto_button.callback = crypto_button_callback

            view = discord.ui.View(timeout=500)
            view.add_item(sku)
            view.add_item(crypto_button)

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return

    async def get_user_count(self):
        try:
            async with get_db_connection() as conn:
                user_count = await conn.fetchval("SELECT COUNT(*) FROM user_data")
                
                async with self.session.get('http://127.0.0.1:5002/getcount') as response:
                    response.raise_for_status()
                    data = await response.json()
                    discord_user_install_count = await asyncio.to_thread(lambda: data.get('discord_user_install_count', 0))
                    
                    #return user_count
                    return discord_user_install_count
        except Exception as e:
            print(f"Failed to get user count: {e}")
            return 0

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.check(permissions.is_blacklisted)
    async def usercount(self, interaction: Interaction):
        """Get the total number of users."""
        user_count = await self.get_user_count()
        member_count = await asyncio.to_thread(lambda: sum(guild.member_count for guild in self.client.guilds))
        
        fuc = await asyncio.to_thread(lambda: "{:,}".format(user_count))
        fmc = await asyncio.to_thread(lambda: "{:,}".format(member_count))
        
        await interaction.response.send_message(
            f"The bot currently has:\n`{fuc}` individual users (Updates every 24h)\n`{fmc}` total server members",
            ephemeral=False
        )

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def embedusage(self, interaction: Interaction):
        """Embed command usage."""
        embed = await cembed(interaction, title="Usage of the embed command", description="\n```/embed (title) (description) (author) (footer) (footer_image) (thumbnail) (color)```\nUse **\\n** to enter a newline (max is 20).\nUse **{timestamp}** to get a timestamp.\nThe value for color has to be [HEX](https://imagecolorpicker.com/color-code).\n\nFor a more interactive way (including presets), check out </selfembed builder:1298023579224637511>.")
        embed.set_footer(text=f"{footer}", icon_url="https://git.cursi.ng/heist.png")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(client):
    await client.add_cog(Info(client))
