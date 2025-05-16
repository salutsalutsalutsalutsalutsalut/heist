import discord
from discord import Interaction
from typing import Optional
from utils.cache import get_embed_color

async def cembed(interaction: Interaction, color: Optional[int] = None, **kwargs) -> discord.Embed:
    user_id = str(interaction.user.id)
    embed_color = color if color is not None else await get_embed_color(user_id)
    embed = discord.Embed(color=embed_color, **kwargs)
    return embed