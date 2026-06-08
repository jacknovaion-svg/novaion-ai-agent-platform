from __future__ import annotations

from bs4 import BeautifulSoup

from app.adapters.base import SearchAdapter
from app.adapters.browser import chromium_browser
from app.adapters.utils import infer_brand_and_model, parse_price, utc_now
from app.core.config import get_settings
from app.models.enums import SearchMode
from app.models.schemas import NormalizedResult, SearchOptions


class BestBuyAdapter(SearchAdapter):
    source_key = "best_buy"
    source_name = "Best Buy"

    async def search(self, query: str, options: SearchOptions) -> dict:
        settings = get_settings()
        if not settings.enable_live_scraping:
            return {"query": query, "html": "", "live_disabled": True}
        if options.mode == SearchMode.LOCAL:
            return {"query": query, "html": "", "mode_unsupported": True}

        url = f"https://www.bestbuy.com/site/searchpage.jsp?st={query.replace(' ', '+')}"
        async with chromium_browser() as browser:
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(2500)
                html = await page.content()
            finally:
                await page.close()
        return {"query": query, "url": url, "html": html, "fallback": False}

    def parse_results(self, raw_data: dict) -> list[dict]:
        if raw_data.get("live_disabled") or raw_data.get("mode_unsupported"):
            return []

        soup = BeautifulSoup(raw_data["html"], "html.parser")
        items = []
        cards = soup.select(
            ".sku-item, .shop-sku-list-item, .product-flexbox, .list-item.wrapper, [data-testid='shop-sku-list-item']"
        )
        seen_urls: set[str] = set()
        for card in cards:
            title_node = card.select_one("a.sku-title, .sku-title a, h4 a, .nc-product-title")
            if title_node and title_node.name != "a":
                title_node = title_node.find_parent("a")
            price_node = card.select_one(
                ".priceView-customer-price span, .pricing-price__regular-price, [data-testid='customer-price'], .sr-only"
            )
            availability_text = card.get_text(" ", strip=True)
            title = title_node.get_text(" ", strip=True) if title_node else ""
            if not title:
                continue
            href = title_node.get("href", "") if title_node else ""
            url = f"https://www.bestbuy.com{href}" if href.startswith("/") else href
            if url in seen_urls:
                continue
            seen_urls.add(url)
            price_text = price_node.get_text(" ", strip=True) if price_node else availability_text
            items.append(
                {
                    "title": title,
                    "price": price_text,
                    "inventory": self._inventory_status(availability_text),
                    "promotion": "Sale" if "save" in availability_text.lower() else "",
                    "url": url,
                    "store": "Best Buy",
                    "shipping": "shipping" in availability_text.lower(),
                    "pickup": "pickup" in availability_text.lower(),
                }
            )
            if len(items) >= 8:
                break
        return items

    def _inventory_status(self, text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ["add to cart", "available", "in stock"]):
            return "Available"
        if any(token in lowered for token in ["sold out", "unavailable"]):
            return "Out of Stock"
        return "Check Site"

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
            pickup_available=bool(parsed_data.get("pickup")) and parsed_data.get("distance") is not None,
            shipping_available=bool(parsed_data.get("shipping")),
            product_url=parsed_data.get("url"),
            updated_at=utc_now(),
        )
