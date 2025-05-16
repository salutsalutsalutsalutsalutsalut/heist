from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
import time
import requests
import asyncio
from typing import Dict, List
import aiohttp
import subprocess
from dotenv import dotenv_values
from utils.db import redis_client
import json

config = dotenv_values(".env")
TOKEN = config["DISCORD_TOKEN"]
DATA_DB = config["DATA_DB"]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_TIMEOUT = 300
STATUS_CACHE_TIMEOUT = 3600
GUILDS_CACHE_TIMEOUT = 86400
DISCORD_API_URL = "https://discord.com/api/v10/applications/1225070865935368265"
DISCORD_AUTH_HEADER = {
    "Authorization": f"Bot {TOKEN}",
    "Content-Type": "application/json"
}

def is_process_online(process_name: str) -> bool:
    cmd = ['pm2', 'info', process_name]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout
    return 'online' in output

@app.get("/status")
async def get_status():
    status = await redis_client.get("status_cache")
    if status:
        return {"status": status.decode()}

    userbot_online = is_process_online('heist')
    status = 'online' if userbot_online else 'offline'
    await redis_client.setex("status_cache", STATUS_CACHE_TIMEOUT, status)

    return {"status": status}

async def get_counts():
    conn = await asyncpg.connect(dsn=DATA_DB)
    try:
        user_count = await conn.fetchval("SELECT COUNT(*) FROM user_data")
        premium_count = await conn.fetchval("SELECT COUNT(*) FROM donors")
        return user_count, premium_count
    finally:
        await conn.close()

async def fetch_discord_data():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(DISCORD_API_URL, headers=DISCORD_AUTH_HEADER) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("approximate_user_install_count", 0), data.get("approximate_guild_count", 0)
    except Exception as e:
        print(f"Error fetching Discord data: {e}")
    return 0, 0

async def update_discord():
    while True:
        discord_user_install_count, discord_guild_count = await fetch_discord_data()
        print(f"Fetched data: users={discord_user_install_count}, guilds={discord_guild_count}")
        await redis_client.set("discord_user_install_count", discord_user_install_count)
        await redis_client.set("discord_guild_count", discord_guild_count)
        await asyncio.sleep(15 * 60)

async def fetch_guilds():
    url = "https://discord.com/api/v10/users/@me/guilds"
    headers = {
        "Authorization": f"Bot {TOKEN}",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
    except Exception as e:
        print(f"Error fetching guilds: {e}")
    return []

async def update_guilds():
    while True:
        guilds = await fetch_guilds()
        serialized_guilds = json.dumps(guilds)
        await redis_client.set("guilds_cache", serialized_guilds)
        await redis_client.set("guilds_cache_timestamp", time.time())
        await asyncio.sleep(24 * 60 * 60)

@app.get("/getcount")
async def counts(response: Response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    cached_counts = await redis_client.get("counts_cache")
    if cached_counts:
        return json.loads(cached_counts)

    user_count, premium_count = await get_counts()
    discord_user_install_count = await redis_client.get("discord_user_install_count")
    discord_guild_count = await redis_client.get("discord_guild_count")

    counts = {
        'user_count': user_count, 
        'premium_count': premium_count,
        'discord_user_install_count': int(discord_user_install_count or 0),
        'discord_guild_count': int(discord_guild_count or 0)
    }

    await redis_client.setex("counts_cache", CACHE_TIMEOUT, json.dumps(counts))
    return counts

@app.get("/guilds")
async def guilds():
    cached_guilds = await redis_client.get("guilds_cache")
    if cached_guilds:
        return {'guilds': json.loads(cached_guilds)}

    guilds = await fetch_guilds()
    serialized_guilds = json.dumps(guilds)
    await redis_client.setex("guilds_cache", GUILDS_CACHE_TIMEOUT, serialized_guilds)
    await redis_client.set("guilds_cache_timestamp", time.time())

    return {'guilds': guilds}

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(update_discord())
    asyncio.create_task(update_guilds())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)