import aiohttp
import base64
import os
import time
import asyncio
import logging
from dotenv import dotenv_values
from aiofiles import open as aio_open
from fastapi import FastAPI, Depends, Request, HTTPException, BackgroundTasks, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from utils.db import get_db_connection
from pydantic import BaseModel
from urllib.parse import urlparse
import asyncpg
from datetime import datetime, timedelta
import os

config = dotenv_values(".env")
LASTFM_API_KEY = config["LASTFM_API_KEY"]

app = FastAPI(docs_url=None)
app.locks = {}
config = dotenv_values(".env")
DATA_DB = config["DATA_DB"]
SPOTIFY_CLIENT_ID = config["SPOTIFY_CLIENT_ID"]
SPOTIFY_CLIENT_SECRET = config["SPOTIFY_SECRET"]
SPOTIFY_REDIRECT_URI = config["SPOTIFY_REDIRECT"]

async def init_db():
    conn = await asyncpg.connect(dsn=DATA_DB)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS spotify (
            user_id TEXT PRIMARY KEY,
            refresh_token TEXT,
            access_token TEXT,
            token_expiry BIGINT
        )
    ''')
    await conn.close()

@app.on_event("startup")
async def startup_event():
    await init_db()

class ExpiringCache:
    def __init__(self, ttl: int):
        self.ttl = ttl
        self._cache = {}

    def get(self, key):
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry['time'] < self.ttl:
                return entry['value']
            else:
                del self._cache[key]
        return None

    def set(self, key, value):
        self._cache[key] = {'value': value, 'time': time.time()}
        
    def delete(self, key):
        if key in self._cache:
            del self._cache[key]

app.cache = ExpiringCache(ttl=3600)

async def load_api_keys():
    conn = await asyncpg.connect(dsn=DATA_DB)
    try:
        api_keys = await conn.fetch("SELECT api_key FROM api_keys")
        return [row['api_key'] for row in api_keys]
    finally:
        await conn.close()

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    api_keys = await load_api_keys()
    if not api_key_header.startswith("Heist-"):
        raise HTTPException(status_code=403, detail="Invalid API Key. Request one here: https://discord.gg/heistbot")
    if api_key_header in api_keys:
        return api_key_header
    else:
        raise HTTPException(status_code=403, detail="Invalid API Key. Request one here: https://discord.gg/heistbot")

class SpotifySong(BaseModel):
    artist: str
    title: str
    image: str
    download_url: str

async def delete_file_after_delay(file_path: str, delay_seconds: int):
    await asyncio.sleep(delay_seconds)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Deleted file: {file_path}")
        else:
            logging.warning(f"File not found for deletion: {file_path}")
    except Exception as e:
        logging.error(f"Error deleting file {file_path}: {e}")

client_id = config["SPOTIFY_CLIENT_ID"]
client_secret = config["SPOTIFY_SECRET"]
token_info = {"access_token": None, "expiration_time": 0}

async def get_spotify_access_token() -> dict:
    auth_str = f"{client_id}:{client_secret}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth_str}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://accounts.spotify.com/api/token", headers=headers, data=data) as response:
            response_data = await response.json()
            access_token = response_data["access_token"]
            expires_in = response_data["expires_in"]
            expiration_time = time.time() + expires_in
            return {
                "access_token": access_token,
                "expiration_time": expiration_time
            }

async def read_lastfm_track(api_key, username, limit=1):
    url = f'http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={username}&api_key={api_key}&format=json&limit={limit}'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            if 'track' in data['recenttracks'] and data['recenttracks']['track']:
                return data['recenttracks']['track'][0]
            else:
                return None

async def search_spotify_track(access_token, track_name, artist_name):
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {
        'q': f'track:{track_name} artist:{artist_name}',
        'type': 'track'
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get("https://api.spotify.com/v1/search", params=params) as response:
            if response.status != 200:
                return []
            data = await response.json()
            return data.get('tracks', {}).get('items', [])

def create_output_dictionary(lastfm_track, spotify_track):
    return {
        'title': lastfm_track.get('name'),
        'artist': lastfm_track.get('artist', {}).get('#text'),
        'spotify_link': spotify_track[0]['external_urls']['spotify'] if spotify_track else None,
        'cover_art': spotify_track[0]['album']['images'][0]['url'] if spotify_track and 'album' in spotify_track[0] and 'images' in spotify_track[0]['album'] and len(spotify_track[0]['album']['images']) > 0 else None,
        'preview_url': spotify_track[0].get('preview_url') if spotify_track else None
    }

async def download_preview(preview_url: str, track_id: str):
    download_path = os.path.join("./temp", f"{track_id}_p.mp3")
    async with aiohttp.ClientSession() as session:
        async with session.get(preview_url) as response:
            if response.status == 200:
                download_byte = await response.read()
                async with aio_open(download_path, "wb") as f:
                    await f.write(download_byte)
                return download_path
    return None

@app.get("/api/spotify/artist", dependencies=[Depends(get_api_key)])
async def get_spotify_artist_cover(artist_name: str, request: Request) -> JSONResponse:
    access_token = await get_spotify_access_token()
    if access_token:
        headers = {'Authorization': f'Bearer {access_token["access_token"]}'}
        params = {'q': f'artist:{artist_name}', 'type': 'artist'}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get("https://api.spotify.com/v1/search", params=params) as response:
                if response.status != 200:
                    return JSONResponse(content={'error': 'Failed to fetch artist data from Spotify'}, status_code=500)
                data = await response.json()
                artists = data.get('artists', {}).get('items', [])
                if artists:
                    artist = artists[0]
                    cover_art = artist['images'][0]['url'] if 'images' in artist and len(artist['images']) > 0 else None
                    return JSONResponse(content={'cover_art': cover_art})
                return JSONResponse(content={'error': 'No artists found'}, status_code=404)
    return JSONResponse(content={'error': 'Failed to obtain Spotify access token'}, status_code=500)

@app.get("/api/search", dependencies=[Depends(get_api_key)])
async def search(lastfm_username: str, artist_name: str, background_tasks: BackgroundTasks, request: Request, album_name: str = None, track_name: str = None):
    access_token = await get_spotify_access_token()
    if access_token:
        if album_name and not track_name:
            spotify_albums = await search_spotify_album(access_token['access_token'], album_name, artist_name)
            output_dict = create_output_dictionary_album({'name': album_name, 'artist': {'#text': artist_name}}, spotify_albums)
        else:
            spotify_tracks = await search_spotify_track(access_token['access_token'], track_name, artist_name)
            output_dict = create_output_dictionary_track({'name': track_name, 'artist': {'#text': artist_name}}, spotify_tracks)

        if output_dict.get('spotify_link'):
            if album_name and not track_name:
                album_id = output_dict['spotify_link'].split('/')[-1]
                output_dict['download_url'] = str(request.url_for("spotify_album_cover", id=album_id))
            else:
                track_id = output_dict['spotify_link'].split('/')[-1]
                preview_url = output_dict.get('preview_url')
                if preview_url:
                    preview_path = await download_preview(preview_url, track_id)
                    if preview_path:
                        background_tasks.add_task(delete_file_after_delay, preview_path, 15)
                output_dict['download_url'] = str(request.url_for("spotify_downloads", id=track_id))
            
            return JSONResponse(content=output_dict)
        
        return JSONResponse(content={'error': 'No Spotify content found'}, status_code=404)
    else:
        return JSONResponse(content={'error': 'Failed to obtain Spotify access token'}, status_code=500)


async def search_spotify_album(access_token, album_name, artist_name):
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {
        'q': f'album:{album_name} artist:{artist_name}',
        'type': 'album'
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get("https://api.spotify.com/v1/search", params=params) as response:
            if response.status != 200:
                return []
            data = await response.json()
            return data.get('albums', {}).get('items', [])

def create_output_dictionary_album(lastfm_album, spotify_albums):
    return {
        'title': lastfm_album.get('name'),
        'artist': lastfm_album.get('artist', {}).get('#text'),
        'spotify_link': spotify_albums[0]['external_urls']['spotify'] if spotify_albums else None,
        'cover_art': spotify_albums[0]['images'][0]['url'] if spotify_albums and 'images' in spotify_albums[0] and len(spotify_albums[0]['images']) > 0 else None,
    }

def create_output_dictionary_track(lastfm_track, spotify_tracks):
    return {
        'title': lastfm_track.get('name'),
        'artist': lastfm_track.get('artist', {}).get('#text'),
        'spotify_link': spotify_tracks[0]['external_urls']['spotify'] if spotify_tracks else None,
        'cover_art': spotify_tracks[0]['album']['images'][0]['url'] if spotify_tracks and 'album' in spotify_tracks[0] and 'images' in spotify_tracks[0]['album'] and len(spotify_tracks[0]['album']['images']) > 0 else None,
        'preview_url': spotify_tracks[0].get('preview_url') if spotify_tracks else None
    }

@app.get("/spotify/album_cover/{id}")
async def spotify_album_cover(id: str, request: Request):
    global token_info
    if time.time() > token_info["expiration_time"]:
        token_info = await get_spotify_access_token()

    access_token = token_info["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f"https://api.spotify.com/v1/albums/{id}") as response:
            if response.status != 200:
                return JSONResponse(content={'error': 'Failed to fetch album data from Spotify'}, status_code=500)
            data = await response.json()
            if 'images' in data and len(data['images']) > 0:
                return JSONResponse(content={'cover_art': data['images'][0]['url']})
            return JSONResponse(content={'error': 'No album cover found'}, status_code=404)

@app.get("/spotify/downloads/{id}")
async def spotify_downloads(id: str, request: Request, background_tasks: BackgroundTasks):
    path = os.path.join("./temp", f"{id}.mp3")
    if os.path.exists(path):
        return FileResponse(path, media_type="audio/mpeg")

    cache = app.cache.get(f"spotify-{id}")
    if cache:
        url = cache['url']
        async with aiohttp.ClientSession() as cs:
            async with cs.get(url) as r:
                download_byte = await r.read()

        async with aio_open(path, "wb") as f:
            await f.write(download_byte)

        background_tasks.add_task(delete_file_after_delay, path, 15)
        return FileResponse(path, media_type="audio/mpeg")

    return JSONResponse(content="Content Not Available", status_code=404)

@app.get("/spotify/song", response_model=SpotifySong, dependencies=[Depends(get_api_key)])
async def spotify_song(request: Request, url: str, background_tasks: BackgroundTasks) -> JSONResponse:
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')
    if len(path_parts) > 2 and path_parts[-2] == 'track':
        track_id = path_parts[-1]
    else:
        raise HTTPException(status_code=400, detail="Invalid Spotify URL.")

    clean_url = f"https://open.spotify.com/track/{track_id}&type=track&limit=1"

    async with app.locks.setdefault(request.client.host, asyncio.Lock()):
        if cache := app.cache.get(f"spotify-{clean_url}"):
            return JSONResponse(content=cache)

        global token_info
        if time.time() > token_info["expiration_time"]:
            token_info = await get_spotify_access_token()

        access_token = token_info["access_token"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession(headers=headers) as cs:
            async with cs.get(f"https://api.spotify.com/v1/tracks/{track_id}") as r:
                track_info = await r.json()
                print(track_info)

                if 'artists' not in track_info:
                    raise HTTPException(status_code=500, detail="Invalid response from Spotify API.")
                
                artist = track_info['artists'][0]['name']
                title = track_info['name']
                image = track_info['album']['images'][0]['url']
                duration_ms = track_info.get('duration_ms')

                payload = {
                    "artist": artist,
                    "title": title,
                    "image": image,
                    "download_url": str(request.url_for("spotify_downloads", id=track_id)),
                    "duration_ms": duration_ms
                }

                app.cache.set(f"spotify-{clean_url}", payload)
                background_tasks.add_task(delete_file_after_delay, os.path.join("./temp", f"{track_id}.mp3"), 15)
                return JSONResponse(content=payload)

@app.get("/spotify/callback")
async def spotify_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")
    
    if error:
        raise HTTPException(status_code=400, detail=f"Spotify authorization failed: {error}")
    
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")
    
    async with get_db_connection() as conn:
        user_id = await conn.fetchval(
            "SELECT user_id FROM spotify_auth_states WHERE state = $1",
            state
        )
        
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        await conn.execute(
            "DELETE FROM spotify_auth_states WHERE state = $1",
            state
        )
    
    async with aiohttp.ClientSession() as session:
        auth_header = base64.b64encode(
            f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth_header}"
        }
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI
        }
        
        async with session.post(
            "https://accounts.spotify.com/api/token",
            headers=headers,
            data=data
        ) as response:
            data = await response.json()
            if response.status != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Spotify error: {data.get('error_description', 'Unknown error')}"
                )
            
            access_token = data["access_token"]
            refresh_token = data["refresh_token"]
            expires_at = datetime.now() + timedelta(seconds=data["expires_in"])
            
            async with session.get(
                "https://api.spotify.com/v1/me",
                headers={"Authorization": f"Bearer {access_token}"}
            ) as user_response:
                user_data = await user_response.json()
                if user_response.status != 200:
                    raise HTTPException(status_code=400, detail="Failed to fetch user data")
                
                product = user_data.get("product")
                if product != "premium":
                    raise HTTPException(status_code=400, detail="Spotify Premium required")
    
    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT INTO spotify_auth (user_id, access_token, refresh_token, expires_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
            SET access_token = $2, refresh_token = $3, expires_at = $4
            """,
            user_id, access_token, refresh_token, expires_at
        )
    
    return RedirectResponse(url="https://discord.com/channels/@me")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=2053)