import time
import functools
from typing import Callable, Optional
from discord import app_commands, Interaction, Embed, Color
from utils.db import redis_client, check_donor
from utils.embed import cembed
from utils import messages

class CooldownManager:
    def __init__(self, redis_client):
        self.redis = redis_client

    def cooldown(self, default: int, donor: Optional[int] = None, group: Optional[str] = None) -> Callable:
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(self, interaction: Interaction, *args, **kwargs):
                user_id = str(interaction.user.id)
                is_donor = await check_donor(user_id) if donor is not None else False
                cooldown = donor if is_donor and donor is not None else default

                key_suffix = group if group is not None else func.__name__
                key = f"cooldown:{user_id}:{key_suffix}"

                lua_script = """
                local last_used = redis.call('GET', KEYS[1])
                if last_used and tonumber(last_used) + tonumber(ARGV[1]) > tonumber(ARGV[2]) then
                    return tonumber(last_used) + tonumber(ARGV[1]) - tonumber(ARGV[2])
                else
                    if tonumber(ARGV[1]) > 0 then
                        redis.call('SETEX', KEYS[1], ARGV[1], ARGV[2])
                    end
                    return 0
                end
                """
                current_time = time.time()
                remaining_cooldown = float(await self.redis.eval(lua_script, 1, key, cooldown, current_time))

                if remaining_cooldown > 0:
                    rcf = (
                        f"{int(remaining_cooldown)}" 
                        if remaining_cooldown.is_integer() 
                        else f"{remaining_cooldown:.1f}"
                    )
                    timeg = "second" if remaining_cooldown == 1 else "seconds"
                    description = messages.warn(
                        interaction.user,
                        f"You're on cooldown for **{rcf} {timeg}**."
                    )
                    if not is_donor and donor is not None:  
                        if donor == 0:
                            description += (
                                "\n\n> [**Premium**](<https://discord.gg/heistbot>) users don't have a cooldown.\n"
                                "> You can find out more by using </premium perks:1278389799857946700>."
                            )
                        else:
                            description += (
                                f"\n\n> The [**Premium**](<https://disczord.gg/heistbot>) cooldown is **{donor} seconds**.\n"
                                "> You can find out more by using </premium perks:1278389799857946700>."
                            )
                    embed = await cembed(
                        interaction,
                        description=description
                    )
                    if not interaction.response.is_done():
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                    else:
                        await interaction.followup.send(embed=embed, ephemeral=True)
                    return

                await func(self, interaction, *args, **kwargs)

            return wrapper
        return decorator

manager = CooldownManager(redis_client)
cooldown = manager.cooldown