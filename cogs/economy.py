import discord
from discord import app_commands, Interaction, User, Embed, ButtonStyle, ui
from discord.app_commands import Group, Command
from discord.ext.commands import GroupCog
from discord.ui import View, Button
from discord.ext import commands
from utils.db import check_blacklisted, check_booster, check_donor, check_owner, check_famous, execute_query, get_db_connection, redis_client
from utils.error import error_handler
from utils.cache import get_embed_color
from utils.embed import cembed
from utils import default, permissions, messages
import random, aiohttp, io, pytz, time, secrets, asyncio, os, aiohttp, urllib.parse, re, json, logging
from datetime import datetime, timedelta, timezone
from filelock import FileLock
from PIL import Image
from utils.cd import cooldown
from dotenv import load_dotenv
from typing import List
import uuid
load_dotenv()

footer = "heist.lol"

class Economy(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pool = get_db_connection
        self.redis = redis_client
        self._lock_identifiers = {}

    async def acquire_lock(self, user_id: str, ttl: int = 10000) -> bool:
        identifier = str(uuid.uuid4())
        key = f"eco_lock:{user_id}"

        acquired = await self.redis.set(key, identifier, nx=True, px=ttl)
        if acquired:
            self._lock_identifiers[user_id] = identifier
            return True
        
        for _ in range(10):
            await asyncio.sleep(0.1)
            acquired = await self.redis.set(key, identifier, nx=True, px=ttl)
            if acquired:
                self._lock_identifiers[user_id] = identifier
                return True

        return False

    async def release_lock(self, user_id: str) -> None:
        key = f"eco_lock:{user_id}"
        if user_id not in self._lock_identifiers:
            return

        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        await self.redis.eval(lua_script, 1, key, self._lock_identifiers[user_id])
        del self._lock_identifiers[user_id]

    async def fetch_data(self, user_id: str):
        cache_key = f"economy:{user_id}"
        cached_data = await self.redis.hgetall(cache_key)
        if cached_data:
            if all(key in cached_data for key in ["cash", "bank", "bank_limit", "claimed_bonus", "last_work", "last_rob", "last_fish", "last_daily", "last_vote"]):
                return {
                    "cash": int(cached_data["cash"]),
                    "bank": int(cached_data["bank"]),
                    "bank_limit": int(cached_data["bank_limit"]),
                    "claimed_bonus": None if cached_data["claimed_bonus"] == "None" else datetime.fromisoformat(cached_data["claimed_bonus"]),
                    "last_work": None if cached_data["last_work"] == "None" else datetime.fromisoformat(cached_data["last_work"]),
                    "last_rob": None if cached_data["last_rob"] == "None" else datetime.fromisoformat(cached_data["last_rob"]),
                    "last_fish": None if cached_data["last_fish"] == "None" else datetime.fromisoformat(cached_data["last_fish"]),
                    "last_daily": None if cached_data["last_daily"] == "None" else datetime.fromisoformat(cached_data["last_daily"]),
                    "last_vote": None if cached_data["last_vote"] == "None" else datetime.fromisoformat(cached_data["last_vote"])
                }
        async with self.pool() as conn:
            row = await conn.fetchrow(
                "SELECT cash, bank, bank_limit, claimed_bonus, last_work, last_rob, last_fish, last_daily, last_vote FROM economy WHERE user_id = $1",
                str(user_id)
            )
            if row:
                claimed_bonus_str = row["claimed_bonus"].isoformat() if row["claimed_bonus"] else "None"
                last_work_str = row["last_work"].isoformat() if row["last_work"] else "None"
                last_rob_str = row["last_rob"].isoformat() if row["last_rob"] else "None"
                last_fish_str = row["last_fish"].isoformat() if row["last_fish"] else "None"
                last_daily_str = row["last_daily"].isoformat() if row["last_daily"] else "None"
                last_vote_str = row["last_vote"].isoformat() if row["last_vote"] else "None"
                await self.redis.hset(cache_key, mapping={
                    "cash": str(row["cash"]),
                    "bank": str(row["bank"]),
                    "bank_limit": str(row["bank_limit"]),
                    "claimed_bonus": claimed_bonus_str,
                    "last_work": last_work_str,
                    "last_rob": last_rob_str,
                    "last_fish": last_fish_str,
                    "last_daily": last_daily_str,
                    "last_vote": last_vote_str
                })
                await self.redis.expire(cache_key, 300)
                return dict(row)
        return None

    eco = app_commands.Group(
        name="eco", 
        description="Economy related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    inventory = app_commands.Group(
        name="inventory", 
        description="Inventory related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        parent=eco
    )

    bank = app_commands.Group(
        name="bank", 
        description="Bank related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        parent=eco
    )

    def parse_amount(self, amount_str: str, current_balance: int) -> int:
        amount_str = amount_str.lower().strip()
        if amount_str == "all":
            return current_balance
        elif amount_str == "half":
            return current_balance // 2
        elif amount_str.endswith("k"):
            return int(float(amount_str[:-1]) * 1000)
        elif amount_str.endswith("m"):
            return int(float(amount_str[:-1]) * 1000000)
        else:
            try:
                return int(amount_str)
            except ValueError:
                raise ValueError("Invalid amount format. Use 'all', 'half', '1k', '2m', or a plain number.")

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user to get information from, leave empty to get your own.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def wallet(self, interaction: Interaction, user: User = None):
        """Check a wallet's balance."""
        if user is None:
            user = interaction.user

        user_data = await self.fetch_data(str(user.id))
        if user_data is None:
            if user.id == interaction.user.id:
                async with self.pool() as conn:
                    await conn.execute(
                        "INSERT INTO economy (user_id, cash, bank, bank_limit) VALUES ($1, $2, $3, $4) ON CONFLICT (user_id) DO NOTHING",
                        str(user.id), 5000, 0, 50000
                    )
                    user_data = await self.fetch_data(str(user.id))
            else:
                await interaction.followup.send(f"{user.name} doesn't have a wallet yet.")
                return

        cash = int(user_data["cash"])
        bank = int(user_data["bank"])
        bank_limit = int(user_data["bank_limit"])

        async with self.pool() as conn:
            total_users = await conn.fetchval("SELECT COUNT(*) FROM economy")
            user_rank = await conn.fetchval(
                "SELECT COUNT(*) FROM economy WHERE (cash::BIGINT + bank::BIGINT) > ($1::BIGINT + $2::BIGINT)",
                cash, bank
            ) + 1

        embed = await cembed(interaction)
        embed.set_author(name=f"{user.name}'s balance", icon_url=user.display_avatar.url)
        embed.add_field(name="💵 Cash", value=f"**`{cash:,}`**", inline=True)
        embed.add_field(name="💳 Bank", value=f"**`{bank:,}`** / **`{bank_limit:,}`**", inline=True)
        embed.set_footer(text=f"#{user_rank:,} out of {total_users:,}")

        await interaction.followup.send(embed=embed)

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=3)
    async def vote(self, interaction: discord.Interaction):
        "Vote for Heist and claim your daily 50,000 💵."
        user_id = str(interaction.user.id)

        try:
            await self.acquire_lock(user_id)

            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return

            last_vote = user_data.get("last_vote")
            if last_vote is not None and last_vote != "None":
                last_vote = datetime.fromisoformat(str(last_vote))
                if datetime.utcnow() < last_vote + timedelta(hours=12):
                    cooldowne = last_vote + timedelta(hours=12)
                    cooldownt = int(cooldowne.timestamp())
                    embed = await cembed(interaction,
                        description=f"⏰ {interaction.user.mention}: You can vote again <t:{cooldownt}:R>.",
                        color=0xff6464
                    )
                    await interaction.followup.send(embed=embed)
                    return

            embed = await cembed(interaction,
                title="Vote for Heist",
                description="✨ Vote for **Heist** & claim **50,000** 💵.",
                url="https://top.gg/bot/1225070865935368265/vote"
            )
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Vote", url="https://top.gg/bot/1225070865935368265/vote"))
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=3)
    async def fish(self, interaction: discord.Interaction):
        """Let's go fishing!"""
        user_id = str(interaction.user.id)

        try:
            await self.acquire_lock(user_id)

            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return

            last_fish = user_data.get("last_fish")
            if last_fish is not None and last_fish != "None":
                last_fish = datetime.fromisoformat(str(last_fish))
                if datetime.utcnow() < last_fish + timedelta(minutes=30):
                    cooldown_end = last_fish + timedelta(minutes=30)
                    cooldown_timestamp = int(cooldown_end.timestamp())
                    embed = await cembed(interaction,
                        description=f"⏰ {interaction.user.mention}: You can fish again <t:{cooldown_timestamp}:R>.",
                        color=0xff6464
                    )
                    await interaction.followup.send(embed=embed)
                    return

            earnings = random.randint(0, 500)
            fish_type = "salmon"
            current_time = datetime.utcnow()

            async with self.pool() as conn:
                await conn.execute(
                    "UPDATE economy SET cash = cash + $1, last_fish = $2 WHERE user_id = $3",
                    earnings, current_time, user_id
                )
                await conn.execute(
                    "INSERT INTO inventory (user_id, item, quantity) VALUES ($1, $2, $3) "
                    "ON CONFLICT (user_id, item) DO UPDATE SET quantity = inventory.quantity + $3",
                    user_id, fish_type, 1
                )

            await self.redis.delete(f"economy:{user_id}")

            if earnings == 0:
                message = f"🎣 {interaction.user.mention}: You caught a **{fish_type}** fish!"
            else:
                message = f"🎣 {interaction.user.mention}: You caught a **{fish_type}** fish and earned **{earnings}** 💵!"

            embed = await cembed(interaction, description=message, color=0xa4ec7c)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @inventory.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=3, donor=0)
    async def view(self, interaction: discord.Interaction, user: discord.User = None):
        """View yours or somebody's inventory."""
        target_user = user if user else interaction.user
        user_id = str(target_user.id)

        try:
            await self.acquire_lock(user_id)

            async with self.pool() as conn:
                inventory_items = await conn.fetch(
                    "SELECT inventory.item, inventory.quantity, items.emoji "
                    "FROM inventory "
                    "JOIN items ON inventory.item = items.item "
                    "WHERE inventory.user_id = $1",
                    user_id
                )

            if not inventory_items:
                if interaction.app_permissions.embed_links:
                    embed = await cembed(interaction,
                        description=f"💀 {interaction.user.mention}: **{target_user.name}** has no items in their inventory.",
                        color=0xff6464
                    )
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"💀 {interaction.user.mention}: **{target_user.name}** has no items in their inventory.")
                return

            inventory_list = []
            for item in inventory_items:
                item_name = item["item"].replace("_", " ").title()
                quantity = item["quantity"]
                emoji = item["emoji"] if item["emoji"] else ""
                inventory_list.append(f"**`{quantity}x`** **{item_name}** {emoji}")

            inventory_list = "\n".join(inventory_list)

            embed = await cembed(
                interaction
            )
            embed.set_author(
                name=f"{target_user.name}'s Inventory",
                icon_url=target_user.display_avatar.url
            )
            embed.add_field(
                name="Items",
                value=inventory_list,
                inline=False
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @inventory.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=3)
    async def use(self, interaction: discord.Interaction, item: str, amount: int = 1):
        """Use an item from your inventory."""
        user_id = str(interaction.user.id)

        try:
            await self.acquire_lock(user_id)

            async with self.pool() as conn:
                item_data = await conn.fetchrow(
                    "SELECT inventory.item, inventory.quantity, items.usable, items.rewards, items.emoji "
                    "FROM inventory "
                    "JOIN items ON inventory.item = items.item "
                    "WHERE inventory.user_id = $1 AND inventory.item = $2",
                    user_id, item
                )

                if not item_data:
                    await interaction.followup.send(messages.warn(interaction.user, f"You don't have **{item.replace('_', ' ').title()}** in your inventory."))
                    return

                if amount > item_data["quantity"]:
                    await interaction.followup.send(messages.warn(interaction.user, f"You don't have enough **{item.replace('_', ' ').title()}** (you have {item_data['quantity']})."))
                    return

                if not item_data["usable"]:
                    if interaction.app_permissions.embed_links:
                        embed = await cembed(interaction,
                            description=f"💀 {interaction.user.mention}: You can't use **{item.replace('_', ' ').title()}**.",
                            color=0xff6464
                        )
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send(f"💀 {interaction.user.mention}: You can't use **{item.replace('_', ' ').title()}**.")
                    return

                rewards = await asyncio.to_thread(json.loads, item_data["rewards"]) if item_data["rewards"] else None
                if not rewards:
                    await interaction.followup.send(f"**{item.replace('_', ' ').title()}** has no use. (why was this enabled?)")
                    return

                emoji = item_data["emoji"] if item_data["emoji"] else "❓"
                if "crate" in item.lower():
                    opening_text = f"Opening {emoji}.."
                else:
                    opening_text = f"Using {emoji}.."

                embed = await cembed(interaction, description=opening_text, color=0xa4ec7c)
                message = await interaction.followup.send(embed=embed)

                await asyncio.sleep(1)

                reward_message = []
                cash_reward = 0
                item_rewards = []

                if "cash" in rewards:
                    cash_min, cash_max = rewards["cash"]
                    cash_reward = random.randint(cash_min, cash_max) * amount
                    await conn.execute(
                        "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                        cash_reward, user_id
                    )
                    reward_message.append(f"**{cash_reward}** 💵")
                    await self.redis.delete(f"economy:{user_id}")

                if "items" in rewards:
                    for item_reward in rewards["items"]:
                        if random.random() <= item_reward["chance"]:
                            item_name_reward = item_reward["item"]
                            quantity_min = item_reward.get("quantity_min", 1)
                            quantity_max = item_reward.get("quantity_max", 1)
                            item_quantity = random.randint(quantity_min, quantity_max) * amount
                            await conn.execute(
                                "INSERT INTO inventory (user_id, item, quantity) VALUES ($1, $2, $3) "
                                "ON CONFLICT (user_id, item) DO UPDATE SET quantity = inventory.quantity + $3",
                                user_id, item_name_reward, item_quantity
                            )
                            item_emoji = await conn.fetchval("SELECT emoji FROM items WHERE item = $1", item_name_reward)
                            item_emoji = item_emoji if item_emoji else ""
                            if item_quantity == 1:
                                item_rewards.append(f"**{item_name_reward.replace('_', ' ').title()}** {item_emoji}")
                            else:
                                item_rewards.append(f"**`{item_quantity}x`** **{item_name_reward.replace('_', ' ').title()}** {item_emoji}")

                if item_rewards:
                    reward_message.extend(item_rewards)

                new_quantity = item_data["quantity"] - amount
                if new_quantity <= 0:
                    await conn.execute(
                        "DELETE FROM inventory WHERE user_id = $1 AND item = $2",
                        user_id, item
                    )
                else:
                    await conn.execute(
                        "UPDATE inventory SET quantity = $1 WHERE user_id = $2 AND item = $3",
                        new_quantity, user_id, item
                    )

                if reward_message:
                    final_message = f"💰 {interaction.user.mention}: You won {', '.join(reward_message)}"
                else:
                    final_message = f"💰 {interaction.user.mention}: You used **{amount}x {item.replace('_', ' ').title()}**, but received nothing."

                embed = await cembed(interaction, description=final_message, color=0xa4ec7c)
                await message.edit(embed=embed)

        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @use.autocomplete("item")
    async def use_item_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        async with self.pool() as conn:
            items = await conn.fetch(
                "SELECT item FROM inventory WHERE user_id = $1 AND item ILIKE $2",
                user_id, f"%{current}%"
            )
            return [app_commands.Choice(name=item["item"].replace("_", " ").title(), value=item["item"]) for item in items]

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user to send money to.", amount="The amount of money to send.")
    @app_commands.check(permissions.is_blacklisted)
    @cooldown(default=5, donor=2)
    async def pay(self, interaction: Interaction, user: User, amount: str):
        """Send cash to another user."""
        await interaction.response.defer(thinking=True)

        sender_id = str(interaction.user.id)
        receiver_id = str(user.id)

        try:
            print('acquiring lock for sender')
            await self.acquire_lock(sender_id)
            print('acquiring lock for receiver')
            await self.acquire_lock(receiver_id)
            print('acquiring lock for both')

            print('fetching data for sender')
            sender_data = await self.fetch_data(sender_id)
            print('fetched data for sender')
            if sender_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return

            receiver_data = await self.fetch_data(receiver_id)
            if receiver_data is None:
                await interaction.followup.send(f"{user.name} doesn't have a wallet yet.")
                return

            try:
                sender_cash = int(sender_data["cash"])
                amount_to_send = self.parse_amount(amount, sender_cash)
            except ValueError as e:
                await interaction.followup.send(str(e))
                return

            if amount_to_send > sender_cash:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have enough cash to send that amount."))
                return
            if amount_to_send <= 0:
                await interaction.followup.send(messages.warn(interaction.user, "You must send a positive amount."))
                return

            print('going to da pool')
            async with self.pool() as conn:
                print('we in the pool')
                async with conn.transaction():
                    print('we doing the transaction rn')
                    sender_row = await conn.fetchrow(
                        "SELECT cash FROM economy WHERE user_id = $1 FOR UPDATE", sender_id
                    )
                    print('got sender row')
                    receiver_row = await conn.fetchrow(
                        "SELECT cash FROM economy WHERE user_id = $1 FOR UPDATE", receiver_id
                    )
                    print('got receiver row')

                    if sender_row["cash"] < amount_to_send:
                        await interaction.followup.send(messages.warn(interaction.user, "You don't have enough cash to send that amount."))
                        return

                    print('setting da cash')
                    await conn.execute(
                        "UPDATE economy SET cash = cash - $1 WHERE user_id = $2",
                        amount_to_send, sender_id
                    )
                    await conn.execute(
                        "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                        amount_to_send, receiver_id
                    )

            await self.redis.delete(f"economy:{sender_id}")
            await self.redis.delete(f"economy:{receiver_id}")

            if interaction.app_permissions.embed_links:
                embed = await cembed(
                    interaction,
                    description=messages.success(interaction.user, f"You sent **{amount_to_send:,}** 💵 to {user.name}.")
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"<:vericheck:1301647869505179678> {interaction.user.mention}: You sent **{amount_to_send:,}** 💵 to {user.name}.")
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(sender_id)
            await self.release_lock(receiver_id)

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=3)
    async def daily(self, interaction: discord.Interaction):
        """Claim your daily reward."""
        user_id = str(interaction.user.id)

        try:
            await self.acquire_lock(user_id)

            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return

            last_daily = user_data.get("last_daily")
            if last_daily is not None and last_daily != "None":
                last_daily = datetime.fromisoformat(str(last_daily))
                if datetime.utcnow() < last_daily + timedelta(hours=24):
                    cooldowne = last_daily + timedelta(hours=24)
                    cooldownt = int(cooldowne.timestamp())
                    embed = await cembed(interaction,
                        description=f"⏰ {interaction.user.mention}: You can claim a daily bonus again <t:{cooldownt}:R>.",
                        color=0xff6464
                    )
                    await interaction.followup.send(embed=embed)
                    return

            daily_reward = random.randint(15000, 20000)
            current_time = datetime.utcnow()

            async with self.pool() as conn:
                await conn.execute(
                    "UPDATE economy SET cash = cash + $1, last_daily = $2 WHERE user_id = $3",
                    daily_reward, current_time, str(user_id)
                )

            cache_key = f"economy:{user_id}"
            cached_data = await self.redis.hgetall(cache_key)
            if cached_data:
                new_cash = int(cached_data["cash"]) + daily_reward
                await self.redis.hset(cache_key, mapping={
                    "last_daily": current_time.isoformat(),
                    "cash": str(new_cash),
                    "bank": cached_data["bank"],
                    "bank_limit": cached_data["bank_limit"]
                })
            else:
                await self.redis.hset(cache_key, mapping={
                    "last_daily": current_time.isoformat(),
                    "cash": str(daily_reward),
                    "bank": "0",
                    "bank_limit": "0"
                })
            await self.redis.expire(cache_key, 300)

            embed = await cembed(interaction,
                description=f"💰 {interaction.user.mention}: You have claimed **{daily_reward:,}** 💵",
                color=0xa4ec7c
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=3)
    async def bonus(self, interaction: discord.Interaction):
        """Claim bonus cash."""
        user_id = str(interaction.user.id)

        try:
            await self.acquire_lock(user_id)

            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return

            claimed_bonus = user_data.get("claimed_bonus")
            if claimed_bonus is not None and claimed_bonus != "None":
                claimed_bonus = datetime.fromisoformat(str(claimed_bonus))
                if datetime.utcnow() < claimed_bonus + timedelta(minutes=10):
                    cooldowne = claimed_bonus + timedelta(minutes=10)
                    cooldownt = int(cooldowne.timestamp())
                    embed = await cembed(interaction,
                        description=f"⏰ {interaction.user.mention}: You can claim a bonus again <t:{cooldownt}:R>.",
                        color=0xff6464
                    )
                    await interaction.followup.send(embed=embed)
                    return

            current_time = datetime.utcnow()
            async with self.pool() as conn:
                await conn.execute(
                    "UPDATE economy SET claimed_bonus = $1 WHERE user_id = $2",
                    current_time, user_id
                )

            cache_key = f"economy:{user_id}"
            cached_data = await self.redis.hgetall(cache_key)
            if cached_data:
                await self.redis.hset(cache_key, "claimed_bonus", current_time.isoformat())
            else:
                await self.redis.hset(cache_key, mapping={
                    "claimed_bonus": current_time.isoformat(),
                    "cash": "0",
                    "bank": "0",
                    "bank_limit": "0"
                })
            await self.redis.expire(cache_key, 300)

            embed = await cembed(
                interaction,
                description=f"{interaction.user.mention}: Choose a button to reveal your prize!"
            )

            class BonusView(ui.View):
                def __init__(self, user: discord.User, pool, redis):
                    super().__init__(timeout=240)
                    self.user = user
                    self.prizes = [random.randint(200, 1000) for _ in range(3)]
                    self.clicked = False
                    self.pool = pool
                    self.redis = redis

                @ui.button(label="\u200B", style=discord.ButtonStyle.primary, custom_id="button_1", row=0)
                async def button_1(self, interaction: discord.Interaction, button: ui.Button):
                    await self.handle_button_click(interaction, button, 0)

                @ui.button(label="\u200B", style=discord.ButtonStyle.primary, custom_id="button_2", row=0)
                async def button_2(self, interaction: discord.Interaction, button: ui.Button):
                    await self.handle_button_click(interaction, button, 1)

                @ui.button(label="\u200B", style=discord.ButtonStyle.primary, custom_id="button_3", row=0)
                async def button_3(self, interaction: discord.Interaction, button: ui.Button):
                    await self.handle_button_click(interaction, button, 2)

                async def handle_button_click(self, interaction: discord.Interaction, button: ui.Button, index: int):
                    if interaction.user != self.user:
                        await interaction.response.send_message("This bonus is not for you!", ephemeral=True)
                        return
                    if self.clicked:
                        await interaction.response.send_message("You've already claimed your bonus!", ephemeral=True)
                        return

                    self.clicked = True

                    for i, child in enumerate(self.children):
                        child.disabled = True
                        child.label = f"{self.prizes[i]} 💵"
                        if i == index:
                            child.style = discord.ButtonStyle.success
                        else:
                            child.style = discord.ButtonStyle.secondary

                    embed = interaction.message.embeds[0]
                    embed.description = f"🎉 {self.user.mention}: You won **{self.prizes[index]}** 💵!"
                    embed.color = 0xa4ec7c
                    await interaction.response.edit_message(embed=embed, view=self)

                    async with self.pool() as conn:
                        await conn.execute(
                            "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                            self.prizes[index], str(self.user.id)
                        )

                    cache_key = f"economy:{self.user.id}"
                    cached_data = await self.redis.hgetall(cache_key)
                    if cached_data:
                        new_cash = int(cached_data["cash"]) + self.prizes[index]
                        await self.redis.hset(cache_key, "cash", str(new_cash))
                    else:
                        await self.redis.hset(cache_key, mapping={
                            "cash": str(self.prizes[index]),
                            "bank": "0",
                            "bank_limit": "0"
                        })
                    await self.redis.expire(cache_key, 300)

                async def on_timeout(self):
                    for child in self.children:
                        child.disabled = True
                    await self.message.edit(view=self)

            view = BonusView(interaction.user, self.pool, await self.redis)
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=3)
    async def work(self, interaction: discord.Interaction):
        """Work to earn cash."""

        user_id = str(interaction.user.id)

        try:
            await self.acquire_lock(user_id)

            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return

            last_work = user_data.get("last_work")
            if last_work is not None and last_work != "None":
                last_work = datetime.fromisoformat(str(last_work))
                if datetime.utcnow() < last_work + timedelta(hours=1):
                    cooldown_end = last_work + timedelta(hours=1)
                    cooldown_timestamp = int(cooldown_end.timestamp())
                    embed = await cembed(interaction,
                        description=f"⏰ {interaction.user.mention}: You can work again <t:{cooldown_timestamp}:R>.",
                        color=0xff6464
                    )
                    await interaction.followup.send(embed=embed)
                    return

            jobs = {
                "surgeon": "🩺",
                "chef": "👨‍🍳",
                "engineer": "👨‍🔧",
                "artist": "🎨",
                "teacher": "👩‍🏫",
                "farmer": "👨‍🌾",
                "scientist": "🔬",
                "programmer": "💻",
                "pilot": "✈️",
                "firefighter": "🚒"
            }

            job = random.choice(list(jobs.keys()))
            emoji = jobs[job]
            earnings = random.randint(250, 1000)

            current_time = datetime.utcnow()

            async with self.pool() as conn:
                await conn.execute(
                    "UPDATE economy SET cash = cash + $1, last_work = $2 WHERE user_id = $3",
                    earnings, current_time, user_id
                )

            await self.redis.delete(f"economy:{user_id}")

            embed = await cembed(interaction,
                description=f"{emoji} {interaction.user.mention}: You were working as a **{job}** and received **{earnings}** 💵",
                color=0xa4ec7c
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @bank.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(amount="The amount of cash to deposit.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=3)
    async def deposit(self, interaction: discord.Interaction, amount: str):
        """Deposit cash into your bank."""
        user_id = str(interaction.user.id)

        try:
            await self.acquire_lock(user_id)

            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return

            cash = user_data["cash"]
            bank = user_data["bank"]
            bank_limit = user_data["bank_limit"]

            if amount.lower() == "all":
                depo = min(cash, bank_limit - bank)
                if depo <= 0:
                    if bank >= bank_limit:
                        await interaction.followup.send(messages.warn(interaction.user, "Your bank is already full.\nGet more space with </eco bank expand:1351011345864327209>."))
                    else:
                        await interaction.followup.send(messages.warn(interaction.user, "You don't have any cash to deposit."))
                    return
            else:
                try:
                    depo = self.parse_amount(amount, cash)
                except ValueError as e:
                    await interaction.followup.send(str(e))
                    return

                if depo <= 0:
                    await interaction.followup.send(messages.warn(interaction.user, "You must deposit a positive amount."))
                    return
                if depo > cash:
                    await interaction.followup.send(messages.warn(interaction.user, "You don't have enough cash to deposit that amount."))
                    return
                if bank + depo > bank_limit:
                    await interaction.followup.send(messages.warn(interaction.user, "Depositing this amount exceeds your bank limit.\nGet more space with </eco bank expand:1351011345864327209>."))
                    return

            async with self.pool() as conn:
                await conn.execute(
                    "UPDATE economy SET cash = cash - $1, bank = bank + $2 WHERE user_id = $3",
                    depo, depo, user_id
                )

            await self.redis.delete(f"economy:{user_id}")

            embed = await cembed(
                interaction,
                description=f"💰 {interaction.user.mention}: Deposited **{depo:,}** 💵"
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def cooldowns(self, interaction: discord.Interaction):
        """Check your cooldowns."""
        try:
            user_id = str(interaction.user.id)
            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return

            claimed_bonus = user_data.get("claimed_bonus")
            if claimed_bonus is None or claimed_bonus == "None":
                bonus_cooldown = "`Available`"
                bonus_reward = "<:pointdrl:1318643571317801040> 250 - 1,000 💵"
            else:
                claimed_bonus = datetime.fromisoformat(str(claimed_bonus))
                if datetime.utcnow() < claimed_bonus + timedelta(minutes=10):
                    cooldown_end = claimed_bonus + timedelta(minutes=10)
                    cooldown_timestamp = int(cooldown_end.timestamp())
                    bonus_cooldown = f"<t:{cooldown_timestamp}:R>"
                else:
                    bonus_cooldown = "`Available`"
                bonus_reward = "<:pointdrl:1318643571317801040> 250 - 1,000 💵"

            last_work = user_data.get("last_work")
            if last_work is None or last_work == "None":
                work_cooldown = "`Available`"
                work_reward = "<:pointdrl:1318643571317801040> 500 - 1,500 💵"
            else:
                last_work = datetime.fromisoformat(str(last_work))
                if datetime.utcnow() < last_work + timedelta(hours=1):
                    cooldown_end = last_work + timedelta(hours=1)
                    cooldown_timestamp = int(cooldown_end.timestamp())
                    work_cooldown = f"<t:{cooldown_timestamp}:R>"
                else:
                    work_cooldown = "`Available`"
                work_reward = "<:pointdrl:1318643571317801040> 500 - 1,500 💵"

            last_rob = user_data.get("last_rob")
            if last_rob is None or last_rob == "None":
                rob_cooldown = "`Available`"
                rob_reward = "<:pointdrl:1318643571317801040> Steal 10% of cash"
            else:
                last_rob = datetime.fromisoformat(str(last_rob))
                if datetime.utcnow() < last_rob + timedelta(hours=3):
                    cooldown_end = last_rob + timedelta(hours=3)
                    cooldown_timestamp = int(cooldown_end.timestamp())
                    rob_cooldown = f"<t:{cooldown_timestamp}:R>"
                else:
                    rob_cooldown = "`Available`"
                rob_reward = "<:pointdrl:1318643571317801040> Steal 10% of cash"

            last_fish = user_data.get("last_fish")
            if last_fish is None or last_fish == "None":
                fish_cooldown = "`Available`"
                fish_reward = "<:pointdrl:1318643571317801040> 0 - 500 💵"
            else:
                last_fish = datetime.fromisoformat(str(last_fish))
                if datetime.utcnow() < last_fish + timedelta(minutes=30):
                    cooldown_end = last_fish + timedelta(minutes=30)
                    cooldown_timestamp = int(cooldown_end.timestamp())
                    fish_cooldown = f"<t:{cooldown_timestamp}:R>"
                else:
                    fish_cooldown = "`Available`"
                fish_reward = "<:pointdrl:1318643571317801040> 0 - 500 💵"

            last_daily = user_data.get("last_daily")
            if last_daily is None or last_daily == "None":
                daily_cooldown = "`Available`"
                daily_reward = "<:pointdrl:1318643571317801040> 15,000 - 20,000 💵"
            else:
                last_daily = datetime.fromisoformat(str(last_daily))
                if datetime.utcnow() < last_daily + timedelta(hours=24):
                    cooldown_end = last_daily + timedelta(hours=24)
                    cooldown_timestamp = int(cooldown_end.timestamp())
                    daily_cooldown = f"<t:{cooldown_timestamp}:R>"
                else:
                    daily_cooldown = "`Available`"
                daily_reward = "<:pointdrl:1318643571317801040> 15,000 - 20,000 💵"

            last_vote = user_data.get("last_vote")
            if last_vote is None or last_vote == "None":
                vote_cooldown = "`Available`"
                vote_reward = "<:pointdrl:1318643571317801040> 50,000 💵"
            else:
                last_vote = datetime.fromisoformat(str(last_vote))
                if datetime.utcnow() < last_vote + timedelta(hours=12):
                    cooldown_end = last_vote + timedelta(hours=12)
                    cooldown_timestamp = int(cooldown_end.timestamp())
                    vote_cooldown = f"<t:{cooldown_timestamp}:R>"
                else:
                    vote_cooldown = "`Available`"
                vote_reward = "<:pointdrl:1318643571317801040> 50,000 💵"

            embed = await cembed(
                interaction
            )

            embed.set_author(
                name=f"{interaction.user.name}'s Cooldowns",
                icon_url=interaction.user.display_avatar.url
            )

            embed.add_field(
                name="Bonus (15m)",
                value=f"{bonus_cooldown}\n{bonus_reward}",
                inline=True
            )
            embed.add_field(
                name="Fish (30m)",
                value=f"{fish_cooldown}\n{fish_reward}",
                inline=True
            )
            embed.add_field(
                name="Work (1h)",
                value=f"{work_cooldown}\n{work_reward}",
                inline=True
            )
            embed.add_field(
                name="Rob (3h)",
                value=f"{rob_cooldown}\n{rob_reward}",
                inline=True
            )
            embed.add_field(
                name="Daily (24h)",
                value=f"{daily_cooldown}\n{daily_reward}",
                inline=True
            )
            embed.add_field(
                name="Vote (12h)",
                value=f"{vote_cooldown}\n{vote_reward}",
                inline=True
            )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await error_handler(interaction, e)

    @bank.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(amount="The amount of cash to withdraw.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=3)
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        """Withdraw cash from your bank."""
        user_id = str(interaction.user.id)

        try:
            await self.acquire_lock(user_id)

            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return

            cash = user_data["cash"]
            bank = user_data["bank"]

            try:
                withdraw_amount = self.parse_amount(amount, bank)
            except ValueError as e:
                await interaction.followup.send(str(e))
                return

            if withdraw_amount <= 0:
                await interaction.followup.send(messages.warn(interaction.user, "You must withdraw a positive amount."))
                return
            if withdraw_amount > bank:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have enough money in your bank to withdraw that."))
                return

            async with self.pool() as conn:
                await conn.execute(
                    "UPDATE economy SET cash = cash + $1, bank = bank - $2 WHERE user_id = $3",
                    withdraw_amount, withdraw_amount, user_id
                )

            await self.redis.delete(f"economy:{user_id}")

            embed = await cembed(
                interaction,
                description=f"💸 {interaction.user.mention}: Withdrew **{withdraw_amount:,}** 💵",
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @bank.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(amount="The amount of bank space to purchase.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=5, donor=2)
    async def expand(self, interaction: discord.Interaction, amount: str):
        """Expand your bank limit."""
        user_id = str(interaction.user.id)

        try:
            await self.acquire_lock(user_id)

            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return

            cash = user_data["cash"]

            try:
                expandee = self.parse_amount(amount, cash)
                if expandee <= 0:
                    return
            except ValueError as e:
                await interaction.followup.send(str(e))
                return

            cost = expandee

            if cost > cash:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have enough cash to purchase this bank space."))
                return

            embed = await cembed(
                interaction,
                description=f"<:question:1323072605489467402> {interaction.user.mention}: Are you sure you want to purchase **{expandee}** bank space for **{cost}** 💵?",
            )

            class ExpandView(ui.View):
                def __init__(self, user: discord.User, pool, redis, amount: int, cost: int):
                    super().__init__(timeout=240)
                    self.user = user
                    self.pool = pool
                    self.redis = redis
                    self.amount = amount
                    self.cost = cost

                @ui.button(label="Approve", style=discord.ButtonStyle.green)
                async def approve(self, interaction: discord.Interaction, button: ui.Button):
                    if interaction.user != self.user:
                        await interaction.response.send_message("This confirmation is not for you!", ephemeral=True)
                        return
                    
                    async with self.pool() as conn:
                        current_cash = await conn.fetchval(
                            "SELECT cash FROM economy WHERE user_id = $1",
                            str(self.user.id))
                        
                        if current_cash < self.cost:
                            embed = await cembed(interaction,
                                description=f"❌ {self.user.mention}: You do not have enough cash for this purchase!",
                                color=0xff6b6b
                            )
                            await interaction.response.edit_message(embed=embed, view=None)
                            return
                            
                        await conn.execute(
                            "UPDATE economy SET cash = cash - $1, bank_limit = bank_limit + $2 WHERE user_id = $3",
                            self.cost, self.amount, str(self.user.id)
                        )

                    await self.redis.delete(f"economy:{self.user.id}")

                    embed = await cembed(interaction,
                        description=messages.success(self.user, f"Successfully bought **{self.amount}** bank space for **{self.cost}** 💵"),
                        color=0xa4ec7c
                    )
                    await interaction.response.edit_message(embed=embed, view=None)

                @ui.button(label="Decline", style=discord.ButtonStyle.red)
                async def decline(self, interaction: discord.Interaction, button: ui.Button):
                    if interaction.user != self.user:
                        await interaction.response.send_message("This confirmation is not for you!", ephemeral=True)
                        return

                    await interaction.response.defer()
                    await interaction.delete_original_response()

            view = ExpandView(interaction.user, self.pool, await self.redis, expandee, cost)
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    async def leaderboard(self, interaction: discord.Interaction):
        """View the economy leaderboard."""
        try:
            async with self.pool() as conn:
                rows = await conn.fetch(
                    "SELECT user_id, cash, bank FROM economy ORDER BY (cash + bank) DESC LIMIT 500"
                )

            leaderboard_data = []
            for row in rows:
                user_id = row["user_id"]
                total = row["cash"] + row["bank"]
                leaderboard_data.append((user_id, total))

            leaderboard_pages = []
            entries_per_page = 10
            for i in range(0, len(leaderboard_data), entries_per_page):
                page = leaderboard_data[i:i + entries_per_page]
                leaderboard_pages.append(page)

            class LeaderboardView(discord.ui.View):
                def __init__(self, interaction: discord.Interaction, leaderboard_pages: list):
                    super().__init__(timeout=240)
                    self.interaction = interaction
                    self.leaderboard_pages = leaderboard_pages
                    self.current_page = 0
                    self.embed = None
                    self.update_button_states()

                async def initialize_embed(self):
                    self.embed = await cembed(self.interaction, title="Heist Leaderboard")
                    await self.update_content()

                def update_button_states(self):
                    self.previous_button.disabled = self.current_page == 0
                    self.next_button.disabled = self.current_page == len(self.leaderboard_pages) - 1

                async def update_content(self):
                    page = self.leaderboard_pages[self.current_page]
                    description = ""
                    for idx, (user_id, total) in enumerate(page, start=1 + (self.current_page * 10)):
                        user = self.interaction.client.get_user(int(user_id))
                        username = user.name if user else f"<@{user_id}>"
                        description += f"{idx}. **{username}** - {total:,} 💵\n"

                    self.embed.description = description
                    self.embed.set_footer(text=f"Page: {self.current_page + 1}/{len(self.leaderboard_pages)} (500 entries)")
                    await self.interaction.edit_original_response(embed=self.embed, view=self)

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:left:1265476224742850633>"), style=discord.ButtonStyle.primary, custom_id="leaderboardleft")
                async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                        return

                    if self.current_page > 0:
                        self.current_page -= 1
                        await interaction.response.defer()
                        self.update_button_states()
                        await self.update_content()

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:right:1265476229876678768>"), style=discord.ButtonStyle.primary, custom_id="leaderboardright")
                async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                        return

                    if self.current_page < len(self.leaderboard_pages) - 1:
                        self.current_page += 1
                        await interaction.response.defer()
                        self.update_button_states()
                        await self.update_content()

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:sort:1317260205381386360>"), style=discord.ButtonStyle.secondary, custom_id="leaderboardskip")
                async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                        return

                    class GoToPageModal(discord.ui.Modal, title="Go to Page"):
                        def __init__(self, view):
                            super().__init__()
                            self.view = view
                            self.page_number = discord.ui.TextInput(
                                label="Navigate to page",
                                placeholder=f"Enter a page number (1-{len(self.view.leaderboard_pages)})",
                                min_length=1,
                                max_length=len(str(len(self.view.leaderboard_pages)))
                            )
                            self.add_item(self.page_number)

                        async def on_submit(self, interaction: discord.Interaction):
                            try:
                                page = int(self.page_number.value) - 1
                                if page < 0 or page >= len(self.view.leaderboard_pages):
                                    raise ValueError
                                self.view.current_page = page
                                self.view.update_button_states()
                                await self.view.update_content()
                                await interaction.response.defer()
                            except ValueError:
                                await interaction.response.send_message("Invalid choice, cancelled.", ephemeral=True)

                    modal = GoToPageModal(self)
                    await interaction.response.send_modal(modal)

                @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:bin:1317214464231079989>"), style=discord.ButtonStyle.danger, custom_id="leaderboarddelete")
                async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.interaction.user.id:
                        await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
                        return

                    await interaction.response.defer()
                    await interaction.delete_original_response()

            view = LeaderboardView(interaction, leaderboard_pages)
            await view.initialize_embed()
            await view.update_content()
        except Exception as e:
            await error_handler(interaction, e)

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user you want to rob.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=3)
    async def rob(self, interaction: discord.Interaction, user: discord.User):
        "Rob another user for their cash."
        user_id = str(interaction.user.id)
        target_id = str(user.id)

        try:
            await self.acquire_lock(user_id)
            await self.acquire_lock(target_id)

            if user_id == target_id:
                embed = await cembed(interaction, description=f"💀 {interaction.user.mention}: bruh what.")
                await interaction.followup.send(embed=embed)
                return

            user_data = await self.fetch_data(user_id)
            target_data = await self.fetch_data(target_id)

            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return
            if target_data is None:
                await interaction.followup.send(messages.warn(interaction.user, f"{user.name} doesn't have a wallet yet."))
                return

            last_rob = user_data.get("last_rob")
            if last_rob is not None and last_rob != "None":
                last_rob = datetime.fromisoformat(str(last_rob))
                if datetime.utcnow() < last_rob + timedelta(hours=3):
                    cooldown_end = last_rob + timedelta(hours=3)
                    cooldown_timestamp = int(cooldown_end.timestamp())
                    embed = await cembed(interaction, description=f"⏰ {interaction.user.mention}: You can rob again <t:{cooldown_timestamp}:R>.")
                    await interaction.followup.send(embed=embed)
                    return

            if user_data["bank"] < 50000:
                embed = await cembed(interaction, description=messages.warn(interaction.user, "You need at least **50,000** 💵 in your bank to rob someone."))
                await interaction.followup.send(embed=embed)
                return

            if target_data["cash"] <= 0:
                embed = await cembed(interaction, description=f"💀 {interaction.user.mention}: **{user.name}** has no cash to rob.")
                await interaction.followup.send(embed=embed)
                return

            success = random.choice([True, False])
            current_time = datetime.utcnow()

            if success:
                stolen_amount = int(target_data["cash"] * 0.10)
                async with self.pool() as conn:
                    async with conn.transaction():
                        target_cash = await conn.fetchval("SELECT cash FROM economy WHERE user_id = $1", target_id)
                        if target_cash < stolen_amount:
                            stolen_amount = target_cash

                        await conn.execute(
                            "UPDATE economy SET cash = cash - $1 WHERE user_id = $2",
                            stolen_amount, target_id
                        )
                        await conn.execute(
                            "UPDATE economy SET cash = cash + $1, last_rob = $2 WHERE user_id = $3",
                            stolen_amount, current_time, user_id
                        )

                await self.redis.delete(f"economy:{user_id}")
                await self.redis.delete(f"economy:{target_id}")

                embed = await cembed(interaction, description=messages.success(interaction.user, f"You stole **{stolen_amount:,}** 💵 from **{user.name}**."))
                await interaction.followup.send(embed=embed)

                try:
                    await user.send(f"**{interaction.user.name}** ({interaction.user.id}) has just robbed you out of **{stolen_amount:,}** 💵, damn..")
                except Exception:
                    pass
            else:
                lost_amount = int(user_data["bank"] * 0.05)
                async with self.pool() as conn:
                    await conn.execute(
                        "UPDATE economy SET bank = bank - $1, last_rob = $2 WHERE user_id = $3",
                        lost_amount, current_time, user_id
                    )

                await self.redis.delete(f"economy:{user_id}")

                embed = await cembed(interaction, description=messages.warn(interaction.user, f"Caught, you couldn't steal money from **{user.mention}**\n> You lost **5%** (`{lost_amount:,}`) of your **bank** balance."))
                await interaction.followup.send(embed=embed)

                try:
                    await user.send(f"**{interaction.user.name}** ({interaction.user.id}) has just attempted to rob you (but failed 😭).")
                except Exception:
                    pass
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)
            await self.release_lock(target_id)

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(amount="The amount to play with.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=5, donor=3)
    async def mines(self, interaction: discord.Interaction, amount: str):
        """Gamble on mines."""
        user_id = str(interaction.user.id)
        try:
            await self.acquire_lock(user_id)
            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return
            try:
                amount_to_play = self.parse_amount(amount, user_data["cash"])
            except ValueError as e:
                await interaction.followup.send(str(e))
                return
            if amount_to_play <= 0:
                await interaction.followup.send(messages.warn(interaction.user, "You must play a positive amount."))
                return
            if amount_to_play > user_data["cash"]:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have enough cash to play that amount."))
                return
            async with self.pool() as conn:
                await conn.execute(
                    "UPDATE economy SET cash = cash - $1 WHERE user_id = $2",
                    amount_to_play, user_id
                )
            await self.redis.delete(f"economy:{user_id}")
            tiles = ["💣"] * 3 + ["🟩"] * 13
            random.shuffle(tiles)
            revealed = [False] * 16
            multiplier = 1.00
            multiplier_increments = [1.10, 1.52, 1.97, 2.54, 2.75, 3.10, 3.50, 4.00, 5.00]
            winnings = 0
            clicks = 0
            embed = await cembed(
                interaction,
                title=f"Playing Mines with {amount_to_play:,} 💵 and 3 💣",
            )
            embed.add_field(name="Fields", value="0/13", inline=False)
            embed.add_field(name="Multiplier", value=f"{multiplier:.2f}x", inline=True)
            embed.add_field(name="Winnings", value=f"{winnings:,} 💵", inline=True)
            class MinesView(discord.ui.View):
                def __init__(self, tiles, revealed, multiplier, winnings, clicks, amount_to_play, user_id, pool, redis):
                    super().__init__(timeout=240)
                    self.tiles = tiles
                    self.revealed = revealed
                    self.multiplier = multiplier
                    self.winnings = winnings
                    self.clicks = clicks
                    self.amount_to_play = amount_to_play
                    self.user_id = user_id
                    self._pool = pool
                    self._redis = redis
                    self.game_finished = False
                    self.update_buttons()
                async def on_timeout(self):
                    if self.game_finished:
                        return
                    self.disable_all_buttons()
                    await self.message.edit(view=self)
                    async with self._pool() as conn:
                        await conn.execute(
                            "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                            self.amount_to_play, self.user_id
                        )
                    await self._redis.delete(f"economy:{self.user_id}")
                    dm_key = f"dm_limit:{self.user_id}"
                    current_dm_count = await self._redis.get(dm_key)
                    if current_dm_count is None:
                        current_dm_count = 0
                    else:
                        current_dm_count = int(current_dm_count)
                    if current_dm_count < 3:
                        try:
                            user = await interaction.client.fetch_user(int(self.user_id))
                            if user:
                                dm_embed = await cembed(interaction,
                                    title="💵 Refund Notice",
                                    description=f"You have been refunded **{self.amount_to_play:,}** 💵 due to your Mines game reaching inactivity timeout.",
                                    color=discord.Color.gold()
                                )
                                await user.send(embed=dm_embed)
                                await self._redis.set(dm_key, current_dm_count + 1, ex=600)
                        except Exception as e:
                            print(f"Failed to send DM: {e}")
                    else:
                        print(f"User {self.user_id} has reached the DM limit. No DM sent.")
                def update_buttons(self):
                    self.clear_items()
                    for i in range(16):
                        if self.revealed[i]:
                            if self.tiles[i] == "💣":
                                button = discord.ui.Button(
                                    label="\u200B",
                                    style=discord.ButtonStyle.danger,
                                    emoji="💣",
                                    disabled=True
                                )
                            else:
                                button = discord.ui.Button(
                                    label="\u200B",
                                    style=discord.ButtonStyle.success,
                                    disabled=True
                                )
                        else:
                            button = discord.ui.Button(
                                label="\u200B",
                                style=discord.ButtonStyle.secondary,
                                custom_id=str(i)
                            )
                            button.callback = self.on_button_click
                        self.add_item(button)
                        if (i + 1) % 4 == 0 and i != 15:
                            if i == 3:
                                cashout_button = discord.ui.Button(
                                    label="Cashout",
                                    style=discord.ButtonStyle.green,
                                    custom_id="cashout"
                                )
                                cashout_button.callback = self.on_cashout
                                self.add_item(cashout_button)
                            elif i == 7:
                                exit_button = discord.ui.Button(
                                    label="Exit",
                                    style=discord.ButtonStyle.red,
                                    custom_id="exit"
                                )
                                exit_button.callback = self.on_exit
                                self.add_item(exit_button)
                            elif i == 11:
                                soon_button = discord.ui.Button(
                                    label="Soon",
                                    style=discord.ButtonStyle.secondary,
                                    disabled=True
                                )
                                self.add_item(soon_button)
                async def on_button_click(self, interaction: discord.Interaction):
                    if self.game_finished:
                        await interaction.response.send_message("This game has already ended.", ephemeral=True)
                        return
                    if interaction.user.id != int(self.user_id):
                        await interaction.response.send_message("This game is not for you!", ephemeral=True)
                        return
                    index = int(interaction.data["custom_id"])
                    if self.revealed[index]:
                        await interaction.response.defer()
                        return
                    self.revealed[index] = True
                    if self.tiles[index] == "💣":
                        for i, tile in enumerate(self.tiles):
                            if tile == "💣":
                                self.revealed[i] = True
                        self.update_buttons()
                        self.disable_all_buttons()
                        self.game_finished = True
                        await interaction.response.edit_message(view=self)
                        embed = await cembed(interaction,
                            description=f"💥 {interaction.user.mention}: You hit a mine and lost **{self.amount_to_play:,}** 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{user_data['cash'] - self.amount_to_play:,}** 💵",
                            color=0xff6464
                        )
                        await interaction.followup.send(embed=embed)
                        return
                    else:
                        self.clicks += 1
                        if self.clicks < len(multiplier_increments):
                            self.multiplier = multiplier_increments[self.clicks - 1]
                        else:
                            self.multiplier = multiplier_increments[-1]
                        self.winnings = int(self.amount_to_play * self.multiplier)
                        embed = interaction.message.embeds[0]
                        embed.set_field_at(
                            0,
                            name="Fields",
                            value=f"{self.clicks}/12",
                            inline=False
                        )
                        embed.set_field_at(
                            1,
                            name="Multiplier",
                            value=f"{self.multiplier:.2f}x",
                            inline=True
                        )
                        embed.set_field_at(
                            2,
                            name="Winnings",
                            value=f"{self.winnings:,} 💵",
                            inline=True
                        )
                        self.update_buttons()
                        await interaction.response.edit_message(embed=embed, view=self)
                async def on_cashout(self, interaction: discord.Interaction):
                    if self.game_finished:
                        await interaction.response.send_message("This game has already ended.", ephemeral=True)
                        return
                    if interaction.user.id != int(self.user_id):
                        await interaction.response.send_message("This game is not for you!", ephemeral=True)
                        return
                    if self.winnings == 0:
                        await interaction.response.send_message(
                            f"<:warning:1350239604925530192> {interaction.user.mention}: You can't cashout already.",
                            ephemeral=True
                        )
                        return
                    async with self._pool() as conn:
                        await conn.execute(
                            "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                            self.winnings, self.user_id
                        )
                    await self._redis.delete(f"economy:{self.user_id}")
                    embed = await cembed(interaction,
                        description=messages.success(interaction.user, f"You've successfully collected **{self.winnings:,}** 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{user_data['cash'] - self.amount_to_play + self.winnings:,}** 💵"),
                        color=0xa4ec7c
                    )
                    self.game_finished = True
                    self.disable_all_buttons()
                    await interaction.response.edit_message(view=self)
                    await interaction.followup.send(embed=embed)
                async def on_exit(self, interaction: discord.Interaction):
                    if self.game_finished:
                        await interaction.response.send_message("This game has already ended.", ephemeral=True)
                        return
                    if interaction.user.id != int(self.user_id):
                        await interaction.response.send_message("This game is not for you!", ephemeral=True)
                        return
                    async with self._pool() as conn:
                        await conn.execute(
                            "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                            self.amount_to_play, self.user_id
                        )
                    await self._redis.delete(f"economy:{self.user_id}")
                    embed = await cembed(interaction,
                        description=messages.success(interaction.user, f"Your bet of **{self.amount_to_play:,}** 💵 has been returned."),
                        color=0xa4ec7c
                    )
                    self.game_finished = True
                    self.disable_all_buttons()
                    await interaction.response.edit_message(view=self)
                    await interaction.followup.send(embed=embed)
                def disable_all_buttons(self):
                    for item in self.children:
                        if isinstance(item, discord.ui.Button):
                            item.disabled = True
            view = MinesView(tiles, revealed, multiplier, winnings, clicks, amount_to_play, user_id, self.pool, await self.redis)
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(amount="The amount to play with.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=5, donor=3)
    async def towers(self, interaction: discord.Interaction, amount: str):
        """Gamble on towers."""
        user_id = str(interaction.user.id)
        try:
            await self.acquire_lock(user_id)
            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return
            try:
                amount_to_play = self.parse_amount(amount, user_data["cash"])
            except ValueError as e:
                await interaction.followup.send(str(e))
                return
            if amount_to_play <= 0:
                await interaction.followup.send(messages.warn(interaction.user, "You must play a positive amount."))
                return
            if amount_to_play > user_data["cash"]:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have enough cash to play that amount."))
                return
            async with self.pool() as conn:
                await conn.execute(
                    "UPDATE economy SET cash = cash - $1 WHERE user_id = $2",
                    amount_to_play, user_id
                )
            await self.redis.delete(f"economy:{user_id}")
            rows = 5
            columns = 3
            current_row = rows
            current_winnings = amount_to_play
            game_over = False
            has_cashed_out = False
            bomb_positions = []
            multipliers = []
            for row in range(rows):
                bomb_position = random.randint(0, columns - 1)
                bomb_positions.append(bomb_position)
                if row == rows - 1:
                    multiplier = round(random.uniform(1.5, 1.8), 2)
                elif row == rows - 2:
                    multiplier = round(random.uniform(2.0, 2.5), 2)
                elif row == rows - 3:
                    multiplier = round(random.uniform(3.0, 3.8), 2)
                elif row == rows - 4:
                    multiplier = round(random.uniform(5.0, 6.5), 2)
                elif row == rows - 5:
                    multiplier = round(random.uniform(8.0, 10.0), 2)
                else:
                    multiplier = round(random.uniform(12.0, 15.0), 2)
                multipliers.append(multiplier)
            embed = await cembed(
                interaction,
                title=f"Playing Towers with {amount_to_play:,} 💵",
            )
            embed.add_field(name="Level", value=f"{rows - current_row}/{rows}", inline=False)
            embed.add_field(name="Multiplier", value=f"{1.00:.2f}x", inline=True)
            embed.add_field(name="Winnings", value=f"{current_winnings:,} 💵", inline=True)
            class TowersView(discord.ui.View):
                def __init__(self, rows, columns, current_row, current_winnings, game_over, has_cashed_out, bomb_positions, multipliers, amount_to_play, user_id, pool, redis):
                    super().__init__(timeout=240)
                    self.rows = rows
                    self.columns = columns
                    self.current_row = current_row
                    self.current_winnings = current_winnings
                    self.game_over = game_over
                    self.has_cashed_out = has_cashed_out
                    self.bomb_positions = bomb_positions
                    self.multipliers = multipliers
                    self.amount_to_play = amount_to_play
                    self.user_id = user_id
                    self._pool = pool
                    self._redis = redis
                    self.current_multiplier = 1.00
                    self.first_click = True
                    self.revealed = [[False for _ in range(columns)] for _ in range(rows)]
                    self.update_buttons()
                async def on_timeout(self):
                    if self.game_over:
                        return
                    self.disable_all_buttons()
                    await self.message.edit(view=self)
                    async with self._pool() as conn:
                        await conn.execute(
                            "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                            self.amount_to_play, self.user_id
                        )
                    await self._redis.delete(f"economy:{self.user_id}")
                    dm_key = f"dm_limit:{self.user_id}"
                    current_dm_count = await self._redis.get(dm_key)
                    if current_dm_count is None:
                        current_dm_count = 0
                    else:
                        current_dm_count = int(current_dm_count)
                    if current_dm_count < 3:
                        try:
                            user = await interaction.client.fetch_user(int(self.user_id))
                            if user:
                                dm_embed = await cembed(interaction,
                                    title="💵 Refund Notice",
                                    description=f"You have been refunded **{self.amount_to_play:,}** 💵 due to your Towers game reaching inactivity timeout.",
                                    color=discord.Color.gold()
                                )
                                await user.send(embed=dm_embed)
                                await self._redis.set(dm_key, current_dm_count + 1, ex=600)
                        except Exception as e:
                            print(f"Failed to send DM: {e}")
                    else:
                        print(f"User {self.user_id} has reached the DM limit. No DM sent.")
                def update_buttons(self):
                    self.clear_items()
                    for row in range(self.rows):
                        for col in range(self.columns):
                            if self.revealed[row][col]:
                                if col == self.bomb_positions[row]:
                                    button = discord.ui.Button(
                                        label="\u200B",
                                        style=discord.ButtonStyle.danger,
                                        emoji="💣",
                                        row=row,
                                        disabled=True
                                    )
                                else:
                                    button = discord.ui.Button(
                                        label="\u200B",
                                        style=discord.ButtonStyle.success,
                                        row=row,
                                        disabled=True
                                    )
                            else:
                                button = discord.ui.Button(
                                    label="\u200B",
                                    style=discord.ButtonStyle.secondary,
                                    row=row,
                                    custom_id=f"{row}_{col}",
                                    disabled=(row != self.current_row - 1 or self.game_over)
                                )
                                button.callback = self.on_button_click
                            self.add_item(button)
                    if self.columns * self.rows < 15:
                        for _ in range(15 - (self.columns * self.rows)):
                            self.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label="\u200B", disabled=True))
                    cashout_button = discord.ui.Button(
                        label="Cashout",
                        style=discord.ButtonStyle.green,
                        custom_id="cashout",
                        disabled=self.game_over or self.first_click
                    )
                    cashout_button.callback = self.on_cashout
                    self.add_item(cashout_button)
                    exit_button = discord.ui.Button(
                        label="Exit",
                        style=discord.ButtonStyle.red,
                        custom_id="exit",
                        disabled=self.game_over or not self.first_click
                    )
                    exit_button.callback = self.on_exit
                    self.add_item(exit_button)
                    soon_button = discord.ui.Button(
                        label="Soon",
                        style=discord.ButtonStyle.secondary,
                        disabled=True
                    )
                    self.add_item(soon_button)
                async def on_button_click(self, interaction: discord.Interaction):
                    if (interaction.user.id != int(self.user_id) or self.game_over or int(interaction.data["custom_id"].split("_")[0]) != self.current_row - 1):
                        if interaction.user.id != int(self.user_id):
                            await interaction.response.send_message("This game is not for you!", ephemeral=True)
                        elif self.game_over:
                            await interaction.response.send_message("This game has already ended.", ephemeral=True)
                        else:
                            await interaction.response.defer()
                        return

                    row = int(interaction.data["custom_id"].split("_")[0])
                    col = int(interaction.data["custom_id"].split("_")[1])
                    self.revealed[row][col] = True
                    if self.first_click:
                        self.first_click = False
                    if col == self.bomb_positions[row]:
                        for r in range(self.rows):
                            if r <= self.current_row - 1:
                                self.revealed[r][self.bomb_positions[r]] = True
                        self.update_buttons()
                        self.game_over = True
                        self.disable_all_buttons()
                        await interaction.response.edit_message(view=self)
                        embed = await cembed(interaction,
                            description=f"💥 {interaction.user.mention}: You hit a bomb and lost **{self.amount_to_play:,}** 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{user_data['cash'] - self.amount_to_play:,}** 💵",
                            color=0xff6464
                        )
                        await interaction.followup.send(embed=embed)
                        return
                    else:
                        self.current_multiplier = self.multipliers[row]
                        self.current_winnings = int(self.amount_to_play * self.current_multiplier)
                        self.current_row -= 1
                        embed = interaction.message.embeds[0]
                        embed.set_field_at(
                            0,
                            name="Level",
                            value=f"{rows - self.current_row}/{rows}",
                            inline=False
                        )
                        embed.set_field_at(
                            1,
                            name="Multiplier",
                            value=f"{self.current_multiplier:.2f}x",
                            inline=True
                        )
                        embed.set_field_at(
                            2,
                            name="Winnings",
                            value=f"{self.current_winnings:,} 💵",
                            inline=True
                        )
                        self.update_buttons()
                        await interaction.response.edit_message(embed=embed, view=self)
                async def on_cashout(self, interaction: discord.Interaction):
                    if self.game_over:
                        await interaction.response.send_message("This game has already ended.", ephemeral=True)
                        return
                    if interaction.user.id != int(self.user_id):
                        await interaction.response.send_message("This game is not for you!", ephemeral=True)
                        return
                    if self.first_click:
                        await interaction.response.send_message(
                            f"<:warning:1350239604925530192> {interaction.user.mention}: You can't cashout already.",
                            ephemeral=True
                        )
                        return
                    async with self._pool() as conn:
                        await conn.execute(
                            "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                            self.current_winnings, self.user_id
                        )
                    await self._redis.delete(f"economy:{self.user_id}")
                    embed = await cembed(interaction,
                        description=messages.success(interaction.user, f"You've successfully collected **{self.current_winnings:,}** 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{user_data['cash'] - self.amount_to_play + self.current_winnings:,}** 💵"),
                        color=0xa4ec7c
                    )
                    self.game_over = True
                    self.disable_all_buttons()
                    await interaction.response.edit_message(view=self)
                    await interaction.followup.send(embed=embed)
                async def on_exit(self, interaction: discord.Interaction):
                    if self.game_over:
                        await interaction.response.send_message("This game has already ended.", ephemeral=True)
                        return
                    if interaction.user.id != int(self.user_id):
                        await interaction.response.send_message("This game is not for you!", ephemeral=True)
                        return
                    if not self.first_click:
                        await interaction.response.send_message(
                            f"<:warning:1350239604925530192> {interaction.user.mention}: You can't exit after starting to play.",
                            ephemeral=True
                        )
                        return
                    async with self._pool() as conn:
                        await conn.execute(
                            "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                            self.amount_to_play, self.user_id
                        )
                    await self._redis.delete(f"economy:{self.user_id}")
                    embed = await cembed(interaction,
                        description=messages.success(interaction.user, f"Your bet of **{self.amount_to_play:,}** 💵 has been returned."),
                        color=0xa4ec7c
                    )
                    self.game_over = True
                    self.disable_all_buttons()
                    await interaction.response.edit_message(view=self)
                    await interaction.followup.send(embed=embed)
                def disable_all_buttons(self):
                    for item in self.children:
                        if isinstance(item, discord.ui.Button):
                            item.disabled = True
            view = TowersView(rows, columns, current_row, current_winnings, game_over, has_cashed_out, bomb_positions, multipliers, amount_to_play, user_id, self.pool, await self.redis)
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message
        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(amount="The amount to play with.")
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=5, donor=3)
    async def blackjack(self, interaction: discord.Interaction, amount: str):
        """Gamble on Blackjack."""
        user_id = str(interaction.user.id)

        def calculate_hand_value(hand):
            value = 0
            aces = 0
            for card in hand:
                if card[0] in ['J', 'Q', 'K']:
                    value += 10
                elif card[0] == 'A':
                    value += 11
                    aces += 1
                else:
                    value += int(card[0])
            while value > 21 and aces:
                value -= 10
                aces -= 1
            return value

        try:
            await self.acquire_lock(user_id)

            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return

            try:
                amount_to_play = self.parse_amount(amount, user_data["cash"])
            except ValueError as e:
                await interaction.followup.send(str(e))
                return

            if amount_to_play <= 0:
                await interaction.followup.send(messages.warn(interaction.user, "You must play a positive amount."))
                return
            if amount_to_play > user_data["cash"]:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have enough cash to play that amount."))
                return

            async with self.pool() as conn:
                await conn.execute(
                    "UPDATE economy SET cash = cash - $1 WHERE user_id = $2",
                    amount_to_play, user_id
                )

            await self.redis.delete(f"economy:{user_id}")

            cards = {
                'Ac': '1277339621931614431', 'Ad': '1277339638633074829', 'Ah': '1277339670115778613', 'As': '1277339705591201834',
                '2c': '1277336190890279005', '2d': '1277336210049863762', '2h': '1277336231994327050', '2s': '1277336263481102436',
                '3c': '1277336370641113148', '3d': '1277336428807717017', '3h': '1277336449221398528', '3s': '1277336467919863828',
                '4c': '1277336519488700436', '4d': '1277336538308546560', '4h': '1277336555119444020', '4s': '1277336572005580900',
                '5c': '1277336588891721768', '5d': '1277336615597113384', '5h': '1277336674426294283', '5s': '1277336729522667531',
                '6c': '1277336776993935464', '6d': '1277336840487174258', '6h': '1277336896527274007', '6s': '1277337048034054305',
                '7c': '1277337074713755678', '7d': '1277337109761626246', '7h': '1277337138375036979', '7s': '1277339225620086987',
                '8c': '1277339252891451462', '8d': '1277339307375464499', '8h': '1277339330247000124', '8s': '1277339355916140625',
                '9c': '1277339388057092106', '9d': '1277339409724739788', '9h': '1277339428519542906', '9s': '1277339450321539072',
                '10c': '1277339485419339776', '10d': '1277339513815044221', '10h': '1277339543128768522', '10s': '1277339572711456908',
                'Jc': '1277339792606105713', 'Jd': '1277339978266837093', 'Jh': '1277340066724843561', 'Js': '1277340212183433409',
                'Qc': '1277351069097398332', 'Qd': '1277351112181153914', 'Qh': '1277351159719264377', 'Qs': '1277351187770769408',
                'Kc': '1277350916592373761', 'Kd': '1277350949664325753', 'Kh': '1277350973676847154', 'Ks': '1277351034452316260',
            }

            deck = list(cards.keys())
            random.shuffle(deck)

            player_hand = [deck.pop()]
            dealer_hand = [deck.pop(), deck.pop()]

            embed = await cembed(
                interaction,
                title=f"Playing Blackjack with {amount_to_play:,} 💵", 
                description="-# <:warning:1350239604925530192> Not eligible for timeout refund."
            )
            embed.add_field(
                name=interaction.user.name,
                value="Hit 'Hit' to start the game",
                inline=True
            )
            embed.add_field(
                name="Dealer",
                value=f"<:{dealer_hand[0]}:{cards[dealer_hand[0]]}> <:blankcard:1277804981457518613>",
                inline=True
            )

            class BlackjackView(discord.ui.View):
                def __init__(self, player_hand, dealer_hand, deck, amount_to_play, user_id, pool, redis):
                    super().__init__(timeout=240)
                    self.player_hand = player_hand
                    self.dealer_hand = dealer_hand
                    self.deck = deck
                    self.amount_to_play = amount_to_play
                    self.user_id = user_id
                    self._pool = pool
                    self._redis = redis
                    self.game_started = False
                    self.game_finished = False

                async def on_timeout(self):
                    if self.game_finished:
                        return

                    self.disable_all_items()
                    await self.message.edit(view=self)
                    
                    refund_amount = self.amount_to_play // 2 if not self.game_started else 0
                    
                    async with self._pool() as conn:
                        await conn.execute(
                            "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                            refund_amount, self.user_id
                        )
                    
                    await self._redis.delete(f"economy:{self.user_id}")
                    
                    try:
                        user = await interaction.client.fetch_user(int(self.user_id))
                        if user:
                            if not self.game_started:
                                dm_embed = await cembed(interaction,
                                    title="💵 Partial Refund Notice",
                                    description=f"You have been refunded **{refund_amount:,}** 💵 (50%) due to your Blackjack game timing out during the initial state.\n<:warning:1350239604925530192> Next time you may not receive a refund.",
                                    color=discord.Color.gold()
                                )
                            else:
                                dm_embed = await cembed(interaction,
                                    title="⏱️ Game Timed Out",
                                    description=f"You didn't receive a refund because you already started playing.\n<:warning:1350239604925530192> Next time finish your game to avoid losing money.",
                                    color=discord.Color.red()
                                )
                            await user.send(embed=dm_embed)
                    except discord.Forbidden:
                        pass
                    except Exception as e:
                        print(f"Failed to send DM: {e}")

                @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
                async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != int(self.user_id):
                        await interaction.response.send_message("This game is not for you!", ephemeral=True)
                        return

                    self.game_started = True
                    self.player_hand.append(self.deck.pop())
                    embed = interaction.message.embeds[0]
                    embed.description = "-# <:warning:1350239604925530192> Not eligible for timeout refund."

                    player_value = calculate_hand_value(self.player_hand)
                    dealer_showing_value = calculate_hand_value([self.dealer_hand[0]])

                    embed.set_field_at(
                        0,
                        name=f"{interaction.user.name} ({player_value})",
                        value=" ".join([f"<:{card}:{cards[card]}>" for card in self.player_hand]),
                        inline=True
                    )

                    embed.set_field_at(
                        1,
                        name=f"Dealer ({dealer_showing_value} + ?)",
                        value=f"<:{self.dealer_hand[0]}:{cards[self.dealer_hand[0]]}> <:blankcard:1277804981457518613>",
                        inline=True
                    )

                    for item in self.children:
                        if item.label == "Exit":
                            item.disabled = True

                    if player_value > 21:
                        dealer_value = calculate_hand_value(self.dealer_hand)
                        embed.description = f"> You've busted and lost {self.amount_to_play:,} 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{user_data['cash'] - self.amount_to_play:,}** 💵"
                        embed.color = 0xff6464
                        embed.set_field_at(
                            1,
                            name=f"Dealer ({dealer_value})",
                            value=" ".join([f"<:{card}:{cards[card]}>" for card in self.dealer_hand]),
                            inline=True
                        )

                        self.game_finished = True
                        self.disable_all_items()
                        await self._redis.delete(f"economy:{self.user_id}")
                        await interaction.response.edit_message(embed=embed, view=self)
                        return

                    await interaction.response.edit_message(embed=embed, view=self)

                @discord.ui.button(label="Stand", style=discord.ButtonStyle.green)
                async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != int(self.user_id):
                        await interaction.response.send_message("This game is not for you!", ephemeral=True)
                        return

                    if not self.game_started:
                        await interaction.response.send_message(
                            f"<:warning:1350239604925530192> {interaction.user.mention}: You can't stand before the game starts.",
                            ephemeral=True
                        )
                        return

                    while calculate_hand_value(self.dealer_hand) < 17:
                        self.dealer_hand.append(self.deck.pop())

                    embed = interaction.message.embeds[0]

                    player_value = calculate_hand_value(self.player_hand)
                    dealer_value = calculate_hand_value(self.dealer_hand)

                    embed.set_field_at(
                        0,
                        name=f"{interaction.user.name} ({player_value})",
                        value=" ".join([f"<:{card}:{cards[card]}>" for card in self.player_hand]),
                        inline=True
                    )
                    embed.set_field_at(
                        1,
                        name=f"Dealer ({dealer_value})",
                        value=" ".join([f"<:{card}:{cards[card]}>" for card in self.dealer_hand]),
                        inline=True
                    )

                    async with self._pool() as conn:
                        if player_value > 21:
                            embed.description = f"> You've busted and lost **{self.amount_to_play:,}** 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{user_data['cash'] - self.amount_to_play:,}** 💵"
                            embed.color = 0xff6464
                        elif dealer_value > 21:
                            remaining = user_data['cash'] + (self.amount_to_play * 2)
                            embed.description = f"> Congratulations! You won **{int(self.amount_to_play * 2):,}** 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{remaining:,}** 💵"
                            embed.color = 0xa4ec7c
                            await conn.execute(
                                "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                                self.amount_to_play * 2, self.user_id
                            )
                        elif player_value > dealer_value:
                            remaining = user_data['cash'] + (self.amount_to_play * 2)
                            embed.description = f"> Congratulations! You won **{int(self.amount_to_play * 2):,}** 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{remaining:,}** 💵"
                            embed.color = 0xa4ec7c
                            await conn.execute(
                                "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                                self.amount_to_play * 2, self.user_id
                            )
                        elif player_value < dealer_value:
                            embed.description = f"> You've busted and lost **{self.amount_to_play:,}** 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{user_data['cash'] - self.amount_to_play:,}** 💵"
                            embed.color = 0xff6464
                        else:
                            remaining = user_data['cash'] + self.amount_to_play
                            embed.description = f"> It's a tie!\n-# <:pointdrl:1318643571317801040> Remaining: **{remaining:,}** 💵"
                            embed.color = 0x739db7
                            await conn.execute(
                                "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                                self.amount_to_play, self.user_id
                            )

                    await self._redis.delete(f"economy:{self.user_id}")
                    self.game_finished = True
                    self.disable_all_items()
                    await interaction.response.edit_message(embed=embed, view=self)

                @discord.ui.button(label="Double Down", style=discord.ButtonStyle.gray)
                async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != int(self.user_id):
                        await interaction.response.send_message("This game is not for you!", ephemeral=True)
                        return

                    if not self.game_started:
                        await interaction.response.send_message(
                            f"<:warning:1350239604925530192> {interaction.user.mention}: You can't double down before the game starts.",
                            ephemeral=True
                        )
                        return

                    self.player_hand.append(self.deck.pop())
                    embed = interaction.message.embeds[0]
                    embed.description = "-# <:warning:1350239604925530192> Not eligible for timeout refund."

                    player_value = calculate_hand_value(self.player_hand)

                    embed.set_field_at(
                        0,
                        name=f"{interaction.user.name} ({player_value})",
                        value=" ".join([f"<:{card}:{cards[card]}>" for card in self.player_hand]),
                        inline=True
                    )

                    for item in self.children:
                        if item.label == "Exit":
                            item.disabled = True

                    if player_value > 21:
                        dealer_value = calculate_hand_value(self.dealer_hand)
                        embed.description = f"> You've busted and lost {self.amount_to_play:,} 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{user_data['cash'] - self.amount_to_play:,}** 💵"
                        embed.color = 0xff6464
                        embed.set_field_at(
                            1,
                            name=f"Dealer ({dealer_value})",
                            value=" ".join([f"<:{card}:{cards[card]}>" for card in self.dealer_hand]),
                            inline=True
                        )
                        self.game_finished = True
                        self.disable_all_items()
                        await interaction.response.edit_message(embed=embed, view=self)
                        return

                    while calculate_hand_value(self.dealer_hand) < 17:
                        self.dealer_hand.append(self.deck.pop())

                    dealer_value = calculate_hand_value(self.dealer_hand)
                    embed.set_field_at(
                        1,
                        name=f"Dealer ({dealer_value})",
                        value=" ".join([f"<:{card}:{cards[card]}>" for card in self.dealer_hand]),
                        inline=True
                    )

                    async with self._pool() as conn:
                        if player_value > 21:
                            embed.description = f"> You've busted and lost {self.amount_to_play:,} 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{user_data['cash'] - self.amount_to_play:,}** 💵"
                            embed.color = 0xff6464
                        elif dealer_value > 21:
                            remaining = user_data['cash'] + (self.amount_to_play * 2)
                            embed.description = f"> Congratulations! You won {int(self.amount_to_play * 2):,} 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{remaining:,}** 💵"
                            embed.color = 0xa4ec7c
                            await conn.execute(
                                "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                                self.amount_to_play * 2, self.user_id
                            )
                        elif player_value > dealer_value:
                            remaining = user_data['cash'] + (self.amount_to_play * 2)
                            embed.description = f"> Congratulations! You won {int(self.amount_to_play * 2):,} 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{remaining:,}** 💵"
                            embed.color = 0xa4ec7c
                            await conn.execute(
                                "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                                self.amount_to_play * 2, self.user_id
                            )
                        elif player_value < dealer_value:
                            embed.description = f"> You've busted and lost {self.amount_to_play:,} 💵\n-# <:pointdrl:1318643571317801040> Remaining: **{user_data['cash'] - self.amount_to_play:,}** 💵"
                            embed.color = 0xff6464
                        else:
                            remaining = user_data['cash'] + self.amount_to_play
                            embed.description = f"> It's a tie!\n-# <:pointdrl:1318643571317801040> Remaining: **{remaining:,}** 💵"
                            embed.color = 0x739db7
                            await conn.execute(
                                "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                                self.amount_to_play, self.user_id
                            )

                    await self._redis.delete(f"economy:{self.user_id}")
                    self.game_finished = True
                    self.disable_all_items()
                    await interaction.response.edit_message(embed=embed, view=self)

                @discord.ui.button(label="Exit", style=discord.ButtonStyle.red)
                async def exit(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != int(self.user_id):
                        await interaction.response.send_message("This game is not for you!", ephemeral=True)
                        return

                    async with self._pool() as conn:
                        await conn.execute(
                            "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                            self.amount_to_play, self.user_id
                        )

                    await self._redis.delete(f"economy:{self.user_id}")

                    embed = await cembed(interaction,
                        description=messages.success(interaction.user, f"Your bet of **{self.amount_to_play:,}** 💵 has been returned."),
                        color=0xa4ec7c
                    )
                    self.game_finished = True
                    self.disable_all_items()
                    await interaction.response.edit_message(embed=embed, view=self)

                def disable_all_items(self):
                    for item in self.children:
                        item.disabled = True

            view = BlackjackView(player_hand, dealer_hand, deck, amount_to_play, user_id, self.pool, await self.redis)
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message

        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

    @eco.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(amount="The amount to bet.", side="The side to bet on.")
    @app_commands.choices(side=[
        app_commands.Choice(name="Heads", value="heads"),
        app_commands.Choice(name="Tails", value="tails")
    ])
    @app_commands.check(permissions.is_blacklisted)
    @permissions.requires_perms(embed_links=True)
    @cooldown(default=5, donor=3)
    async def coinflip(self, interaction: discord.Interaction, amount: str, side: str):
        "Bet on a coin flip."
        user_id = str(interaction.user.id)

        try:
            await self.acquire_lock(user_id)

            user_data = await self.fetch_data(user_id)
            if user_data is None:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have a wallet yet. Use </eco wallet:1351011345864327209> to create one."))
                return

            try:
                amount_to_bet = self.parse_amount(amount, user_data["cash"])
            except ValueError as e:
                await interaction.followup.send(str(e))
                return

            if amount_to_bet <= 0:
                await interaction.followup.send(messages.warn(interaction.user, "You must bet a positive amount."))
                return
            if amount_to_bet > user_data["cash"]:
                await interaction.followup.send(messages.warn(interaction.user, "You don't have enough cash to bet that amount."))
                return

            if side.lower() not in ["heads", "tails"]:
                await interaction.followup.send(messages.warn(interaction.user, "You must choose either `heads` or `tails`."))
                return

            result = "heads" if secrets.randbelow(2) == 0 else "tails"
            won = side.lower() == result

            async with self.pool() as conn:
                if won:
                    await conn.execute(
                        "UPDATE economy SET cash = cash + $1 WHERE user_id = $2",
                        amount_to_bet, user_id
                    )
                    new_balance = user_data["cash"] + amount_to_bet
                    description = f"💰 It's **{result}**\n> You won **{amount_to_bet:,}** 💵, you have a remaining **{new_balance:,}** 💵"
                    color = 0xa4ec7c
                else:
                    await conn.execute(
                        "UPDATE economy SET cash = cash - $1 WHERE user_id = $2",
                        amount_to_bet, user_id
                    )
                    new_balance = user_data["cash"] - amount_to_bet
                    description = f":moneybag: You chose **{side}**, but it was **{result}**\n> You lost **{amount_to_bet:,}** 💵, you have a remaining **{new_balance:,}** 💵"
                    color = 0xff6464

            await self.redis.delete(f"economy:{user_id}")

            embed = await cembed(interaction, description=description, color=color)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await error_handler(interaction, e)
        finally:
            await self.release_lock(user_id)

async def setup(client):
    await client.add_cog(Economy(client))