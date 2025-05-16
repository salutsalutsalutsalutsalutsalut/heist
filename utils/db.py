import asyncpg
import asyncio
import os
from dotenv import dotenv_values
import redis.asyncio as redis
from contextlib import asynccontextmanager

config = dotenv_values(".env")
DATA_DB = config['DATA_DB']

redis_pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True,
    max_connections=250
)

redis_client = redis.Redis(connection_pool=redis_pool)

class Database:
    _pool = None
    _lock = asyncio.Lock()
    
    @classmethod
    async def init_pool(cls):
        if cls._pool is None:
            async with cls._lock:
                if cls._pool is None:
                    print("Initializing database pool...")
                    try:
                        cls._pool = await asyncpg.create_pool(
                            dsn=DATA_DB,
                            min_size=5,
                            max_size=20,
                            max_inactive_connection_lifetime=300,
                            max_queries=10_000,
                        )
                        print("Database pool initialized successfully.")
                    except Exception as e:
                        print(f"Failed to initialize database pool: {e}")
                        raise
        return cls._pool

    @classmethod
    @asynccontextmanager
    async def get_connection(cls):
        pool = await cls.init_pool()
        async with pool.acquire() as connection:
            yield connection

    @classmethod
    async def execute_query(cls, query, params=None, fetch_one=True):
        retry_attempts = 3
        for attempt in range(retry_attempts):
            try:
                async with cls.get_connection() as conn:
                    async with conn.transaction():
                        if fetch_one:
                            result = await conn.fetchrow(query, *(params or ()))
                        else:
                            result = await conn.execute(query, *(params or ()))
                        return result
            except asyncpg.PostgresError as e:
                if 'could not connect' in str(e):
                    if attempt < retry_attempts - 1:
                        await asyncio.sleep(3)
                        continue
                raise

@asynccontextmanager
async def get_db_connection():
    async with Database.get_connection() as conn:
        yield conn

async def execute_query(query, params=None, fetch_one=True):
    return await Database.execute_query(query, params, fetch_one)

async def check_blacklisted(user_id):
    user_id_str = str(user_id)
    cached_result = await redis_client.get(f"blacklist:{user_id_str}")
    if cached_result is not None:
        return cached_result == "True"

    query = "SELECT COUNT(*) FROM blacklisted WHERE user_id = $1"
    result = await Database.execute_query(query, (user_id_str,))
    is_blacklisted = result['count'] > 0 if result else False

    await redis_client.setex(f"blacklist:{user_id_str}", 300, str(is_blacklisted))
    return is_blacklisted

async def check_booster(user_id):
    user_id_str = str(user_id)
    cached_result = await redis_client.get(f"booster:{user_id_str}")
    if cached_result is not None:
        return cached_result == "True"
    
    query = "SELECT booster FROM user_data WHERE user_id = $1"
    result = await Database.execute_query(query, (user_id_str,))
    is_booster = result['booster'] if result else False
    
    await redis_client.setex(f"booster:{user_id_str}", 300, str(is_booster))
    return is_booster

async def check_donor(user_id):
    user_id_str = str(user_id)
    cached_result = await redis_client.get(f"donor:{user_id_str}")
    if cached_result is not None:
        return cached_result == "True"

    query = "SELECT COUNT(*) FROM donors WHERE user_id = $1"
    result = await Database.execute_query(query, (user_id_str,))
    is_donor = result['count'] > 0 if result else False

    await redis_client.setex(f"donor:{user_id_str}", 300, str(is_donor))
    return is_donor

async def check_owner(user_id):
    user_id_str = str(user_id)
    cached_result = await redis_client.get(f"owner:{user_id_str}")
    if cached_result is not None:
        return cached_result == "True"

    query = "SELECT COUNT(*) FROM owners WHERE user_id = $1"
    result = await Database.execute_query(query, (user_id_str,))
    is_owner = result['count'] > 0 if result else False

    await redis_client.setex(f"owner:{user_id_str}", 300, str(is_owner))
    return is_owner

async def check_famous(user_id):
    user_id_str = str(user_id)
    cached_result = await redis_client.get(f"famous:{user_id_str}")
    if cached_result is not None:
        return cached_result == "True"

    async with Database.get_connection() as conn:
        fame_status = await conn.fetchval("SELECT fame FROM user_data WHERE user_id = $1", user_id_str)
        is_famous = bool(fame_status)

        await redis_client.setex(f"famous:{user_id_str}", 300, str(is_famous))
        return is_famous