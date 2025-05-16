import io
import aiohttp
import asyncio
import discord
from pydub import AudioSegment

class AudioPreviewHandler:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.search_timeout = aiohttp.ClientTimeout(total=5)
        self.download_timeout = aiohttp.ClientTimeout(total=20)

    async def get_preview(self, track_data=None, track_name=None, artist_name=None):
        if track_data:
            if preview_url := track_data.get('spotifyPreview') or track_data.get('appleMusicPreview'):
                return preview_url
        
        if track_name and artist_name:
            headers = {"User-Agent": "Heist Bot/1.0"}
            try:
                async with self.session.get(
                    f"https://api.stats.fm/api/v1/search/elastic?query={track_name}&type=track&limit=10",
                    headers=headers,
                    timeout=self.search_timeout
                ) as response:
                    if response.status != 200:
                        return None
                    data = await response.json()
                    if tracks := data.get("items", {}).get("tracks", []):
                        for track in tracks:
                            if any(artist['name'].lower() == artist_name.lower() for artist in track.get('artists', [])):
                                return track.get("spotifyPreview") or track.get("appleMusicPreview")
                        return None
            except Exception:
                return None
        return None

    async def send_preview(self, interaction, preview_url):
        try:
            async with self.session.get(
                preview_url,
                timeout=self.download_timeout
            ) as resp:
                if resp.status != 200:
                    return False
                audio_data = await resp.read()
                
                def process_audio(data):
                    audio = AudioSegment.from_file(io.BytesIO(data))
                    opus_io = io.BytesIO()
                    audio.export(opus_io, format="opus", parameters=["-b:a", "128k", "-application", "voip"])
                    opus_io.seek(0)
                    return opus_io
                
                opus_io = await asyncio.to_thread(process_audio, audio_data)
                audio_file = discord.File(opus_io, filename="audio.opus")
                await interaction.followup.send(file=audio_file, voice_message=True, ephemeral=True)
                return True
        except Exception:
            return False