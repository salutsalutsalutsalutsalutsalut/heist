import asyncio
import aiohttp
import logging
from bs4 import BeautifulSoup
import tldextract
from googlesearch import search
from dataclasses import dataclass
from typing import Optional, Dict, List
from cachetools import TTLCache
from random import choice
import re
import json
import yt_dlp
import os
import uuid
import base64
import datetime
from urllib.parse import urlparse, quote, unquote
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import UserStatusEmpty, UserStatusOnline, UserStatusOffline, UserStatusRecently, UserStatusLastWeek, UserStatusLastMonth
from playwright.async_api import async_playwright
import base64
import time
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class InstagramProfile:
    username: str
    avatar_url: Optional[str]
    followers: str
    following: str
    posts: str
    verified: bool
    bio: Optional[str]
    bio_source: str
    url: str

class InstagramHandler:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.profile_cache = TTLCache(maxsize=100, ttl=300)
        self.request_semaphore = asyncio.Semaphore(10)
        self.cookies = {
            'sessionid': os.getenv('INSTAGRAM_SESSION_ID', ''),
            'csrftoken': os.getenv('INSTAGRAM_CSRF_TOKEN', ''),
            'ds_user_id': os.getenv('INSTAGRAM_DS_USER_ID', ''),
            'ig_did': os.getenv('INSTAGRAM_IG_DID', '')
        }
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Firefox/123.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/122.0.2365.80'
        ]

    def _get_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Pragma': 'no-cache',
            'Referer': 'https://www.instagram.com/',
            'Origin': 'https://www.instagram.com'
        }

    async def _fetch_profile_page(self, username: str) -> str:
        url = f"https://www.instagram.com/{username}/"
        async with self.request_semaphore:
            async with self.session.get(url, headers=self._get_headers(), cookies=self.cookies, timeout=10) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to fetch profile: {response.status}")
                html = await response.text()
                if "Login • Instagram" in html:
                    raise ValueError("Session expired")
                return html

    async def _extract_bio(self, html: str) -> tuple[Optional[str], str]:
        soup = BeautifulSoup(html, 'html.parser')
        def clean_bio(text: str) -> str:
            text = bytes(text, 'utf-8').decode('utf-8')
            text = text.strip('"\'') 
            text = re.sub(r'(?:^|")([^"]*?) on Instagram:', '', text)
            text = re.sub(r'^.*? on Instagram[:\s]*', '', text)
            text = re.sub(r'^[^(]*\(@[\w.]+\)\s*', '', text)
            text = re.sub(r'^@[\w.]+\s*', '', text)
            text = re.sub(r'\\n|\\r|\n|\r', '\n', text)
            text = text.replace('\\"', '"').replace('\\\\', '\\')
            text = re.sub(r'Verification:.*?(?=\n|$)', '', text, flags=re.IGNORECASE)
            text = text.strip()
            text = re.sub(r'^["\']\s*|\s*["\']$', '', text)
            if not text or text == '""':
                return ''
            return text

        tasks = [
            self._extract_bio_from_json(html, clean_bio),
            self._extract_bio_from_meta(html, soup, clean_bio),
            self._extract_bio_from_structured(html, soup, clean_bio)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, tuple) and result[0]:
                return result
                
        return None, "NOT_FOUND"

    async def _extract_bio_from_json(self, html: str, clean_func) -> tuple[Optional[str], str]:
        json_match = re.search(r'"user":\s*({[^}]+})', html)
        if json_match:
            bio_match = re.search(r'"biography":"((?:[^"\\]|\\.)*)"', json_match.group(1))
            if bio_match and bio_match.group(1).strip():
                return clean_func(bio_match.group(1)), "USER_JSON"
        return None, "NOT_FOUND"

    async def _extract_bio_from_meta(self, html: str, soup: BeautifulSoup, clean_func) -> tuple[Optional[str], str]:
        meta = soup.find('meta', {'name': 'description'})
        if meta and meta.get('content'):
            content = meta.get('content')
            parts = re.split(r'\d+(?:,\d+)*\s+(?:Followers|Following|Posts)|Verified account|•', content)
            if parts and not parts[-1].lower().startswith(('follow', 'followers', 'following')):
                return clean_func(parts[-1]), "META_DESCRIPTION"
        return None, "NOT_FOUND"

    async def _extract_bio_from_structured(self, html: str, soup: BeautifulSoup, clean_func) -> tuple[Optional[str], str]:
        structured = soup.find('script', type='application/ld+json')
        if structured:
            try:
                data = json.loads(structured.string)
                if isinstance(data, dict) and 'description' in data:
                    return clean_func(data['description']), "STRUCTURED_DATA"
            except:
                pass
        return None, "NOT_FOUND"

    async def get_profile(self, username: str) -> InstagramProfile:
        cache_key = f"instagram_{username}"
        if cache_key in self.profile_cache:
            return self.profile_cache[cache_key]

        html = await self._fetch_profile_page(username)
        soup = BeautifulSoup(html, "html.parser")

        meta_content = soup.find('meta', {'name': 'description'})
        if not meta_content:
            raise ValueError("Profile data not found")

        content = meta_content['content'].split()
        bio, bio_source = await self._extract_bio(html)
        
        verified = any(
            re.search(pattern, html, re.IGNORECASE) is not None
            for pattern in [
                r'"is_verified"\s*:\s*true',
                r'"isVerified"\s*:\s*true',
                r'"verified"\s*:\s*true',
                r'class="[^"]*verified-badge[^"]*"'
            ]
        )

        avatar_url = None
        meta_tag = soup.find('meta', property='og:image')
        if meta_tag:
            avatar_url = meta_tag['content']

        profile = InstagramProfile(
            username=username,
            avatar_url=avatar_url,
            followers=content[0],
            following=content[2],
            posts=content[4],
            verified=verified,
            bio=bio,
            bio_source=bio_source,
            url=f"https://www.instagram.com/{username}/"
        )

        self.profile_cache[cache_key] = profile
        return profile

@dataclass
class TikTokTrendingVideo:
    title: str
    author_id: str
    author_username: str
    author_nickname: str
    video_url: str
    likes: str
    comments: str
    shares: str
    cover_url: str

class TikTokScraper:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.api_base = "https://tikwm.com/api"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
        }

    async def get_trending_videos(self, region: str = "US", count: int = 12) -> List[TikTokTrendingVideo]:
        try:
            async with self.session.post(
                f"{self.api_base}/feed/list",
                json={
                    "region": region,
                    "count": count,
                    "cursor": 0,
                    "web": 1,
                    "hd": 1
                }) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")

                data = await response.json()
                
                if data.get("code") != 0:
                    raise ValueError(data.get("msg", "API returned error"))

                trending_videos = []
                for video in data["data"]:
                    trending_videos.append(TikTokTrendingVideo(
                        title=video.get("title", ""),
                        likes=str(video.get("digg_count", 0)),
                        comments=str(video.get("comment_count", 0)),
                        shares=str(video.get("share_count", 0)),
                        author_id=video["author"]["id"],
                        author_username=video["author"]["unique_id"],
                        author_nickname=video["author"]["nickname"],
                        video_url=f"https://www.tiktok.com/@{video['author']['unique_id']}/video/{video['id']}",
                        cover_url=video.get("cover", "")
                    ))

                return trending_videos

        except Exception as e:
            raise ValueError(f"Failed to fetch trending videos: {str(e)}")

class TelegramHandler:
    def __init__(self):
        self.api_id = int(os.getenv('TELEGRAM_API_ID', 0))
        self.api_hash = os.getenv('TELEGRAM_API_HASH', '')
        self.session_string = os.getenv('TELEGRAM_SESSION', '')
        self.phone = os.getenv('TELEGRAM_PHONE', '')
        self.client = None

    async def initialize(self):
        if not self.session_string:
            raise ValueError("Telegram session string not configured")
            
        self.client = TelegramClient(StringSession(self.session_string), self.api_id, self.api_hash)
        await self.client.connect()
        
        if not await self.client.is_user_authorized():
            if not self.phone:
                raise ValueError("Phone number required for authorization")
                
            await self.client.send_code_request(self.phone)
            code = input('Enter the Telegram code: ')
            await self.client.sign_in(self.phone, code)
            
            self.session_string = self.client.session.save()
            os.environ['TELEGRAM_SESSION'] = self.session_string

    async def get_user_info(self, username: str):
        if not self.client:
            await self.initialize()
            
        entity = await self.client.get_entity(username)
        full_user = await self.client(GetFullUserRequest(entity))
        photos = await self.client.get_profile_photos(entity)
        is_premium = getattr(full_user.users[0], 'premium', False)
        bio = getattr(full_user.full_user, 'about', None)
        
        last_seen = None
        if hasattr(entity, 'status'):
            if isinstance(entity.status, UserStatusOnline):
                last_seen = "Online"
            elif isinstance(entity.status, UserStatusOffline):
                last_seen = entity.status.was_online.timestamp()
            elif isinstance(entity.status, UserStatusEmpty):
                last_seen = "Hidden or never online"
            elif isinstance(entity.status, (UserStatusRecently, UserStatusLastWeek, UserStatusLastMonth)):
                last_seen = self._get_telegram_user_status(entity.status)
        
        return {
            'id': entity.id,
            'first_name': entity.first_name,
            'last_name': entity.last_name,
            'is_premium': is_premium,
            'bio': bio,
            'username': entity.username,
            'last_seen': last_seen,
            'profile_photos': [await self._get_telegram_photo(photo) for photo in photos]
        }

    async def _get_telegram_photo(self, photo):
        file = await self.client.download_media(photo, file=bytes, thumb=-1)
        return base64.b64encode(file).decode('utf-8')

    def _get_telegram_user_status(self, status):
        if isinstance(status, UserStatusEmpty): 
            return "never" 
        elif isinstance(status, UserStatusOnline): 
            return "now" 
        elif isinstance(status, UserStatusOffline): 
            return status.was_online.isoformat() 
        elif isinstance(status, UserStatusRecently): 
            return "recently" 
        elif isinstance(status, UserStatusLastWeek): 
            return "last week" 
        elif isinstance(status, UserStatusLastMonth): 
            return "last month"

class YouTubeHandler:
    def __init__(self, temp_dir: str = "/heist/temp"):
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)

    async def download_shorts(self, url: str) -> str:
        unique_id = str(uuid.uuid4())
        safe_filename = f"heist_{unique_id}.mp4"
        output_file = os.path.join(self.temp_dir, safe_filename)
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_file,
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4'
        }

        loop = asyncio.get_event_loop()
        def run_ytdl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, True)
        
        await loop.run_in_executor(None, run_ytdl)
            
        if os.path.exists(output_file):
            return output_file
        raise FileNotFoundError(f"Downloaded file not found at {output_file}")

class PinterestHandler:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.cookies = {
            'sessionid': os.getenv('PINTEREST_SESSION_ID', ''),
            'csrftoken': os.getenv('PINTEREST_CSRF_TOKEN', ''),
            'ds_user_id': os.getenv('PINTEREST_DS_USER_ID', ''),
            'ig_did': os.getenv('PINTEREST_IG_DID', '')
        }
        self.headers = {
            "accept": "application/json, text/javascript, */*, q=0.01",
            "accept-language": "en-US,en;q=0.9",
            "priority": "u=1, i",
            "referer": "https://ro.pinterest.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/116.0.0.0",
            "x-app-version": "c056fb7",
            "x-pinterest-appstate": "active",
            "x-pinterest-pws-handler": "www/index.js",
            "x-requested-with": "XMLHttpRequest"
        }

    async def search_images(self, query: str) -> List[str]:
        equery = quote(query)
        api_url = f"https://ro.pinterest.com/resource/BaseSearchResource/get/?source_url=%2Fsearch%2Fpins%2F%3Fq%3D{equery}%26rs%3Dtyped&data=%7B%22options%22%3A%7B%22applied_unified_filters%22%3Anull%2C%22appliedProductFilters%22%3A%22---%22%2C%22article%22%3Anull%2C%22auto_correction_disabled%22%3Afalse%2C%22corpus%22%3Anull%2C%22customized_rerank_type%22%3Anull%2C%22domains%22%3Anull%2C%22dynamicPageSizeExpGroup%22%3A%22enabled_350_18capped%22%2C%22filters%22%3Anull%2C%22journey_depth%22%3Anull%2C%22page_size%22%3A%229%22%2C%22query%22%3A%22{equery}%22%2C%22redux_normalize_feed%22%3Atrue%2C%22scope%22%3A%22pins%22%2C%22source_url%22%3A%22%2Fsearch%2Fpins%2F%3Fq%3D{equery}%26rs%3Dtyped%22%7D%2C%22context%22%3A%7B%7D%7D&_=1734203755445"
        
        async with self.session.get(api_url, headers=self.headers, cookies=self.cookies) as response:
            if response.status != 200:
                raise ValueError(f"Failed to fetch Pinterest results: {response.status}")
            
            data = await response.json()
            results = data.get("resource_response", {}).get("data", {}).get("results", [])
            return [result["images"]["orig"]["url"] for result in results if result.get("images", {}).get("orig", {}).get("url")]

    async def get_pin_details(self, url: str) -> dict:
        parsed = urlparse(url)
        if parsed.netloc.endswith("pinterest.com") and parsed.path.startswith("/pin/"):
            pin_id = parsed.path.split('/')[2]
        elif parsed.netloc.endswith("pin.it"):
            pin_id = parsed.path.lstrip('/')
        else:
            raise ValueError("Invalid Pinterest URL")

        api_url = f"https://ro.pinterest.com/resource/PinResource/get/?source_url=%2Fpin%2F{pin_id}%2Ffeedback%2F%3Finvite_code%3De39cd0819eea42a9a3f54cefda573aed%26sender_id%3D547680142093334810&data=%7B%22options%22%3A%7B%22id%22%3A%22{pin_id}%22%2C%22field_set_key%22%3A%22auth_web_main_pin%22%2C%22noCache%22%3Atrue%2C%22fetch_visual_search_objects%22%3Atrue%7D%2C%22context%22%3A%7B%7D%7D&_=1733881746715"

        async with self.session.get(api_url, headers=self.headers, cookies=self.cookies) as response:
            if response.status != 200:
                raise ValueError(f"Failed to fetch pin: {response.status}")
            
            data = await response.json()
            pin_data = data['resource_response']['data']
            creator_data = pin_data.get('pinner') or pin_data.get('origin_pinner') or {}
            
            return {
                'username': creator_data.get('username', 'unknown'),
                'fullName': creator_data.get('full_name', 'Unknown Creator'),
                'followerCount': creator_data.get('follower_count', 0),
                'verifiedIdentity': creator_data.get('verified_identity', {}).get('verified', False),
                'avatar': creator_data.get('image_medium_url', ''),
                'title': pin_data.get('title', pin_data.get('seo_title', 'No title')),
                'reactions': pin_data.get('reaction_counts', {}).get('1', 0),
                'image': pin_data.get('images', {}).get('orig', {}).get('url', ''),
                'commentsCount': pin_data.get('aggregated_pin_data', {}).get('comment_count', 0),
                'description': pin_data.get('description', pin_data.get('seo_description', 'No description')),
                'annotations': pin_data.get('visual_objects', []),
                'board': {
                    'name': pin_data.get('board', {}).get('name', 'Unknown Board'),
                    'description': pin_data.get('board', {}).get('description', ''),
                    'followerCount': pin_data.get('board', {}).get('follower_count', 0),
                    'id': pin_data.get('board', {}).get('id', ''),
                    'url': f"https://www.pinterest.com{pin_data.get('board', {}).get('url', '')}" if pin_data.get('board', {}).get('url') else ''
                },
                'createdAt': pin_data.get('created_at', ''),
                'link': pin_data.get('link', f"https://www.pinterest.com/pin/{pin_id}"),
                'altText': pin_data.get('auto_alt_text', 'N/A'),
                'repinCount': pin_data.get('repin_count', 0)
            }

@dataclass
class BraveSearchResult:
    content: str
    followup_links: List[str]
    followup_images: List[str]
    followup_titles: List[str]

@dataclass
class BraveImageResult:
    image_urls: List[str]
    sources: List[str]
    titles: List[str]

class BraveSearchHandler:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.cache = TTLCache(maxsize=1000, ttl=300)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def initialize(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=["--disable-gl-drawing-for-tests", "--no-sandbox", "--disable-css", "--use-angle=default"]
        )
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()

    async def search_images(self, query: str, safe_search: bool = True) -> BraveImageResult:
        cache_key = f"brave_images:{query}:{safe_search}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        if not self.page:
            await self.initialize()

        base_url = "https://search.brave.com"
        search_url = f"{base_url}/images?q={query}&source=web"
        
        if safe_search:
            await self.context.add_cookies([{
                "name": "safesearch",
                "value": "strict",
                "domain": "search.brave.com",
                "path": "/",
                "secure": True,
                "sameSite": "Lax"
            }])
        else:
            await self.context.clear_cookies()

        await self.page.goto(search_url, timeout=50000)
        
        if await self.page.query_selector('#bad-results-info-banner'):
            return BraveImageResult([], [], [])

        try:
            await self.page.wait_for_selector('.image-thumbnail', timeout=50000)
        except:
            return BraveImageResult([], [], [])

        image_elements = await self.page.query_selector_all('.image-thumbnail')
        image_urls = []
        sources = []
        titles = []

        for image in image_elements:
            try:
                img_url = await image.get_attribute('data-thumbnail-src')
                source_element = await image.query_selector('.img-source .text-ellipsis')
                source = await source_element.inner_text() if source_element else None
                title = await image.get_attribute('alt') or None
                
                if img_url:
                    image_urls.append(img_url)
                    sources.append(source)
                    titles.append(title)
            except Exception as e:
                logging.warning(f"Error processing image element: {e}")
                continue

        result = BraveImageResult(image_urls, sources, titles)
        self.cache[cache_key] = result
        return result

class SpotifyHandler:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.client_id = os.getenv('SPOTIFY_CLIENT_ID', '')
        self.client_secret = os.getenv('SPOTIFY_SECRET', '')
        self.token_info = {"access_token": None, "expiration_time": 0}
        self.cache = TTLCache(maxsize=1000, ttl=3600)

    async def get_access_token(self) -> str:
        if time.time() < self.token_info["expiration_time"]:
            return self.token_info["access_token"]

        auth_str = f"{self.client_id}:{self.client_secret}"
        b64_auth_str = base64.b64encode(auth_str.encode()).decode()

        headers = {
            "Authorization": f"Basic {b64_auth_str}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials"}

        async with self.session.post("https://accounts.spotify.com/api/token", headers=headers, data=data) as response:
            if response.status != 200:
                raise ValueError("Failed to get Spotify access token")
            
            data = await response.json()
            self.token_info = {
                "access_token": data["access_token"],
                "expiration_time": time.time() + data["expires_in"]
            }
            return self.token_info["access_token"]

    async def search_track(self, track_name: str, artist_name: str) -> dict:
        cache_key = f"spotify_track:{track_name}:{artist_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        access_token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "q": f"track:{track_name} artist:{artist_name}",
            "type": "track",
            "limit": 1
        }

        async with self.session.get("https://api.spotify.com/v1/search", headers=headers, params=params) as response:
            if response.status != 200:
                raise ValueError("Failed to search Spotify tracks")
            
            data = await response.json()
            tracks = data.get("tracks", {}).get("items", [])
            if not tracks:
                return {}

            track = tracks[0]
            result = {
                "title": track["name"],
                "artist": track["artists"][0]["name"],
                "spotify_link": track["external_urls"]["spotify"],
                "cover_art": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
                "preview_url": track.get("preview_url")
            }

            self.cache[cache_key] = result
            return result

    async def get_artist_cover(self, artist_name: str) -> Optional[str]:
        cache_key = f"spotify_artist:{artist_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        access_token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "q": f"artist:{artist_name}",
            "type": "artist",
            "limit": 1
        }

        async with self.session.get("https://api.spotify.com/v1/search", headers=headers, params=params) as response:
            if response.status != 200:
                raise ValueError("Failed to search Spotify artists")
            
            data = await response.json()
            artists = data.get("artists", {}).get("items", [])
            if not artists:
                return None

            cover_art = artists[0]["images"][0]["url"] if artists[0]["images"] else None
            self.cache[cache_key] = cover_art
            return cover_art

class SocialsManager:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.instagram = InstagramHandler(session)
        self.tiktok = TikTokScraper(session)
        self.youtube = YouTubeHandler()
        self.pinterest = PinterestHandler(session)
        self.brave = BraveSearchHandler(session)
        self.spotify = SpotifyHandler(session) if os.getenv('SPOTIFY_CLIENT_ID') else None
        self.telegram = TelegramHandler() if os.getenv('TELEGRAM_API_ID') else None

    async def search_pinterest(self, query: str) -> List[str]:
        return await self.pinterest.search_images(query)

    async def get_pinterest_pin(self, url: str) -> dict:
        return await self.pinterest.get_pin_details(url)

    async def get_instagram_user(self, username: str) -> InstagramProfile:
        return await self.instagram.get_profile(username)

    async def get_tiktok_trending(self, limit: int = 12, region: str = "US") -> List[TikTokTrendingVideo]:
        return await self.tiktok.get_trending_videos(region=region, count=limit)

    async def get_telegram_user(self, username: str) -> dict:
        if not self.telegram:
            raise RuntimeError("Telegram credentials not configured")
        return await self.telegram.get_user_info(username)

    async def download_youtube_short(self, url: str) -> str:
        return await self.youtube.download_shorts(url)

    async def search_spotify_track(self, track_name: str, artist_name: str) -> dict:
        if not self.spotify:
            raise RuntimeError("Spotify credentials not configured")
        return await self.spotify.search_track(track_name, artist_name)

    async def get_spotify_artist_cover(self, artist_name: str) -> Optional[str]:
        if not self.spotify:
            raise RuntimeError("Spotify credentials not configured")
        return await self.spotify.get_artist_cover(artist_name)

    async def close(self):
        if self.telegram and self.telegram.client:
            await self.telegram.client.disconnect()
        if hasattr(self.brave, 'context') and self.brave.context:
            await self.brave.context.close()
        if hasattr(self.brave, 'browser') and self.brave.browser:
            await self.brave.browser.close()
        if hasattr(self.brave, 'playwright') and self.brave.playwright:
            await self.brave.playwright.stop()