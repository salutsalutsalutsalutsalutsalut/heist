import discord
from discord import app_commands, Interaction, Embed, ButtonStyle
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from utils.db import get_db_connection, check_donor
from utils import permissions
from utils.cache import set_embed_color, get_embed_color

class SetColorModal(Modal):
    def __init__(self, user_id: int, settings_cog):
        super().__init__(title="Set Embed Color")
        self.user_id = user_id
        self.settings_cog = settings_cog

        self.color_input = TextInput(
            label="Enter a HEX color code (e.g., #ff5733)",
            placeholder="#000000",
            max_length=7,
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.color_input)

    async def on_submit(self, interaction: Interaction):
        color_code = self.color_input.value.strip()

        if not color_code.startswith("#") or len(color_code) != 7:
            await interaction.response.send_message("Invalid color. Please use a hex color code, like `#ff5733` for example.", ephemeral=True)
            return

        try:
            color_value = int(color_code[1:], 16)

            if not (0 <= color_value <= 0xFFFFFF):
                await interaction.response.send_message("Invalid color. Please use a valid hex color code.", ephemeral=True)
                return

            await self.settings_cog.db_execute(
                "INSERT INTO settings (user_id, embed_color) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET embed_color = EXCLUDED.embed_color",
                (self.user_id, color_value)
            )

            await set_embed_color(self.user_id, color_value)

            embed = interaction.message.embeds[0]
            embed.color = color_value
            embed.description = embed.description.split("\n* **Embed Color:**\n")[0] + f"\n* **Embed Color:**\n  * #{color_code[1:]}"

            await interaction.response.edit_message(embed=embed)
            await interaction.followup.send(f"Embed color updated to {color_code}!", ephemeral=True)

        except ValueError:
            await interaction.response.send_message("Invalid color code. Please use a hex color code like `#ff5733`.", ephemeral=True)

class Settings(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def db_execute(self, query, params=(), fetchone=False):
        async with get_db_connection() as conn:
            try:
                async with conn.transaction():
                    if fetchone:
                        result = await conn.fetchrow(query, *params)
                    else:
                        result = await conn.fetch(query, *params)
                    return result
            except Exception as e:
                print(f"Database query error: {e}")
                return None
            finally:
                await conn.close()

    async def load_colors_from_db(self):
        result = await self.db_execute(
            "SELECT user_id, embed_color FROM settings"
        )

        if result:
            for row in result:
                user_id = row['user_id']
                embed_color = row['embed_color']

                if isinstance(embed_color, int):
                    await set_embed_color(user_id, embed_color)
                    
    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def settings(self, interaction: Interaction):
        """Manage your personal settings."""
        user_id = str(interaction.user.id)
        
        await self.db_execute(
            "CREATE TABLE IF NOT EXISTS settings (user_id BIGINT PRIMARY KEY, guilds_state TEXT DEFAULT 'Show', lastfm_state TEXT DEFAULT 'Show', embed_color INTEGER DEFAULT 15, guild_activity_state TEXT DEFAULT 'Enabled')"
        )

        result = await self.db_execute(
            "SELECT guilds_state, lastfm_state, embed_color, guild_activity_state FROM settings WHERE user_id = $1", (user_id,), fetchone=True
        )
        if result:
            guilds_state = result['guilds_state']
            lastfm_state = result['lastfm_state']
            embed_color = result['embed_color']
            guild_activity_state = result['guild_activity_state']
        else:
            guilds_state = 'Show'
            lastfm_state = 'Show'
            embed_color = 0x3b3b3b
            guild_activity_state = 'Enabled'

        guilds_display_state = '☑️ Shown' if guilds_state == 'Show' else '✖️ Hidden'
        guilds_button_label = "Hide Guilds" if guilds_state == 'Show' else "Show Guilds"

        lastfm_display_state = '☑️ Shown' if lastfm_state == 'Show' else '✖️ Hidden'
        lastfm_button_label = "Hide LastFM Username" if lastfm_state == 'Show' else "Show LastFM Username"

        guild_presence_display_state = '☑️ Enabled' if guild_activity_state == 'Enabled' else '✖️ Disabled'
        guild_presence_button_label = "Disable Guild Activity" if guild_activity_state == 'Enabled' else "Enable Guild Activity"

        embed = Embed(
            title="Settings",
            description=f"* **LastFM Username Visibility:**\n  * {lastfm_display_state}\n* **Guild Activity:**\n  * {guild_presence_display_state}\n* **Embed Color:**\n  * #{embed_color:06x}\n",
            color=embed_color
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)

        lastfm_button = Button(label=lastfm_button_label, emoji="🔗", style=ButtonStyle.secondary, custom_id="toggle_lastfm")
        guild_presence_button = Button(label=guild_presence_button_label, emoji="🌐", style=ButtonStyle.secondary, custom_id="toggle_guild_presence")
        color_button = Button(label="Set Embed Color", emoji="🎨", style=ButtonStyle.primary, custom_id="set_embed_color")

        view = View()
        view.add_item(lastfm_button)
        view.add_item(guild_presence_button)
        view.add_item(color_button)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_colors_from_db()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: Interaction):
        if interaction.type == discord.InteractionType.component:
            user_id = str(interaction.user.id)

            if interaction.data['custom_id'] == "toggle_guilds":
                result = await self.db_execute(
                    "SELECT guilds_state FROM settings WHERE user_id = $1", (user_id,), fetchone=True
                )
                current_state = result['guilds_state'] if result else 'Show'
                new_state = 'Hide' if current_state == 'Show' else 'Show'

                await self.db_execute(
                    "INSERT INTO settings (user_id, guilds_state) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET guilds_state = EXCLUDED.guilds_state",
                    (user_id, new_state)
                )

            elif interaction.data['custom_id'] == "toggle_lastfm":
                result = await self.db_execute(
                    "SELECT lastfm_state FROM settings WHERE user_id = $1", (user_id,), fetchone=True
                )
                current_state = result['lastfm_state'] if result else 'Show'
                new_state = 'Hide' if current_state == 'Show' else 'Show'

                await self.db_execute(
                    "INSERT INTO settings (user_id, lastfm_state) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET lastfm_state = EXCLUDED.lastfm_state",
                    (user_id, new_state)
                )

            elif interaction.data['custom_id'] == "toggle_guild_presence":
                result = await self.db_execute(
                    "SELECT guild_activity_state FROM settings WHERE user_id = $1", (user_id,), fetchone=True
                )
                current_state = result['guild_activity_state'] if result else 'Enabled'
                new_state = 'Disabled' if current_state == 'Enabled' else 'Enabled'

                await self.db_execute(
                    "INSERT INTO settings (user_id, guild_activity_state) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET guild_activity_state = EXCLUDED.guild_activity_state",
                    (user_id, new_state)
                )

            elif interaction.data['custom_id'] == "set_embed_color":
                if not await check_donor(interaction.user.id):
                    await interaction.response.send_message(
                        "This is a premium-only command. Run </premium buy:1278389799857946700> to learn more.",
                        ephemeral=True
                    )
                    return

                modal = SetColorModal(user_id=user_id, settings_cog=self)
                await interaction.response.send_modal(modal)
                return

            else:
                return

            guilds_result = await self.db_execute(
                "SELECT guilds_state FROM settings WHERE user_id = $1", (user_id,), fetchone=True
            )
            guilds_state = guilds_result['guilds_state'] if guilds_result else 'Show'

            lastfm_result = await self.db_execute(
                "SELECT lastfm_state FROM settings WHERE user_id = $1", (user_id,), fetchone=True
            )
            lastfm_state = lastfm_result['lastfm_state'] if lastfm_result else 'Show'

            guild_presence_result = await self.db_execute(
                "SELECT guild_activity_state FROM settings WHERE user_id = $1", (user_id,), fetchone=True
            )
            guild_activity_state = guild_presence_result['guild_activity_state'] if guild_presence_result else 'Enabled'

            color_result = await self.db_execute(
                "SELECT embed_color FROM settings WHERE user_id = $1", (user_id,), fetchone=True
            )
            embed_color = color_result['embed_color'] if color_result else 0x3b3b3b
            await set_embed_color(user_id, embed_color)

            guilds_display_state = '☑️ Shown' if guilds_state == 'Show' else '✖️ Hidden'
            guilds_button_label = "Hide Guilds" if guilds_state == 'Show' else "Show Guilds"

            lastfm_display_state = '☑️ Shown' if lastfm_state == 'Show' else '✖️ Hidden'
            lastfm_button_label = "Hide LastFM Username" if lastfm_state == 'Show' else "Show LastFM Username"

            guild_presence_display_state = '☑️ Enabled' if guild_activity_state == 'Enabled' else '✖️ Disabled'
            guild_presence_button_label = "Disable Guild Activity" if guild_activity_state == 'Enabled' else "Enable Guild Activity"

            embed = Embed(
                title="Settings",
                description=f"* **LastFM Username Visibility:**\n  * {lastfm_display_state}\n* **Guild Activity:**\n  * {guild_presence_display_state}\n* **Embed Color:**\n  * #{embed_color:06x}",
                color=embed_color
            )
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)

            lastfm_button = Button(label=lastfm_button_label, emoji="🔗", style=ButtonStyle.secondary, custom_id="toggle_lastfm")
            guild_presence_button = Button(label=guild_presence_button_label, emoji="🌐", style=ButtonStyle.secondary, custom_id="toggle_guild_presence")
            color_button = Button(label="Set Embed Color", emoji="🎨", style=ButtonStyle.primary, custom_id="set_embed_color")

            view = View()
            view.add_item(lastfm_button)
            view.add_item(guild_presence_button)
            view.add_item(color_button)

            await interaction.response.edit_message(embed=embed, view=view)

async def setup(client):
    await client.add_cog(Settings(client))