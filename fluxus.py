from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from aiohttp import ClientSession
import re
import time

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'DNT': '1',
    'Connection': 'close',
    'Referer': 'https://linkvertise.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x66) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
}

key_regex = r'let content = \("([^"]+)"\);'

async def fetch(session, url, referer):
    headers["Referer"] = referer
    async with session.get(url, headers=headers) as response:
        content = await response.text()
        if response.status != 200:
            return None, response.status, content
        return content, response.status, None

async def process_link(hwid):
    endpoints = [
        {
            "url": f"https://flux.li/android/external/start.php?HWID={hwid}",
            "referer": "https://linkvertise.com"
            },
        {
            "url": "https://flux.li/android/external/check1.php?hash={hash}",
            "referer": "https://linkvertise.com"
            },
        {
            "url": "https://flux.li/android/external/main.php?hash={hash}",
            "referer": "https://linkvertise.com"
        }
    ]
    
    async with ClientSession() as session:
        for i, endpoint in enumerate(endpoints):
            url = endpoint["url"]
            referer = endpoint["referer"]
            content, status, error_content = await fetch(session, url, referer)
            if error_content:
                return {
                    "status": "error",
                    "message": f"Failed to bypass at step {i} | Status code: {status}",
                    "content": error_content
                }

            if i == len(endpoints) - 1:
                match = re.search(key_regex, content)
                if match:
                    return {
                        "status": "success",
                        "key": match.group(1)
                    }
                else:
                    return {
                        "status": "error",
                        "message": "Bypass not successful! No key found.",
                        "content": content
                    }

@app.get("/api/fluxus")
async def handle_request(request: Request):
    start_time = time.time()
    link = request.query_params.get('link')
    if not link:
        raise HTTPException(status_code=400, detail="No link provided")

    hwid = link.split("HWID=")[-1]
    result = await process_link(hwid)
    end_time = time.time()
    execution_time = end_time - start_time
    result['execution_time'] = execution_time
    return JSONResponse(content=result)

@app.get("/")
async def root():
    return "<h1>Hi! You.</h1>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=1117)

