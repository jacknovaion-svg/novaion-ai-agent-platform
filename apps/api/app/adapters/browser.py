from contextlib import asynccontextmanager
from typing import AsyncIterator

from playwright.async_api import Browser, async_playwright

from app.core.config import get_settings


@asynccontextmanager
async def chromium_browser() -> AsyncIterator[Browser]:
    settings = get_settings()
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=settings.playwright_headless,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions",
        ],
    )
    try:
        yield browser
    finally:
        await browser.close()
        await playwright.stop()
