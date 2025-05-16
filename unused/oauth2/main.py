import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from starlette.responses import PlainTextResponse
from dotenv import dotenv_values
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
import asyncio

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

config = dotenv_values(".env")
DATABASE_URL = config['DATABASE_URL']
WEBHOOK_CODE = config['WEBHOOK_CODE']
WEBHOOK_URL = f'https://discord.com/api/webhooks/{WEBHOOK_CODE}'

app = FastAPI()
scheduler = AsyncIOScheduler()

async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    scheduler.add_job(update_user_guilds, 'interval', hours=5)
    scheduler.start()
    yield
    scheduler.shutdown()
    await app.state.pool.close()

app = FastAPI(lifespan=lifespan)

async def execute_sql_query(query: str, params: tuple = ()):
    async with app.state.pool.acquire() as conn:
        try:
            return await conn.fetch(query, *params)
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Database error: {e}")
            raise HTTPException(status_code=500, detail="Database connection issue")

async def update_guilds_in_db(user_id: str, new_guilds_data: list):
    existing_guild_ids = {record['guild_id'] for record in await execute_sql_query('SELECT guild_id FROM user_guilds WHERE user_id = $1', (user_id,))}
    new_guild_ids = {guild['id'] for guild in new_guilds_data}
    guilds_to_add = new_guild_ids - existing_guild_ids
    guilds_to_remove = existing_guild_ids - new_guild_ids

    for guild in new_guilds_data:
        if guild['id'] in guilds_to_add:
            await execute_sql_query('''
                INSERT INTO guilds (guild_id, guild_name)
                VALUES ($1, $2)
                ON CONFLICT (guild_id) DO NOTHING
            ''', (guild['id'], guild['name']))

            await execute_sql_query('''
                INSERT INTO user_guilds (user_id, guild_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id, guild_id) DO NOTHING  -- Handle duplicates here
            ''', (user_id, guild['id']))

    for guild_id in guilds_to_remove:
        await execute_sql_query('DELETE FROM user_guilds WHERE user_id = $1 AND guild_id = $2', (user_id, guild_id))

async def log_user_info(user_id: str, username: str, user_ip: str, guilds_data: list, refresh_token: str):
    async with app.state.pool.acquire() as conn:
        date_authorized = datetime.utcnow()
        params = (user_id, username, user_ip, date_authorized, refresh_token)
        await conn.execute('''
            INSERT INTO users (user_id, username, user_ip, date_authorized, refresh_token)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT(user_id) DO UPDATE SET
            username=EXCLUDED.username,
            user_ip=EXCLUDED.user_ip,
            date_authorized=EXCLUDED.date_authorized,
            refresh_token=EXCLUDED.refresh_token
        ''', *params)
        await update_guilds_in_db(user_id, guilds_data)

async def fetch_user_guilds(access_token: str):
    async with httpx.AsyncClient() as client:
        response = await client.get('https://discord.com/api/v10/users/@me/guilds', headers={'Authorization': f'Bearer {access_token}'})
        response.raise_for_status()
        return response.json()

async def refresh_access_token(refresh_token: str):
    form_data = {
        'client_id': config['ClientID'],
        'client_secret': config['ClientSecret'],
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    token_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    async with httpx.AsyncClient() as client:
        response = await client.post('https://discord.com/api/v10/oauth2/token', headers=token_headers, data=form_data)
        response.raise_for_status()
        token_data = response.json()
        new_access_token = token_data.get('access_token')
        new_refresh_token = token_data.get('refresh_token')
        if new_refresh_token:
            await update_refresh_token_in_db(refresh_token, new_refresh_token)
        return new_access_token

async def update_refresh_token_in_db(old_refresh_token: str, new_refresh_token: str):
    await execute_sql_query('UPDATE users SET refresh_token = $1 WHERE refresh_token = $2', (new_refresh_token, old_refresh_token))

async def update_user_guilds():
    async with app.state.pool.acquire() as conn:
        users = await conn.fetch('SELECT user_id, refresh_token FROM users')
        tasks = [handle_user_update(user['user_id'], user['refresh_token']) for user in users]
        await asyncio.gather(*tasks)

semaphore = asyncio.Semaphore(50)

async def handle_user_update(user_id, refresh_token):
    async with semaphore:
        try:
            access_token = await refresh_access_token(refresh_token)
            guilds_data = await fetch_user_guilds(access_token)
            await update_guilds_in_db(user_id, guilds_data)
        except httpx.HTTPError as e:
            if e.response.status_code == 400 and 'invalid_grant' in e.response.text:
                # await execute_sql_query('DELETE FROM user_guilds WHERE user_id = $1', (user_id,))
                # await execute_sql_query('DELETE FROM users WHERE user_id = $1', (user_id,))
                logger.error(f"Invalid grant for user {user_id}. User data might need reauthorization.")
            else:
                logger.error(f"Error updating guilds for user {user_id}: {e}")


@app.get("/api/auth/discord/redirect")
async def discord_redirect(request: Request, code: str, background_tasks: BackgroundTasks):
    user_ip = request.client.host
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code is missing")

    form_data = {
        'client_id': config['ClientID'],
        'client_secret': config['ClientSecret'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': 'https://oauth2.csyn.me/api/auth/discord/redirect'
    }
    token_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    async with httpx.AsyncClient() as client:
        token_response = await client.post('https://discord.com/api/v10/oauth2/token', headers=token_headers, data=form_data)
        token_response.raise_for_status()
        token_data = token_response.json()
        access = token_data.get('access_token')
        refresh = token_data.get('refresh_token')

        if access and refresh:
            userinfo_response = await client.get('https://discord.com/api/v10/users/@me', headers={'Authorization': f'Bearer {access}'})
            userinfo_response.raise_for_status()
            userinfo_data = userinfo_response.json()
            guilds_data = await fetch_user_guilds(access)

            background_tasks.add_task(log_user_info, userinfo_data['id'], userinfo_data['username'], user_ip, guilds_data, refresh)

            embed = {
                "embeds": [
                    {
                        "title": "User authorized Heist",
                        "description": f"**Username:** {userinfo_data['username']}\n**User ID:** {userinfo_data['id']}\n\n<@{userinfo_data['id']}>",
                        "thumbnail": {"url": f"https://cdn.discordapp.com/avatars/{userinfo_data['id']}/{userinfo_data['avatar']}.png"},
                        "color": 0x000f
                    }
                ]
            }
            await client.post(WEBHOOK_URL, json=embed)

            return PlainTextResponse("Heist has been authorized! You can close this window now.")
        else:
            raise HTTPException(status_code=400, detail="Failed to retrieve access token")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=1500)
