import io
import time
import asyncio
import tempfile

from PIL import Image
from playwright.async_api import async_playwright

async def match_description_to_sports_score_url(match_description):
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Navigate to the URL
        url = f"https://www.google.com/search?q={match_description}"
        await page.goto(url)
        try:
            # Wait for the element to be present
            sports_div = await page.wait_for_selector('#sports-app', timeout=2000)
            
            # Get the content
            content = await sports_div.inner_text()
            await sports_div.click()
            await asyncio.sleep(2)  # Added delay to observe the click result
            current_url = page.url
            return current_url
                
        except Exception as e:
            print(f"Error finding sports app for {match_description}: {str(e)}")
            return None

import tempfile

async def get_score_image(url):
    """
    Get score div from Google app sports page
    
    Args:
        url (str): Google sports app url
    """
    async with async_playwright() as p:
        # Launch browser
        print(f"Getting score image for {url}")
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        print(f"Navigating to {url}")
        # Navigate to the URL
        await page.goto(url)
        await asyncio.sleep(2)  # Added delay to observe the click result
        
        print("Waiting for score div")
        # Get the specific div
        div = page.locator('div.imso_mh__tm-scr.imso_mh__mh-bd').first

        final_score_locators = page.locator('div[aria-label="Final score"]')
        is_final_score = bool(await final_score_locators.count())
        
        print("Taking screenshot")
        # Capture the div as bytes
        try:    
            screenshot_bytes = await div.screenshot(timeout=3000)
        except Exception as e:
            print(f"Error taking screenshot: {str(e)}")
            await page.screenshot(path="current_page.png")
            return None, False
        
        print("Saving to temp file")
        # Convert bytes to PIL Image and save to a temporary file
        image = Image.open(io.BytesIO(screenshot_bytes))
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            image.save(temp_file, format='PNG')
            temp_file_path = temp_file.name
        
        await browser.close()

        print(f"Returning {temp_file_path}")
        return temp_file_path, is_final_score

if __name__ == "__main__":
    # Run the async function
    async def main():
        url = "https://www.google.com/search?q=jazz%20vs%20clippers#sie=m;/g/11lmmfkqqv;3;/m/05jvx;dt;fp;1;;;"
        print(await get_score_image(url))
        # x = await match_description_to_sports_score_url("jazz vs clippers")
        # print(x)

    # Run the async main function
    asyncio.run(main())
