import asyncio
from playwright.async_api import async_playwright
import sys

# Ensure policy is set here for isolation test
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def main():
    print("Starting Playwright...")
    async with async_playwright() as p:
        print("Launching Browser...")
        browser = await p.chromium.launch(headless=True)
        print("Browser Launched!")
        page = await browser.new_page()
        await page.goto("http://example.com")
        print(await page.title())
        await browser.close()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
