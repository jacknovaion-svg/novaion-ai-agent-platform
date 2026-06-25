from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from app.hardware_daily.models import HardwareResultPageType


@dataclass(frozen=True)
class HardwarePageClassification:
    page_type: HardwareResultPageType
    reason: str


class HardwareResultQualityClassifier:
    def classify(self, source_name: str, url: str, title: str, description: str | None) -> HardwarePageClassification:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        text = f"{title} {description or ''}".lower()

        if self._is_irrelevant(domain, text):
            return HardwarePageClassification(HardwareResultPageType.IRRELEVANT, "Blocked domain or unrelated result.")
        if self._is_news(path, text):
            return HardwarePageClassification(HardwareResultPageType.NEWS_OR_ARTICLE, "News, article, or content page.")
        if self._is_specific_listing(domain, path, query, text):
            return HardwarePageClassification(HardwareResultPageType.SPECIFIC_LISTING, "URL/title matches specific lot or item pattern.")
        if self._is_listing_collection(path, query, text):
            return HardwarePageClassification(HardwareResultPageType.LISTING_COLLECTION, "Search/category/results page.")
        if self._is_source_page(path, text):
            return HardwarePageClassification(HardwareResultPageType.SOURCE_PAGE, "Company, service, or source landing page.")
        if self._has_specific_lot_language(text) and source_name in {"GovDeals", "Public Surplus", "eBay", "HGP Industrial Auctions"}:
            return HardwarePageClassification(HardwareResultPageType.SPECIFIC_LISTING, "Marketplace title looks like a specific lot.")
        return HardwarePageClassification(HardwareResultPageType.IRRELEVANT, "No specific lot/listing evidence.")

    def _is_specific_listing(self, domain: str, path: str, query: dict[str, list[str]], text: str) -> bool:
        if "govdeals.com" in domain and re.search(r"/(?:en/)?asset/\d+", path):
            return True
        if "ebay.com" in domain and ("/itm/" in path or re.search(r"/\d{10,}$", path)):
            return True
        if "publicsurplus.com" in domain and (query.get("auc") or query.get("auction") or "viewauction" in path or "view" in path):
            return True
        if "hgpauction.com" in domain and any(token in path for token in ["/lot/", "/lots/", "/item/", "/auction/"]) and self._has_specific_lot_language(text):
            return True
        return self._has_specific_lot_language(text) and any(token in path for token in ["/lot", "/item", "/asset", "/listing", "/auction"])

    def _is_listing_collection(self, path: str, query: dict[str, list[str]], text: str) -> bool:
        collection_tokens = ["search", "category", "catalog", "results", "inventory", "auctions", "marketplace", "browse"]
        if any(token in path for token in collection_tokens):
            return True
        if query.get("q") or query.get("keyword") or query.get("search"):
            return True
        return any(token in text for token in ["search results", "all auctions", "current auctions", "browse", "category"])

    def _is_source_page(self, path: str, text: str) -> bool:
        source_tokens = ["services", "about", "contact", "liquidator", "liquidation services", "asset recovery", "server liquidation"]
        if any(token in path for token in ["/services", "/about", "/contact", "/company"]):
            return True
        return any(token in text for token in source_tokens) and not self._has_specific_lot_language(text)

    def _is_news(self, path: str, text: str) -> bool:
        if any(token in path for token in ["/news", "/blog", "/article", "/press", "/story"]):
            return True
        return any(token in text for token in ["news", "press release", "article", "blog"])

    def _is_irrelevant(self, domain: str, text: str) -> bool:
        blocked_domains = ["reddit.com", "youtube.com", "facebook.com", "wikipedia.org", "indeed.com", "manualslib.com"]
        if any(domain.endswith(blocked) for blocked in blocked_domains):
            return True
        blocked_text = ["driver download", "firmware", "manual", "repair guide", "job opening", "salary"]
        return any(token in text for token in blocked_text)

    def _has_specific_lot_language(self, text: str) -> bool:
        patterns = [
            r"\blot\s+(?:of\s+)?\d+",
            r"\blot\s*#?\s*\d+",
            r"\basset\s*#?\s*\d+",
            r"\bitem\s*#?\s*\d+",
            r"\b\d+\s*x\s+",
            r"\bqty\.?\s*\d+",
            r"\bauction\s+ends?\b",
            r"\bcurrent bid\b",
            r"\bbuy it now\b",
        ]
        return any(re.search(pattern, text, flags=re.I) for pattern in patterns)
