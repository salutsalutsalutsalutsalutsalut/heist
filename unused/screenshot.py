import os
import time
import traceback
import asyncio
from flask import Flask, request, jsonify
from playwright.async_api import async_playwright
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

app = Flask(__name__)

def is_nsfw(url: str) -> bool:
    nsfw_keywords = ["adult", "porn", "nsfw", "xxx", "sex", "nudity", "cp", "young teen"]
    return any(keyword in url.lower() for keyword in nsfw_keywords)

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

    return jsonify(result)

if __name__ == '__main__':
    async def create_app():
        return app

    run_simple('localhost', 5008, DispatcherMiddleware(app), use_reloader=True)