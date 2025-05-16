import asyncio
import threading
import websockets
import json
from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader, APIKey
import aiohttp
import uvicorn
from datetime import datetime, timedelta, timezone
import asyncpg
from asyncpg.pool import Pool
from utils.db import Database, get_db_connection, redis_client
from functools import wraps
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
config = dotenv_values(".env")
BYPASS_API_KEY = config["HEIST_API_KEY"]

request_counts = {}

async def load_api_keys() -> list[str]:
    async with get_db_connection() as conn:
        rows = await conn.fetch('SELECT api_key FROM api_keys')
        return [row['api_key'] for row in rows]

api_key_header = APIKeyHeader(name="X-API-Key")

async def get_api_key(api_key: str = Depends(api_key_header), request: Request = None):
    api_keys = await load_api_keys()
    if api_key not in api_keys:
        raise HTTPException(status_code=403, detail="Invalid API Key. Request one here: https://discord.gg/heistbot")
    if api_key == BYPASS_API_KEY:
        return api_key
    endpoint_path = str(request.url.path)
    if api_key not in request_counts:
        request_counts[api_key] = {}
    if endpoint_path not in request_counts[api_key]:
        request_counts[api_key][endpoint_path] = {"count": 1, "timestamp": datetime.utcnow()}
        return api_key
    current_time = datetime.utcnow()
    last_timestamp = request_counts[api_key][endpoint_path]["timestamp"]
    request_count = request_counts[api_key][endpoint_path]["count"]
    time_diff = current_time - last_timestamp
    if time_diff < timedelta(minutes=1):
        request_counts[api_key][endpoint_path]["count"] += 1
    else:
        request_counts[api_key][endpoint_path]["count"] = 1
        request_counts[api_key][endpoint_path]["timestamp"] = current_time
    if request_counts[api_key][endpoint_path]["count"] > 10:
        raise HTTPException(status_code=429, detail="Rate limit exceeded for this endpoint. Try again later.")
    return api_key

@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return JSONResponse(content={"message": "API key required. Request one here: https://discord.gg/heistbot"}, status_code=403)
    api_keys = await load_api_keys()
    if api_key not in api_keys:
        return JSONResponse(content={"message": "Invalid API key. Request one here: https://discord.gg/heistbot"}, status_code=403)
    response = await call_next(request)
    return response

with open('config.json', 'r') as file:
    config = json.load(file)

tokens = config["tokens"]

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
            proxy="http://avxnhvsd-rotate:8oulnn82723n@p.webshare.io:80"
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
        return await fetch_data_np(url, token)
    except Exception as e:
        if isinstance(e, HTTPException) and e.status in [403, 429]:
            print(f"Cloudflare error {e.status} encountered, switching to fallback.")
            return await fetch_data_np(id, token)
        else:
            print(e)

@cached(ttl=1200)
async def get_guilds(token):
    try:
        url = "https://discord.com/api/v9/users/@me/guilds"
        return await fetch_data_np(url, token)
    except Exception as e:
        print('o no tolet error below')
        print(e)

@cached(ttl=1200)
@app.get("/users/{id}")
async def get_user_endpoint(id: int, request: Request, api_key: APIKey = Depends(get_api_key)):
    client_host = request.headers.get("CF-Connecting-IP", request.client.host)
    if client_host not in ("127.0.0.1", "localhost", "::1", "38.45.67.46"):
        raise HTTPException(status_code=403, detail="Forbidden: This endpoint is only available for whitelisted IPs.")

    try:
        tasks = [get_user(id, token) for token in tokens]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, dict) and "message" not in result:
                return result
        return {}
    except Exception as e:
        print(e)

@app.get("/users/lastseen/{user_id}")
async def get_last_seen(
    user_id: str, 
    request: Request, 
    api_key: APIKey = Depends(get_api_key)
):
    try:
        last_seen = await redis_client.get(f'last_seen_users:{user_id}')
        if not last_seen:
            return {}
        
        return json.loads(last_seen)
    except Exception as e:
        print(f"Error fetching last seen data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/users/vcstate/{user_id}")
async def get_voice_state(
    user_id: str, 
    request: Request, 
    api_key: APIKey = Depends(get_api_key)
):
    try:
        vc_state = await redis_client.get(f'vc_state:{user_id}')
        if not vc_state:
            return {}
            
        return json.loads(vc_state)
    except Exception as e:
        print(f"Error fetching voice state data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

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

@cached(ttl=1200)
@app.get("/mutualguilds/{user_id}")
async def get_mutual_guilds_endpoint(user_id: int, api_key: APIKey = Depends(get_api_key)):
    try:
        tasks = [get_mutual_guilds(user_id, token) for token in tokens]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        mutual_guilds = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Error fetching mutual guilds with token: {result}")
                continue 
            if isinstance(result, list):
                mutual_guilds.extend(result)
        unique_guilds = [dict(t) for t in {tuple(guild.items()) for guild in mutual_guilds}]
        return unique_guilds
    except Exception as e:
        print(f"Unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

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
#     async with get_db_connection() as conn:
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
#     async with get_db_connection() as conn:
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
        
        key = f'last_seen_users:{user_id}'
        await redis_client.setex(key, 24 * 60 * 60, json.dumps(last_seen_data))

        event_data = {
            "type": "message",
            "user_id": user_id,
            "guild_id": guild_id,
            "guild_name": guild_name,
            "channel_id": channel_id,
            "channel_name": channel_name
        }
        await redis_client.publish('user_activity', json.dumps(event_data))

    except Exception as e:
        print(f"Error updating last seen: {e}")

async def handle_voice_state(data, token):
    try:
        user_id = str(data["user_id"])
        channel_id = data.get("channel_id")

        vc_key = f'vc_state:{user_id}'
        prev_vc_data_str = await redis_client.get(vc_key)
        prev_vc_data = json.loads(prev_vc_data_str) if prev_vc_data_str else None
        prev_channel_id = prev_vc_data.get("channel_id") if prev_vc_data else None

        if channel_id:
            guild_info = await get_guild(data["guild_id"], token)
            guild_name = guild_info.get("name", "Unknown Guild")
            channel_name = await get_channel_name(data["guild_id"], channel_id, token)

            vc_data = {
                "channel_id": channel_id,
                "guild_id": data["guild_id"],
                "guild_name": guild_name,
                "channel_name": channel_name,
                "self_deaf": data.get("self_deaf", False),
                "self_mute": data.get("self_mute", False),
                "deaf": data.get("deaf", False),
                "mute": data.get("mute", False),
                "timestamp": int(datetime.utcnow().timestamp())
            }

            await redis_client.setex(vc_key, 24 * 60 * 60, json.dumps(vc_data))

            if prev_channel_id and prev_channel_id != channel_id:
                prev_channel_name = await get_channel_name(data["guild_id"], prev_channel_id, token)
                event_type = "voice_switch"
                event_data = {
                    "type": event_type,
                    "user_id": user_id,
                    "guild_name": guild_name,
                    "old_channel_name": prev_channel_name,
                    "channel_id": channel_id,
                    "channel_name": channel_name
                }
            else:
                event_type = "voice_join"
                event_data = {
                    "type": event_type,
                    "user_id": user_id,
                    "guild_name": guild_name,
                    "channel_id": channel_id,
                    "channel_name": channel_name
                }

        else:
            if prev_channel_id:
                guild_info = await get_guild(data["guild_id"], token)
                guild_name = guild_info.get("name", "Unknown Guild")
                prev_channel_name = await get_channel_name(data["guild_id"], prev_channel_id, token)

                event_type = "voice_leave"
                event_data = {
                    "type": event_type,
                    "user_id": user_id,
                    "guild_name": guild_name,
                    "channel_id": channel_id,
                    "channel_name": prev_channel_name
                }

                await redis_client.delete(vc_key)
            else:
                return

        await redis_client.publish('user_activity', json.dumps(event_data))

    except Exception as e:
        print(f"Error updating voice state: {e}")

async def handle_message_create(data):
    user_id = str(data["author"]["id"])
    guild_id = str(data["guild_id"])
    content = data["content"][:197] + ("..." if len(data["content"]) > 197 else "")
    timestamp = datetime.fromisoformat(data["timestamp"].rstrip('Z')).replace(tzinfo=None)

    async with get_db_connection() as conn:
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

#     async with get_db_connection() as conn:
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
    async with get_db_connection() as conn:
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
    async with get_db_connection() as conn:
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
    uri = "wss://gateway.discord.gg/?v=9&encoding=json"
    
    while True:
        try:
            print(f"Connecting to gateway with token: {token}")
            async with websockets.connect(uri, ping_interval=30, ping_timeout=10, max_size=None) as websocket:
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

                async for event_data in websocket:
                    try:
                        event = json.loads(event_data)

                        if event["op"] == 10:
                            heartbeat_interval = event["d"]["heartbeat_interval"] / 1000
                            asyncio.create_task(send_heartbeat(websocket, heartbeat_interval))

                        elif event["op"] == 0:
                            if event["t"] == "MESSAGE_CREATE":
                                await handle_last_seen(event["d"], token)
                            elif event["t"] == "VOICE_STATE_UPDATE":
                                await handle_voice_state(event["d"], token)

                    except Exception as e:
                        print(f"Error processing event for token {token}: {e}")

        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed for token {token} ({e}). Reconnecting in 5s...")
            await asyncio.sleep(5)

        except Exception as e:
            print(f"Unexpected error for token {token}: {e}. Reconnecting in 10s...")
            await asyncio.sleep(10)

async def send_heartbeat(websocket, interval):
    while True:
        try:
            await asyncio.sleep(interval)
            await websocket.send(json.dumps({"op": 1, "d": None}))
            print("Heartbeat sent")
        except websockets.exceptions.ConnectionClosed:
            print("Heartbeat stopped: WebSocket closed")
            break

async def run_async():
    asyncio.create_task(periodic_cleanup(172800))
    tasks = [asyncio.create_task(connect_to_gateway(token)) for token in tokens]
    await asyncio.gather(*tasks)

async def start_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8002)
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(
        run_async(),
        start_server()
    )

if __name__ == "__main__":
    asyncio.run(main())
