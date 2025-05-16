from fastapi import FastAPI, Request, Response, HTTPException
import aiohttp, asyncio, json, hmac
from datetime import datetime, timedelta
from typing import Dict, Any
from utils.db import get_db_connection, redis_client
import nacl.signing
import nacl.exceptions
from dotenv import dotenv_values

config = dotenv_values(".env")
DISCORD_PUBLIC_KEY = config["DISCORD_PUBLIC_KEY"]
TOPGG_WEBHOOK_SECRET = config["TOPGG_WEBHOOK_SECRET"]
TOKEN = config["DISCORD_TOKEN"]

DISCORD_VOTE_HOOK = "https://discord.com/api/webhooks/1351959086740017213/OFoPF6fQ2B4MYFNj3aA0qljs2I4sawNtJ9ppIIndu4NSeffxZOJcqyR8kVo3S2_Vfe78"
WEBHOOK_URL = "https://discord.com/api/webhooks/1336692216307126272/j6wtroMosXH7rjIfD8IvmVpkB5F_cTsMWBCbq4YFWeEQjbJDYGNopuB90vDcHTvyjSdX"

app = FastAPI()

def verify_signature(signature: str, timestamp: str, body: str) -> bool:
    try:
        verify_key = nacl.signing.VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        message = timestamp.encode() + body.encode()
        verify_key.verify(message, bytes.fromhex(signature))
        return True
    except (nacl.exceptions.BadSignatureError, ValueError):
        return False

def format_discord_timestamp(iso_timestamp: str | None) -> str:
    if not iso_timestamp:
        return "Unknown Time"
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        unix_timestamp = int(dt.timestamp())
        return f"<t:{unix_timestamp}:R>"
    except (ValueError, TypeError):
        return "Unknown Time"

async def format_event_message(event_type: str, event_data: Dict[str, Any]) -> str:
    if event_type == "APPLICATION_AUTHORIZED":
        data = event_data.get("data", {})
        user = data.get("user", {})
        username = user.get("username", "Unknown")
        user_id = user.get("id", "Unknown")
        app_id = data.get("application_id", "Unknown")
        integration_type = "Server" if event_data.get("data", {}).get("integration_type") == 0 else "User Account"
        scopes = data.get("scopes", [])
        scopes_str = ", ".join(scopes) if scopes else "None"
        timestamp = format_discord_timestamp(event_data.get("timestamp"))
        if user_id and integration_type == "User Account":
            embed = {
                "description": "We aim at enhancing your Discord experience.\n\n[Commands](https://heist.lol/commands) · [Premium](https://heist.lol/premium) · [Support](https://discord.gg/6ScZFN3wPA)\n-# You can use </settings:1278389799681527967> to manage your personal settings.",
                "author": {"name": "Thank you for choosing Heist!"},
                "thumbnail": {"url": "https://csyn.me/assets/heist.png"}
            }
            await send_dm_to_user(user_id, embed, TOKEN)
            print(f"{username} authorised Heist.")
        return f"User authorized Heist.\nUser: [@{username}](discord://-/users/{user_id}) ({user_id})\nIntegration Type: **`{integration_type}`**\nAuthorized Scopes: **`{scopes_str}`**\nTime: {timestamp}"
    elif event_type == "ENTITLEMENT_CREATE":
        data = event_data.get("data", {})
        sku_id = data.get("sku_id", "Unknown")
        user_id = data.get("user_id", "Unknown")
        return f"💎 **New Entitlement Created**\nUser: <@{user_id}>\nSKU ID: `{sku_id}`\nTime: {format_discord_timestamp(event_data.get('timestamp'))}"
    elif event_type == "QUEST_USER_ENROLLMENT":
        data = event_data.get("data", {})
        user_id = data.get("user_id", "Unknown")
        quest_id = data.get("quest_id", "Unknown")
        return f"🎯 **New Quest Enrollment**\nUser: <@{user_id}>\nQuest ID: `{quest_id}`\nTime: {format_discord_timestamp(event_data.get('timestamp'))}"
    return f"📨 **New Event: {event_type}**\nTime: {format_discord_timestamp(event_data.get('timestamp'))}\n```json\n{json.dumps(event_data, indent=2)}\n```"

async def send_dm_to_user(user_id: int, embed: Dict[str, Any], bot_token: str):
    async with aiohttp.ClientSession() as session:
        url = f"https://discord.com/api/v10/users/@me/channels"
        headers = {"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"}
        payload = {"recipient_id": user_id}
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                return
            dm_channel_id = (await response.json())["id"]
            message_url = f"https://discord.com/api/v10/channels/{dm_channel_id}/messages"
            message_payload = {"embeds": [embed]}
            async with session.post(message_url, headers=headers, json=message_payload) as message_response:
                if message_response.status != 200:
                    return

@app.post("/webhook", include_in_schema=False)
async def handle_webhook(request: Request):
    try:
        signature = request.headers.get("X-Signature-Ed25519")
        timestamp = request.headers.get("X-Signature-Timestamp")
        if not signature or not timestamp:
            raise HTTPException(status_code=401, detail="Missing security headers")
        body = await request.body()
        body_str = body.decode()
        if not verify_signature(signature, timestamp, body_str):
            raise HTTPException(status_code=401, detail="Invalid signature")
        data = json.loads(body_str)
        if data.get("type") == 1 and "event" not in data:
            return Response(status_code=204)
        event = data.get("event", {})
        event_type = event.get("type")
        if not event_type:
            return Response(status_code=204)
        message = await format_event_message(event_type, event)
        async with aiohttp.ClientSession() as session:
            async with session.post(WEBHOOK_URL, json={"content": message}, headers={"Content-Type": "application/json"}) as response:
                if response.status != 204:
                    raise HTTPException(status_code=500, detail="Failed to forward to Discord webhook")
        return Response(status_code=204)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def verify_topgg_signature(request: Request, body: bytes) -> bool:
    signature = request.headers.get("Authorization")
    if not signature:
        return False
    expected_signature = hmac.new(TOPGG_WEBHOOK_SECRET.encode(), body, "sha256").hexdigest()
    return hmac.compare_digest(signature, expected_signature)

@app.post("/topgg-webhook")
async def topgg_webhook(request: Request):
    body = await request.body()
    auth_header = request.headers.get("Authorization")
    if auth_header != TOPGG_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    data = json.loads(body)
    user_id = data.get("user")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid payload")
    current_time = datetime.utcnow()
    async with get_db_connection() as conn:
        row = await conn.fetchrow("SELECT last_vote FROM economy WHERE user_id = $1", str(user_id))
        if row and row["last_vote"]:
            last_vote = row["last_vote"]
            if current_time < last_vote + timedelta(hours=12):
                return Response(status_code=204)
        await conn.execute("UPDATE economy SET cash = cash + 50000, last_vote = $1 WHERE user_id = $2", current_time, str(user_id))
    cache_key = f"economy:{user_id}"
    cached_data = await redis_client.hgetall(cache_key)
    if cached_data:
        new_cash = int(cached_data.get("cash", 0)) + 50000
        await redis_client.hset(cache_key, mapping={"cash": str(new_cash), "last_vote": current_time.isoformat()})
    else:
        await redis_client.hset(cache_key, mapping={"cash": "50000", "last_vote": current_time.isoformat()})
    await redis_client.expire(cache_key, 300)
    async with aiohttp.ClientSession() as session:
        url = f"https://discord.com/api/v10/users/@me/channels"
        headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
        payload = {"recipient_id": user_id}
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                dm_channel_id = (await response.json())["id"]
                message_url = f"https://discord.com/api/v10/channels/{dm_channel_id}/messages"
                message_payload = {"content": "Thank you for voting! You have been credited **50,000** 💵."}
                async with session.post(message_url, headers=headers, json=message_payload) as message_response:
                    if message_response.status != 200:
                        pass
    embed = {
        "title": "New Vote Received",
        "description": f"<@{user_id}> has voted for Heist!",
        "color": 0xa4ec7c,
        "timestamp": current_time.isoformat()
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(DISCORD_VOTE_HOOK, json={"embeds": [embed]}) as response:
            if response.status != 204:
                pass
    return Response(status_code=204)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5063)