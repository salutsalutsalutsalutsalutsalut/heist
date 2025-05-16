import asyncio
import discord
from discord.ext import commands, tasks
import uuid
import logging
import os
from datetime import datetime
import aiohttp
from aiohttp import web
import random
from urllib.parse import urlparse

TOKEN = "MTA5NTAxNDM1NzgxOTIxMTg1OA.GAiTnb.gDYclvvl2VlTwBJOcWc12HTq9yJMP9JAnBKfso"
GUILD_ID = 1215729734215016469
PFP_DIR = "pfps"
BANNER_DIR = "banners"
GIFS_DIR = "gifs"
LOG_FILE = 'bot.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s /> %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

os.makedirs(PFP_DIR, exist_ok=True)
os.makedirs(BANNER_DIR, exist_ok=True)
os.makedirs(GIFS_DIR, exist_ok=True)

def clear_existing_images():
    try:
        prompt = input("Do you want to delete all existing images in the folders? (y/n): ").strip().lower()
        if prompt == "y":
            for folder in [PFP_DIR, BANNER_DIR, GIFS_DIR]:
                for file in os.listdir(folder):
                    file_path = os.path.join(folder, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        logger.info(f"Deleted file: {file_path}")
            logger.info("All existing images deleted.")
        elif prompt == "n":
            logger.info("Existing images kept.")
        else:
            logger.warning("Invalid input. No files were deleted.")
    except Exception as e:
        logger.error(f"Error clearing images: {e}")

clear_existing_images()

bot = commands.Bot(command_prefix='nsdbijbghisbgsbguiosbugsbuiogs', help_command=None, chunk_guilds_at_startup=False)

@bot.event
async def on_ready():
    try:
        logger.info(f'Bot logged in as {bot.user}')
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="you in your sleep"
            )
        )
        
        if not bot.guilds:
            logger.warning("Bot is not connected to any guilds")
            return

        await process_all_guilds()
        logger.info("Initial member processing completed")

    except Exception as e:
        logger.error(f"Error in on_ready: {e}", exc_info=True)


async def process_member(
    member: discord.Member, 
    member_semaphore: asyncio.Semaphore,
    download_semaphore: asyncio.Semaphore
):
    async with member_semaphore:
        try:
            if not member:
                return
            if member.bot:
                return

            avatar = member.display_avatar
            if not avatar:
                return

            url = str(avatar.url)
            if not url:
                return

            async with download_semaphore:
                if avatar.is_animated():
                    await check_user_gif(url)
                else:
                    await check_user_pfp(url)

        except discord.NotFound:
            logger.debug(f"Member {member.id} not found")
        except discord.HTTPException as e:
            logger.warning(f"HTTP error processing member {member.id}: {e}")
        except Exception as e:
            logger.error(
                f"Error processing member {member.id} ({member}): {e}", 
                exc_info=True
            )

async def process_all_guilds():
    try:
        member_semaphore = asyncio.Semaphore(10)
        download_semaphore = asyncio.Semaphore(10)
        
        for guild in bot.guilds:
            logger.info(f"Processing guild: {guild.name} (ID: {guild.id})")
            logger.info(f"Guild member count: {guild.member_count}")
            
            all_members = await guild.fetch_members(force_scraping=True, cache=True)
            
            member_chunks = [all_members[i:i + 100] for i in range(0, len(all_members), 100)]
            
            for chunk in member_chunks:
                tasks = [
                    process_member(
                        member, 
                        member_semaphore, 
                        download_semaphore
                    ) for member in chunk
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Error processing guilds: {e}", exc_info=True)



async def setup_web_server():
    app = web.Application()
    app.add_routes([
        web.get('/pfps', handle_pfps),
        web.get('/banners', handle_banners),
        web.get('/gifs', handle_gifs),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Web server started on port 8080")

@bot.event
async def on_connect():
    bot.loop.create_task(setup_web_server())

async def download_image(url: str, directory: str, prefix: str) -> str:
    try:
        url = str(url)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = "gif" if prefix == "gif" else "png"
        filename = os.path.join(directory, f"{prefix}_{timestamp}_{uuid.uuid4().hex[:8]}.{extension}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    with open(filename, 'wb') as f:
                        f.write(data)
                    logger.info(f"Downloaded {prefix} from {url} to {filename}")
                    return filename
                logger.error(f"Failed to download {prefix}: HTTP {response.status}")
    except Exception as e:
        logger.error(f"Error downloading {prefix}: {e}")
    return None

async def check_user_pfp(url):
    if url:
        await download_image(url, PFP_DIR, "avatar")

async def check_user_banner(url):
    if url:
        await download_image(url, BANNER_DIR, "banner")

async def check_user_gif(url):
    if url:
        await download_image(url, "gifs", "gif")

async def handle_pfps(request):
    try:
        pfp_files = os.listdir(PFP_DIR)
        selected_pfps = random.sample(pfp_files, min(8, len(pfp_files)))
        return web.json_response({"pfps": selected_pfps})
    except Exception as e:
        logger.error(f"Error handling /pfps: {e}")
        return web.json_response({"error": "Unable to fetch profile pictures"}, status=500)

async def handle_banners(request):
    try:
        banner_files = os.listdir(BANNER_DIR)
        selected_banners = random.sample(banner_files, min(8, len(banner_files)))
        return web.json_response({"banners": selected_banners})
    except Exception as e:
        logger.error(f"Error handling /banners: {e}")
        return web.json_response({"error": "Unable to fetch banners"}, status=500)

async def handle_gifs(request):
    try:
        gif_files = os.listdir("gifs")
        selected_gifs = random.sample(gif_files, min(8, len(gif_files)))
        return web.json_response({"gifs": selected_gifs})
    except Exception as e:
        logger.error(f"Error handling /gifs: {e}")
        return web.json_response({"error": "Unable to fetch gifs"}, status=500)

if __name__ == "__main__":
    try:
        bot.run(TOKEN, reconnect=True)
    except Exception as e:
        logger.error(f"Failed to run bot: {e}")