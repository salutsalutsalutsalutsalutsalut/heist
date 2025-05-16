import discord
import random
import string
from discord.app_commands.errors import CommandInvokeError
from utils import messages

def generate_error_id(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

async def error_handler(interaction, error, custom_message=None, fallback_message=None):
    error_message = str(error)
    if "Interaction has already been acknowledged." in error_message:
        return
    if isinstance(error, CommandInvokeError):
        return
    if isinstance(error, discord.HTTPException) and error.status == 404:
        return 

    error_id = generate_error_id()
    user_id = interaction.user.id
    command_name = interaction.command.name if interaction.command else "Origin: Button/Select"

    embed = discord.Embed(title="Error Log", color=0x000f)
    embed.add_field(name="User ID", value=user_id, inline=True)

    command_details = f"**{command_name}**\n"

    try:
        options = interaction.data.get('options', [])
        if options:
            options_text = "\n".join([
                f"* {opt['name']}: `{opt.get('value', 'N/A')}`" 
                for opt in options
            ])
            command_details += options_text
    except Exception:
        command_details += "(Unable to parse options)"

    embed.add_field(name="Command Issued", value=command_details, inline=True)
    embed.add_field(name="Error", value=str(error), inline=True)
    embed.add_field(name="Error ID", value=f"`{error_id}`", inline=True)
    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)

    error_logs_channel_id = 1336529686666154064
    error_logs_channel = interaction.client.get_channel(error_logs_channel_id)
    if error_logs_channel:
        await error_logs_channel.send(embed=embed)

    is_automod_error = "Message was blocked by AutoMod" in error_message
    user_message = custom_message or (
        messages.warn(interaction.user, f"`Command '{command_name}' was blocked by AutoMod.`")
        if is_automod_error else
        messages.warn(interaction.user, f"`Command '{command_name}' raised an exception: {str(error)}`\nError persists? Join the [discord server](<https://discord.gg/heistbot>) and report it.\n-# * id: `{error_id}`")
    )

    try:
        if interaction.response.is_done():
            await interaction.followup.send(user_message, ephemeral=False)
        else:
            await interaction.response.send_message(user_message, ephemeral=False)
    except discord.HTTPException as e:
        if fallback_message:
            if command_name == "Origin: Button/Select":
                if "Message was blocked by AutoMod" not in error_message:
                    fallback_msg = f"`Interaction raised an exception: {str(error_message)}`\nError persists? Join the [discord server](<https://discord.gg/heistbot>) and report it.\n-# * id: `{error_id}`"
                else:
                    fallback_msg = f"`Interaction was blocked by AutoMod.`\nError persists? Join the [discord server](<https://discord.gg/heistbot>) and report it.\n-# * id: `{error_id}`"
                await interaction.user.send(fallback_msg)
            else:
                if "Message was blocked by AutoMod" not in error_message:
                    fallback_msg = f"`Command '{command_name}' raised an exception: {str(error_message)}`\nError persists? Join the [discord server](<https://discord.gg/heistbot>) and report it.\n-# * id: `{error_id}`"
                else:
                    fallback_msg = f"`Command '{command_name}' was blocked by AutoMod.`"
                try:
                    await interaction.followup.send(fallback_msg)
                except Exception:
                    if "Message was blocked by AutoMod" not in error_message:
                        if command_name:
                            try:
                                await interaction.followup.send(f"`Command '{command_name}' raised an exception. Check DMs for details.`\n-# * id: `{error_id}`")
                            except Exception:
                                try:
                                    await interaction.followup.send(f"`Command '{command_name}' raised an exception. Check DMs for details.`")
                                except Exception:
                                    try:
                                        await interaction.followup.send(f"Command {command_name} raised an exception. Check DMs for details.`")
                                    except Exception:
                                        await interaction.user.send(f"`Command '{command_name}' raised an exception: {str(error_message)}`\n"
                                        "Error persists? Join the [discord server](<https://discord.gg/heistbot>) and report it.\n"
                                        f"-# * id: `{error_id}`")
                        else:
                            await interaction.user.send(f"`Interaction raised an exception: {str(error_message)}`\n"
                            "Error persists? Join the [discord server](<https://discord.gg/heistbot>) and report it.\n"
                            f"-# * id: `{error_id}`")
                    else:
                        if command_name:
                            try:
                                await interaction.followup.send(f"`Command '{command_name}' was blocked by AutoMod. Check DMs for details.`\n-# * id: `{error_id}`")
                            except Exception:
                                try:
                                    await interaction.followup.send(f"`Command '{command_name}' was blocked by AutoMod.`")
                                except Exception:
                                    try:
                                        await interaction.followup.send(f"Command {command_name} was blocked by AutoMod.`")
                                    except Exception:
                                        await interaction.user.send(f"`Command '{command_name}' was blocked by AutoMod.`\n"
                                        "Error persists? Join the [discord server](<https://discord.gg/heistbot>) and report it.\n"
                                        f"-# * id: `{error_id}`")
                        else:
                            await interaction.user.send(f"`Interaction was blocked by AutoMod.`\n"
                            "Error persists? Join the [discord server](<https://discord.gg/heistbot>) and report it.\n"
                            f"-# * id: `{error_id}`")