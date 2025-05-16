import os
import time
import traceback
import asyncio
import aiohttp
import aiofiles
import zipfile
import shutil
import io
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, send_from_directory, abort
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
from playwright.async_api import async_playwright

app = Flask(__name__)

ALLOWED_IP = "37.114.46.135"

def is_private_address(url):
    from urllib.parse import urlparse
    import ipaddress
    import socket

    parsed_url = urlparse(url)
    host = parsed_url.hostname

    if host is None:
        return True

    if any(x in host.lower() for x in ['localhost', '127.', '0.0.0.0', '[::1]', 'localhost.localdomain']):
        return True

    try:
        addrinfo = socket.getaddrinfo(host, None)
        for family, _, _, _, sockaddr in addrinfo:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            
            if (ip.is_private or ip.is_loopback or 
                ip.is_link_local or ip.is_multicast or 
                ip.is_unspecified or ip.is_reserved):
                return True

            dangerous_ranges = [
                '169.254.0.0/16',  # Link-local
                '192.168.0.0/16',  # Private network
                '172.16.0.0/12',   # Private network
                '10.0.0.0/8',      # Private network
                '100.64.0.0/10',   # CGN space
                '192.0.0.0/24',    # IANA special purpose
                '192.0.2.0/24',    # TEST-NET-1
                '198.51.100.0/24', # TEST-NET-2
                '203.0.113.0/24',  # TEST-NET-3
                'fc00::/7',        # Unique local address
                'fe80::/10',       # Link-local
            ]

            for cidr in dangerous_ranges:
                network = ipaddress.ip_network(cidr)
                if ip in network:
                    return True

            if isinstance(ip, ipaddress.IPv6Address):
                if (ip.ipv4_mapped or ip.sixtofour or ip.teredo):
                    return True

    except (socket.gaierror, ValueError, UnicodeError) as e:
        print(f"Error checking address {host}: {e}")
        return True

    return False

async def resolve_redirects(session, url, max_redirects=10):
    redirects = 0
    current_url = url

    while redirects < max_redirects:
        try:
            async with session.get(current_url, allow_redirects=False, timeout=10) as response:
                if response.status not in (301, 302, 303, 307, 308):
                    return current_url

                location = response.headers.get('Location')
                if not location:
                    return current_url

                if not location.startswith(('http://', 'https://')):
                    location = urljoin(str(response.url), location)

                if is_private_address(location):
                    print(f"Blocked redirect to private address: {location}")
                    return None
                
                current_url = location
                redirects += 1

        except Exception as e:
            print(f"Redirect error: {e}")
            return "error"

    print(f"Too many redirects from {url}")
    return None

async def is_zip_bomb(zip_data):
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            total_size = 0
            for zip_info in zf.infolist():
                if zip_info.file_size > 500 * 1024 * 1024:
                    return True
                total_size += zip_info.file_size
                if total_size > 2 * 1024 * 1024 * 1024:
                    return True
    except Exception:
        return True
    return False

async def process_resource(session, resource_url, resource_path):
    if 'localhost' in resource_url:
        return None
    if is_private_address(resource_url):
        return None
    try:
        async with session.get(resource_url, timeout=10, allow_redirects=True) as resource_response:
            final_url = await resolve_redirects(session, resource_url)
            if 'localhost' in final_url or '127.0.0.1' in final_url or is_private_address(final_url):
                return None
            resource_response.raise_for_status()
            content_type = resource_response.headers.get('Content-Type', '')
            content_length = int(resource_response.headers.get('Content-Length', 0))

            if content_length > 10 * 1024 * 1024:
                return None

            if any(ext in resource_url.lower() for ext in ['.zip', '.tar.gz', '.7z', '.rar']):
                zip_data = await resource_response.read()
                if await is_zip_bomb(zip_data):
                    return None

            if 'audio/mpeg' in content_type or resource_url.lower().endswith('.mp3'):
                return None

            os.makedirs(os.path.dirname(resource_path), exist_ok=True)
            async with aiofiles.open(resource_path, 'wb') as f:
                await f.write(await resource_response.read())
            return resource_path
    except Exception as e:
        return None

def is_nsfw(url: str) -> bool:
    nsfw_keywords = ["adult", "porn", "nsfw", "xxx", "sex", "nudity", "cp", "young teen"]
    return any(keyword in url.lower() for keyword in nsfw_keywords)

@app.before_request
def restrict_access():
    client_ip = request.remote_addr
    if client_ip != ALLOWED_IP:
        abort(403, description="Access denied. Your IP is not allowed.")

@app.route('/screenshot', methods=['GET'])
async def screenshot():
    url = request.args.get('url')
    delay = request.args.get('delay', 0)
    proxy = request.args.get('proxy')

    if not url:
        return jsonify({"error": "Missing URL parameter."}), 400

    if is_nsfw(url):
        return jsonify({"error": "This URL contains NSFW content and cannot be processed."}), 403

    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"https://{url}"

    try:
        delay = int(delay)
        if delay > 15:
            return jsonify({"error": "Delay cannot be more than 15 seconds."}), 400
    except ValueError:
        return jsonify({"error": "Invalid delay input."}), 400

    result = await take_screenshot(url, delay, proxy)

    if "error" in result:
        return jsonify(result), 500

    screenshot_path = result.get("screenshot_path")
    if not screenshot_path or not os.path.exists(screenshot_path):
        return jsonify({"error": "Screenshot could not be generated."}), 500

    with open(screenshot_path, "rb") as f:
        image_data = f.read()

    os.remove(screenshot_path)

    return image_data, 200, {"Content-Type": "image/png"}

async def take_screenshot(url: str, delay: int, proxy: str = None):
    timestamp = int(time.time())
    screenshot_path = f"temp/screenshot_{timestamp}.png"

    os.makedirs("temp", exist_ok=True)

    try:
        async with async_playwright() as p:
            browser_args = [
                "--no-sandbox", 
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-dev-shm-usage",
                "--hide-scrollbars",
                "--mute-audio",
                "--disable-blink-features=AutomationControlled"
            ]

            if proxy:
                browser_args.append(f"--proxy-server={proxy}")

            browser = await p.chromium.launch(
                headless=True, 
                args=browser_args
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.92 Safari/537.36",
                locale="en-US",
                device_scale_factor=1.0,
                permissions=[],
                geolocation=None,
                color_scheme='light'
            )

            await context.add_init_script("""
            () => {
                Object.defineProperty(navigator, 'webdriver', { 
                    get: () => undefined 
                });

                if (window.chrome) {
                    window.chrome.runtime = {};
                }

                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer' },
                        { name: 'Shockwave Flash', filename: 'pepflashplayer.dll' },
                        { name: 'Widevine Content Decryption Module', filename: 'widevinecdmadapter.dll' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin' },
                        { name: 'Chrome Video Player', filename: 'internal-video-player' },
                    ],
                });

                Object.defineProperty(navigator, 'languages', { 
                    get: () => ['en-US', 'en']
                });

                Object.defineProperty(navigator, 'hardwareConcurrency', { 
                    get: () => 8 
                });

                const originalReact = navigator.react;
                Object.defineProperty(navigator, 'react', {
                    get: () => originalReact ? { ...originalReact, isAutomated: false } : undefined
                });

                const originalGetContext = HTMLCanvasElement.prototype.getContext;
                HTMLCanvasElement.prototype.getContext = function(contextType, ...args) {
                    const context = originalGetContext.call(this, contextType, ...args);
                    if (contextType === '2d') {
                        const originalGetImageData = context.getImageData;
                        context.getImageData = function(...getImageDataArgs) {
                            const imageData = originalGetImageData.apply(this, getImageDataArgs);
                            for (let i = 0; i < imageData.data.length; i++) {
                                imageData.data[i] += Math.random() > 0.5 ? 1 : -1;
                            }
                            return imageData;
                        };
                    }
                    return context;
                };
            }
            """)

            page = await context.new_page()

            start_time = time.time()
            await page.goto(url, wait_until='networkidle')
            await page.wait_for_timeout(delay * 1000)
            await page.screenshot(
                path=screenshot_path, 
                full_page=False,
                omit_background=True
            )
            end_time = time.time()

            await browser.close()
            return {
                "screenshot_path": screenshot_path,
                "finish_time": end_time - start_time
            }

    except Exception as e:
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
    finally:
        try:
            await browser.close()
        except:
            pass

@app.route('/download', methods=['GET'])
async def download_website():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing URL parameter."}), 400

    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    if 'localhost' in url or is_private_address(url):
        return jsonify({"error": "You can't download from local or private addresses."}), 403

    async with aiohttp.ClientSession() as session:
        final_url = await resolve_redirects(session, url)
        if final_url is None:
            return jsonify({"error": "You can't download from local or private addresses."}), 403
        elif final_url == "error":
            return jsonify({"error": "Too many redirects, unable to get this one."}), 400

    if is_private_address(final_url):
        return jsonify({"error": "You can't download from local or private addresses."}), 403

    if 'localhost' in final_url:
        return jsonify({"error": "You can't download from local or private addresses."}), 403

    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    download_dir = os.path.join("temp/website", domain)
    os.makedirs(download_dir, exist_ok=True)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                if int(response.headers.get('Content-Length', 0)) > 50 * 1024 * 1024:
                    return jsonify({"error": "Website size is above 50MB, can't process."}), 400

                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')

                resources_to_process = set()
                index_paths = []

                for tag in soup.find_all(['link', 'script', 'img', 'audio', 'source']):
                    src = tag.get('href') or tag.get('src')
                    if src:
                        full_url = urljoin(url, src)
                        resources_to_process.add(full_url)

                for resource_url in resources_to_process:
                    parsed_resource = urlparse(resource_url)
                    resource_path = os.path.join(download_dir, parsed_resource.path.lstrip('/'))
                    downloaded_path = await process_resource(session, resource_url, resource_path)

                    if downloaded_path:
                        relative_path = os.path.relpath(downloaded_path, download_dir)
                        for tag in soup.find_all(['link', 'script', 'img', 'audio', 'source']):
                            if tag.get('href') == resource_url:
                                tag['href'] = relative_path
                            elif tag.get('src') == resource_url:
                                tag['src'] = relative_path
                            if os.path.basename(downloaded_path) == "index.html":
                                index_paths.append(resource_path)

                index_path = os.path.join(download_dir, "index.html")
                async with aiofiles.open(index_path, 'w', encoding='utf-8') as f:
                    await f.write(str(soup))

                zip_filename = f"{domain}.zip"
                zip_path = os.path.join("temp/website", zip_filename)
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(download_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(download_dir))
                            zipf.write(file_path, arcname=arcname)

                return send_from_directory(os.path.dirname(zip_path), zip_filename, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
    finally:
        if os.path.exists(os.path.dirname(download_dir)):
            shutil.rmtree(os.path.dirname(download_dir))

if __name__ == '__main__':
    async def create_app():
        return app

    run_simple('0.0.0.0', 5008, DispatcherMiddleware(app), use_reloader=True)