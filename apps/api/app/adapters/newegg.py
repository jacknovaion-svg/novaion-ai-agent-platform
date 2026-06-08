from __future__ import annotations

from bs4 import BeautifulSoup

from app.adapters.base import SearchAdapter
from app.adapters.browser import chromium_browser
from app.adapters.utils import infer_brand_and_model, parse_price, utc_now
from app.core.config import get_settings
from app.models.schemas import NormalizedResult, SearchOptions


class NeweggAdapter(SearchAdapter):
    source_key = "newegg"
    source_name = "Newegg"

    async def search(self, query: str, options: SearchOptions) -> dict:
        settings = get_settings()
        if not settings.enable_live_scraping:
            return {"query": query, "html": "", "live_disabled": True}

        url = f"https://www.newegg.com/p/pl?d={query.replace(' ', '+')}"
        async with chromium_browser() as browser:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(2500)
            html = await page.content()
            await page.close()
        return {"query": query, "url": url, "html": html, "fallback": False}

    def parse_results(self, raw_data: dict) -> list[dict]:
        if raw_data.get("live_disabled"):
            return []

        soup = BeautifulSoup(raw_data["html"], "html.parser")
        items = []
        for card in soup.select(".item-cell")[:8]:
            title_node = card.select_one(".item-title")
            price_current = card.select_one(".price-current")
            text = card.get_text(" ", strip=True)
            title = title_node.get_text(" ", strip=True) if title_node else ""
            if not title:
                continue
            items.append(
                {
                    "title": title,
                    "price": price_current.get_text(" ", strip=True) if price_current else None,
                    "inventory": "Available" if "add to cart" in text.lower() else "Check Site",
                    "promotion": "Free shipping" if "free shipping" in text.lower() else "",
                    "url": title_node.get("href") if title_node else "",
                    "store": "Newegg",
                    "shipping": True,
                    "pickup": False,
                }
            )
        return items

    def normalize_result(self, parsed_data: dict) -> NormalizedResult:
        brand, model = infer_brand_and_model(parsed_data["title"], parsed_data["title"])
        return NormalizedResult(
            source=self.source_name,
            product_name=parsed_data["title"],
            brand=brand,
            model=model,
            store_name=parsed_data.get("store"),
            address=None,
            distance=None,
            price=parse_price(parsed_data.get("price")),
            promotion=parsed_data.get("promotion") or None,
            inventory_status=parsed_data.get("inventory"),
            pickup_available=bool(parsed_data.get("pickup")),
            shipping_available=bool(parsed_data.get("shipping")),
            product_url=parsed_data.get("url"),
            updated_at=utc_now(),
        )
