import asyncio
from playwright.async_api import async_playwright

async def t():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page()
        await page.goto("https://www.skillbox.co/events?city=hyderabad")
        await page.wait_for_timeout(5000)
        c = await page.content()
        with open("sb_content.html", "w", encoding="utf-8") as f:
            f.write(c)
        await b.close()

if __name__ == "__main__":
    asyncio.run(t())
