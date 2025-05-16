import asyncio
import hashlib
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from playwright.async_api import async_playwright
from aiocache import cached
from aiocache.serializers import JsonSerializer

app = FastAPI()

def generate_cache_key(image_data: bytes) -> str:
    return hashlib.md5(image_data).hexdigest()

@cached(ttl=3600, serializer=JsonSerializer())
async def scrape_picarta(image_path: str, cache_key: str):
    retries = 2
    for attempt in range(retries):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                print("Navigating to Picarta.ai...")
                await page.goto('https://picarta.ai', timeout=60000)
                print("Clicking upload button...")
                await page.click('#upload-btn')
                print(f"Setting input file to {image_path}...")
                await page.set_input_files('input[type="file"]', image_path)
                print("Waiting for classify button...")
                await page.wait_for_selector('#find-location-globally-button span.common-btn.classify-btn', state='visible')
                print("Clicking classify button...")
                await page.click('#find-location-globally-button span.common-btn.classify-btn')

                print("Waiting for predictions...")
                try:
                    await page.wait_for_function(
                        '''() => {
                            const predictions = document.querySelector("#predictions");
                            return predictions && predictions.textContent.includes("%");
                        }''',
                        timeout=35000,
                        polling=500
                    )
                except Exception as e:
                    print(f"Timeout while waiting for predictions: {e}")
                    if attempt < retries - 1:
                        print(f"Retrying attempt {attempt + 2}...")
                        await browser.close()
                        continue
                    else:
                        await browser.close()
                        return {"error": "Failed to extract predictions after retries"}

                print("Extracting predictions text...")
                predictions_text = await page.evaluate('() => document.querySelector("#predictions").textContent')
                print(f"Predictions text: {predictions_text}")

                if 'GPS location around:' in predictions_text:
                    location = predictions_text.split('GPS location around:')[0].strip()
                    location = location.rstrip('.')
                    if location.strip()[0].isdigit() and '. ' in location:
                        location = location.split('. ', 1)[1]
                else:
                    location = predictions_text.split('Confidence:')[0].strip().rstrip('.')
                    if location.strip()[0].isdigit() and '. ' in location:
                        location = location.split('. ', 1)[1]

                confidence = predictions_text.split('Confidence: ')[1].split('%')[0] + '%'
                result = {
                    "result": location,
                    "confidence": confidence
                }
                print(f"Result: {result}")
                await browser.close()
                return result

        except Exception as e:
            print(f"Error in scrape_picarta (attempt {attempt + 1}): {e}")
            if attempt == retries - 1:
                return {"error": str(e)}
            await asyncio.sleep(5)

@app.post("/locate")
async def scrape(file: UploadFile = File(...)):
    try:
        print("Received file upload request.")
        image_data = await file.read()

        temp_path = "temp_image.png"
        with open(temp_path, "wb") as f:
            f.write(image_data)
        print("File saved as temp_image.png.")

        cache_key = generate_cache_key(image_data)

        try:
            result = await scrape_picarta(temp_path, cache_key)
            print(f"Scraping result: {result}")

            if os.path.exists(temp_path):
                os.remove(temp_path)

            return result
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        print(f"Error in scrape endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8889)
