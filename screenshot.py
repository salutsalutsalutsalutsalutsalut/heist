from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from playwright.async_api import async_playwright
import asyncio
import io

app = FastAPI()
_browser = None

async def get_browser():
    global _browser
    if not _browser:
        _browser = await async_playwright().start()
        _browser = await _browser.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--disable-setuid-sandbox',
                '--disable-extensions',
                '--disable-audio-output',
                '--disable-background-networking',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-breakpad',
                '--disable-client-side-phishing-detection',
                '--disable-default-apps',
                '--disable-features=site-per-process',
                '--disable-hang-monitor',
                '--disable-ipc-flooding-protection',
                '--disable-prompt-on-repost',
                '--disable-renderer-backgrounding',
                '--disable-sync',
                '--disable-translate',
                '--metrics-recording-only',
                '--no-first-run',
                '--safebrowsing-disable-auto-update'
            ]
        )
    return _browser

@app.get("/screenshot")
async def take_screenshot(url: str = Query(...), delay: int = Query(0)):
    if delay > 15:
        raise HTTPException(status_code=400, detail="Delay cannot be more than 15 seconds.")

    browser = await get_browser()
    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        java_script_enabled=True,
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    )
    
    page = await context.new_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=10000)
    await asyncio.sleep(delay)
    
    screenshot_bytes = await page.screenshot(type="png", full_page=True)
    await context.close()

    return StreamingResponse(io.BytesIO(screenshot_bytes), media_type="image/png")

@app.on_event("shutdown")
async def shutdown_browser():
    global _browser
    if _browser:
        await _browser.close()
        _browser = None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5008)