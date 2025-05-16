import asyncio
import threading
import websockets
import json
from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader, APIKey
import aiohttp
import uvicorn
from datetime import datetime, timedelta
import asyncpg
from asyncpg.pool import Pool
from functools import wraps, lru_cache
import time

from aiocache import caches, cached
from aiocache.serializers import JsonSerializer
from asyncpg.exceptions import PostgresError
import redis.asyncio as redis

redis_client = redis.Redis(
    host='localhost', 
    port=6379,
    db=0  
)

caches.set_config({
    'default': {
        'cache': "aiocache.SimpleMemoryCache",
        'serializer': {
            'class': JsonSerializer
        }
    }
})

app = FastAPI(docs_url=None)

with open('config.json', 'r') as file:
    config = json.load(file)

tokens = config["tokens"]

ALLOWED_API_KEY = "Pedovade-V2-TravisScottGyat"

def validate_api_key(x_api_key: str = Header(None)):
    if x_api_key != ALLOWED_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid API key.")
    return x_api_key

@cached(ttl=1200)
async def get_mutual_guilds(user_id, token):
    user_profile = await get_user(user_id, token)
    mutual_guilds = user_profile.get("mutual_guilds", [])
    tasks = [get_guild(guild["id"], token) for guild in mutual_guilds]
    guild_details = await asyncio.gather(*tasks)
    guild_details = [guild_info for guild_info in guild_details if 'id' in guild_info]
    guild_details = [{
        "id": guild_info["id"],
        "name": guild_info["name"],
        "vanity_url": guild_info.get("vanity_url_code", "")
    } for guild_info in guild_details]
    return guild_details

XSuperProperties = {
    "os": "Windows",
    "browser": "Firefox",
    "device": "",
    "system_locale": "en-US",
    "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "browser_version": "123.0",
    "os_version": "10",
    "referrer": "https://www.google.com/search?q=discord",
    "referring_domain": "google.com",
    "referrer_current": "",
    "referring_domain_current": "",
    "release_channel": "stable",
    "client_build_number": 284422,
    "client_event_source": "null"
}

async def fetch_data(url, token):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={
            "Accept": "*/*",
            "Accept-Language": "en-US",
            "Authorization": f"{token}",
            "X-Super-Properties": json.dumps(XSuperProperties),
            "X-Discord-Locale": "en",
            "Connection": "keep-alive",
            "Referer": "https://discord.com/channels/@me",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "TE": "trailers",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"}, 
            #proxy="http://avxnhvsd-rotate:8oulnn82723n@p.webshare.io:80"
            ) as response:
                return await response.json()

async def fetch_data_np(url, token):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={
            "Accept": "*/*",
            "Accept-Language": "en-US",
            "Authorization": f"{token}",
            "X-Super-Properties": json.dumps(XSuperProperties),
            "X-Discord-Locale": "en",
            "Connection": "keep-alive",
            "Referer": "https://discord.com/channels/@me",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "TE": "trailers",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"}, 
            ) as response:
                return await response.json()

@cached(ttl=604800)
async def get_guild(id, token):
    try:
        url = f"https://discord.com/api/v9/guilds/{id}"
        return await fetch_data_np(url, token)
    except Exception as e:
        if isinstance(e, HTTPException) and e.status in [403, 429]:
            print(f"Cloudflare error {e.status} encountered, switching to fallback.")
            return await fetch_data(id, token)
        else:
            print(e)

@cached(ttl=86400)
async def get_channel_name(guild_id, channel_id, token):
    try:
        url = f"https://discord.com/api/v9/guilds/{guild_id}/channels"
        channels = await fetch_data_np(url, token)
        if channels:
            for channel in channels:
                if str(channel["id"]) == channel_id:
                    return channel.get("name", "Unknown Channel")
        return "Unknown Channel"
    except Exception as e:
        print(f"Error fetching channel name: {e}")
        return "Unknown Channel"

@cached(ttl=3600)
async def get_user(id, token):
    try:
        url = f"https://discord.com/api/v9/users/{id}/profile"
        return await fetch_data(url, token)
    except Exception as e:
        if isinstance(e, HTTPException) and e.status in [403, 429]:
            print(f"Cloudflare error {e.status} encountered, switching to fallback.")
            return await fetch_data(id, token)
        else:
            print(e)

@cached(ttl=1200)
async def get_guilds(token):
    try:
        url = "https://discord.com/api/v9/users/@me/guilds"
        return await fetch_data(url, token)
    except Exception as e:
        print('o no tolet error below')
        print(e)

@cached(ttl=1200)
@app.get("/users/{id}")
async def get_user_endpoint(id: int, request: Request):
    try:
        tasks = [get_user(id, token) for token in tokens]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, dict) and "message" not in result:
                return result
        return {}
    except Exception as e:
        print(e)

# @cached(ttl=18000)
# @app.get("/guilds/{id}")
# async def get_guild_endpoint(id: int, api_key: APIKey = Depends(get_api_key)):
#     try:
#         tasks = [get_guild(id, token) for token in tokens]
#         results = await asyncio.gather(*tasks, return_exceptions=True)
#         for result in results:
#             if isinstance(result, dict) and "message" not in result:
#                 return result
#         return {}
#     except Exception as e:
#         print(e)

# @cached(ttl=1200)
# @app.get("/mutualguilds/{user_id}")
# async def get_mutual_guilds_endpoint(user_id: int, api_key: APIKey = Depends(get_api_key)):
#     try:
#         tasks = [get_mutual_guilds(user_id, token) for token in tokens]
#         results = await asyncio.gather(*tasks, return_exceptions=True)
#         mutual_guilds = []
#         for result in results:
#             if isinstance(result, Exception):
#                 print(f"Error fetching mutual guilds with token: {result}")
#                 continue 
#             if isinstance(result, list):
#                 mutual_guilds.extend(result)
#         unique_guilds = [dict(t) for t in {tuple(guild.items()) for guild in mutual_guilds}]
#         return unique_guilds
#     except Exception as e:
#         print(f"Unexpected error occurred: {e}")
#         raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

# @cached(ttl=1200)
# @app.get("/guildscount/{user_id}")
# async def get_guilds_count_endpoint(user_id: int, api_key: APIKey = Depends(get_api_key)):
#     try:
#         async def count_mutual_guilds(user_id, token):
#             user_profile = await get_user(user_id, token)
#             return len(user_profile.get("mutual_guilds", []))

#         tasks = [count_mutual_guilds(user_id, token) for token in tokens]
#         results = await asyncio.gather(*tasks, return_exceptions=True)
        
#         total_count = 0
#         for result in results:
#             if isinstance(result, int):
#                 total_count = max(total_count, result)
#             elif isinstance(result, Exception):
#                 print(f"Error fetching mutual guilds count with token: {result}")
        
#         return {"count": total_count}
#     except Exception as e:
#         print(f"Unexpected error occurred: {e}")
#         raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

#@app.get("/heist/mutualguilds/{user_id}")
#async def get_mutual_guilds_endpoint2(user_id: str, api_key: APIKey = Depends(get_api_key)):
    #async with logs_pool.acquire() as conn:
        #try:
            #query = '''
                #SELECT g.guild_id, g.guild_name 
                #FROM user_guilds ug
                #JOIN guilds g ON ug.guild_id = g.guild_id
                #WHERE ug.user_id = $1
            #'''
            #guilds = await conn.fetch(query, user_id)
            #result = [{'id': guild['guild_id'], 'name': guild['guild_name']} for guild in guilds]
            #return result
        #except asyncpg.Error as e:
            #raise HTTPException(status_code=500, detail=f"Database error occurred: {e}")

# @app.get("/messages/{user_id}")
# async def get_user_messages_endpoint(user_id: str, api_key: APIKey = Depends(get_api_key)):
#     async with data_pool.acquire() as conn:
#         try:
#             query = '''
#                 SELECT user_id, guild_id, content, timestamp
#                 FROM messages
#                 WHERE user_id = $1
#                 ORDER BY timestamp DESC
#             '''
#             messages = await conn.fetch(query, user_id)
#             result = [{'user_id': message['user_id'],
#                        'guild_id': message['guild_id'],
#                        'content': message['content'],
#                        'timestamp': message['timestamp']} for message in messages]
#             return result
#         except asyncpg.Error as e:
#             raise HTTPException(status_code=500, detail=f"Database error occurred: {e}")

# @app.get("/namehistory/{user_id}")
# async def get_user_history_endpoint(user_id: str, api_key: APIKey = Depends(get_api_key)):
#     async with data_pool.acquire() as conn:
#         try:
#             query = '''
#                 SELECT old_username, new_username, timestamp
#                 FROM name_history
#                 WHERE user_id = $1
#                 ORDER BY timestamp DESC
#             '''
#             history = await conn.fetch(query, user_id)
#             result = [{'old_username': record['old_username'],
#                       'new_username': record['new_username'],
#                       'timestamp': record['timestamp']} for record in history]
#             return result
#         except asyncpg.Error as e:
#             raise HTTPException(status_code=500, detail=f"Database error occurred: {e}")

async def handle_last_seen(data, token):
    if data.get('author', {}).get('bot'):
        return
    
    try:
        user_id = str(data["author"]["id"])
        guild_id = str(data["guild_id"])
        channel_id = str(data["channel_id"])

        guild_info = await get_guild(guild_id, token)
        guild_name = guild_info.get("name", "Unknown Guild")

        channel_name = await get_channel_name(guild_id, channel_id, token)

        last_seen_data = {
            'guild_name': guild_name,
            'channel_name': channel_name,
            'timestamp': int(datetime.utcnow().timestamp())
        }
        print(last_seen_data)

        await redis_client.hset(
            'last_seen_users', 
            user_id, 
            json.dumps(last_seen_data)
        )
    except Exception as e:
        print(f"Error updating last seen: {e}")

async def handle_voice_state(data, token):
    try:
        user_id = str(data["user_id"])
        channel_id = data.get("channel_id")
        
        if channel_id:
            vc_data = {
                "channel_id": channel_id,
                "guild_id": data["guild_id"],
                "self_deaf": data.get("self_deaf", False),
                "self_mute": data.get("self_mute", False),
                "deaf": data.get("deaf", False),
                "mute": data.get("mute", False),
                "timestamp": int(datetime.utcnow().timestamp())
            }
            
            guild_info = await get_guild(data["guild_id"], token)
            guild_name = guild_info.get("name", "Unknown Guild")
            channel_name = await get_channel_name(data["guild_id"], channel_id, token)
            
            vc_data.update({
                'guild_name': guild_name,
                'channel_name': channel_name
            })
            
            #print(f"User {user_id} voice state update: {vc_data}")

            await redis_client.hset(
                'vc_users',
                user_id,
                json.dumps(vc_data)
            )
        else:
            await redis_client.hdel('vc_users', user_id)

    except Exception as e:
        print(f"Error updating voice state: {e}")

async def handle_message_create(data):
    user_id = str(data["author"]["id"])
    guild_id = str(data["guild_id"])
    content = data["content"][:197] + ("..." if len(data["content"]) > 197 else "")
    timestamp = datetime.fromisoformat(data["timestamp"].rstrip('Z')).replace(tzinfo=None)

    async with data_pool.acquire() as conn:
        try:
            await conn.execute('''
                INSERT INTO messages (user_id, guild_id, content, timestamp)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, guild_id, content, timestamp) DO NOTHING
            ''', user_id, guild_id, content, timestamp)

            messages = await conn.fetch('''
                SELECT id FROM messages
                WHERE user_id = $1 AND guild_id = $2
                ORDER BY timestamp DESC
                LIMIT 15
            ''', user_id, guild_id)

            message_ids = [message['id'] for message in messages]

            await conn.execute('''
                DELETE FROM messages
                WHERE user_id = $1 AND guild_id = $2
                AND id NOT IN (SELECT id FROM messages WHERE user_id = $1 AND guild_id = $2 ORDER BY timestamp DESC LIMIT 15)
            ''', user_id, guild_id)

        except PostgresError as e:
            print(f"Database error occurred while handling message: {e}")

# async def handle_user_update(data):
#     user_id = str(data["id"])
#     new_username = data["username"]
#     timestamp = int(time.time())

#     print(f"Processing username update for user {user_id}: new username = {new_username}")

#     async with data_pool.acquire() as conn:
#         try:
#             last_record = await conn.fetchrow('''
#                 SELECT new_username
#                 FROM name_history
#                 WHERE user_id = $1
#                 ORDER BY timestamp DESC
#                 LIMIT 1
#             ''', user_id)

#             old_username = last_record['new_username'] if last_record else new_username
#             print(f"Previous username found: {old_username}")

#             if old_username != new_username:
#                 print(f"Inserting new record: {old_username} -> {new_username}")
#                 await conn.execute('''
#                     INSERT INTO name_history (user_id, old_username, new_username, timestamp)
#                     VALUES ($1, $2, $3, $4)
#                     ON CONFLICT (user_id, old_username, new_username, timestamp) DO NOTHING
#                 ''', user_id, old_username, new_username, timestamp)
#                 print("Record inserted successfully")
#             else:
#                 print("No username change detected, skipping insert")

#         except PostgresError as e:
#             print(f"Database error occurred while handling username update: {e}")

async def delete_old_name_history():
    async with data_pool.acquire() as conn:
        try:
            cutoff_timestamp = int(time.time()) - (90 * 24 * 60 * 60)
            await conn.execute('''
                DELETE FROM name_history
                WHERE timestamp < $1
            ''', cutoff_timestamp)
            print(f"Deleted name history records before timestamp {cutoff_timestamp}")
        except PostgresError as e:
            print(f"Database error occurred while deleting old name history: {e}")

async def delete_old_messages():
    async with data_pool.acquire() as conn:
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=12)
            await conn.execute('''
                DELETE FROM messages
                WHERE timestamp < $1
            ''', cutoff_time)
            print(f"Deleted old messages before {cutoff_time}")
        except PostgresError as e:
            print(f"Database error occurred while deleting old messages: {e}")

async def periodic_cleanup(interval: int):
    while True:
        await delete_old_messages()
        #await delete_old_name_history()
        await asyncio.sleep(interval)

async def connect_to_gateway(token):
    try:
        print(f"Connecting to gateway with token: {token}")
        uri = "wss://gateway.discord.gg/?v=9&encoding=json"
        async with websockets.connect(uri, ping_interval=None, ping_timeout=None, max_size=None) as websocket:
            print(f"Connected to gateway with token: {token}")
            await websocket.send(json.dumps({
                "op": 2,
                "d": {
                    "token": token,
                    "properties": {
                        "$os": "Discord iOS",
                        "$browser": "Discord iOS",
                        "$device": "iOS"
                    }
                }
            }))
            guilds = await get_guilds(token)
            for guild in guilds:
                eventJson = {
                    "guild_id": guild["id"],
                    "typing": True,
                    "threads": True,
                    "activities": False,
                }
                await websocket.send(json.dumps({
                    "op": 14,
                    "d": eventJson
                }))
                print(f"Subscribed to guild {guild['id']}")        
            print(f"Sent identify message with token: {token}")
            while True:
                try:
                    event_data = await websocket.recv()
                    event = json.loads(event_data)
                    if event["op"] == 10:
                        heartbeat_interval = event["d"]["heartbeat_interval"] / 1000
                        asyncio.create_task(send_heartbeat(websocket, heartbeat_interval))
                    #elif event["op"] == 0:
                       # if event["t"] == "MESSAGE_CREATE":
                           # await handle_last_seen(event["d"], token)
                        #if event["t"] == "VOICE_STATE_UPDATE":
                            #await handle_voice_state(event["d"], token)
                            # await handle_message_create(event["d"])
                        # if event["t"] == "USER_UPDATE":
                            # await handle_user_update(event["d"])
                except websockets.exceptions.ConnectionClosed:
                    print(f"Connection closed for token {token}. Reconnecting...")
                    await asyncio.sleep(5)
                    await connect_to_gateway(token)
    except Exception as e:
        print(f"Error connecting to gateway for token {token}: {e}")
        await asyncio.sleep(5)
        await connect_to_gateway(token)

async def send_heartbeat(websocket, interval):
    while True:
        print(f"Waiting for {interval} seconds before sending heartbeat")
        await asyncio.sleep(interval)
        print("Sending heartbeat")
        await websocket.send(json.dumps({"op": 1, "d": None}))

async def run_async():
    tasks = [asyncio.create_task(connect_to_gateway(token)) for token in tokens]
    await asyncio.gather(*tasks)

async def start_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8002)
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(
        run_async(),
        start_server()
    )

if __name__ == "__main__":
    asyncio.run(main())