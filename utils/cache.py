import time
import asyncio
import asyncpg
from utils.db import get_db_connection, redis_client

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
CACHE_EXPIRY_TIME = 3600

async def set_embed_color(user_id: str, color: int):
    if isinstance(color, str):
        color = int(color, 16)
    if isinstance(color, int) and 0 <= color <= 0xFFFFFF:
        await redis_client.set(f"embed_color:{str(user_id)}", color, ex=CACHE_EXPIRY_TIME)

async def get_embed_color(user_id: str):
    cached_color = await redis_client.get(f"embed_color:{user_id}")
    if cached_color:
        return int(cached_color)

    async with get_db_connection() as conn:
        async with conn.transaction():
            result = await conn.fetchrow("SELECT embed_color FROM settings WHERE user_id = $1", str(user_id))
            if result and result['embed_color'] is not None:
                embed_color = result['embed_color']
            else:
                embed_color = 0xd3d6f1

            await set_embed_color(user_id, embed_color)
            return embed_color