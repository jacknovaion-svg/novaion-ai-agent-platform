from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import re
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.adapters.browser import chromium_browser
from app.hardware_daily.models import HardwareResultPageType, HardwareScanRequest, RawHardwareListing, utc_now
from app.hardware_daily.quality import HardwareResultQualityClassifier
from app.site_hunter.web_search import WebSearchClient

logger = logging.getLogger(__name__)


@dataclass
class HardwareSearchHit:
    title: str
    url: str
    snippet: str | None = None
    domain: str | None = None


class HardwareSourceAdapter(ABC):
    source_name: str
    adapter_type: str

    @abstractmethod
    async def search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        raise NotImplementedError


class WebSearchHardwareAdapter(HardwareSourceAdapter):
    source_name = "Public Hardware Web Search"
    adapter_type = "web_search_hardware"

    def __init__(self) -> None:
        self.web_search = WebSearchClient()
        self.quality = HardwareResultQualityClassifier()

    async def search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        if query.source_group == "GovAuctions.app":
            return await self._govauctions_app_search(query, request)
        if query.source_group == "GovDeals":
            return await self._govdeals_search(query, request)
        if query.source_group == "GSA Auctions":
            direct_results = await self._gsa_auctions_search(query, request)
            if direct_results:
                return direct_results
        if query.source_group == "Public Surplus":
            direct_results = await self._public_surplus_search(query, request)
            if direct_results:
                return direct_results
        if query.source_group == "Municibid":
            direct_results = await self._municibid_search(query, request)
            if direct_results:
                return direct_results
        try:
            hits = await self.web_search.search(query.generated_query_en, max_results=request.max_results_per_query)
        except Exception:
            hits = await self._bing_search(query.generated_query_en, max_results=request.max_results_per_query)
        listings: list[RawHardwareListing] = []
        for hit in hits:
            if not self._is_relevant(hit.title, hit.snippet, hit.domain):
                continue
            if not self._is_category_relevant(query.category.value, hit.title, hit.snippet):
                continue
            classification = self.quality.classify(query.source_group or self.source_name, hit.url, hit.title, hit.snippet)
            listings.append(
                RawHardwareListing(
                    source_name=query.source_group or self.source_name,
                    source_url=hit.url,
                    original_title=hit.title,
                    original_description=hit.snippet,
                    category=query.category,
                    page_type=classification.page_type,
                    classification_reason=classification.reason,
                    raw_data={
                        "query": query.generated_query_en,
                        "domain": hit.domain,
                        "adapter_type": self.adapter_type,
                        "public_search_discovery": True,
                        "page_type": classification.page_type.value,
                        "classification_reason": classification.reason,
                    },
                    fetched_at=utc_now(),
                )
            )
        return listings

    async def _govdeals_search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        keyword = self._marketplace_keyword(query)
        direct_status = await self._govdeals_direct_probe(keyword)
        try:
            hits = await self.web_search.search(query.generated_query_en, max_results=request.max_results_per_query)
        except Exception:
            hits = await self._bing_search(query.generated_query_en, max_results=request.max_results_per_query)

        listings: list[RawHardwareListing] = []
        for hit in hits:
            if "govdeals.com" not in (hit.domain or "").lower() and "govdeals.com" not in hit.url.lower():
                continue
            if not self._is_relevant(hit.title, hit.snippet, hit.domain):
                continue
            if not self._is_category_relevant(query.category.value, hit.title, hit.snippet):
                continue
            classification = self.quality.classify("GovDeals", hit.url, hit.title, hit.snippet)
            listings.append(
                RawHardwareListing(
                    source_name="GovDeals",
                    source_url=hit.url,
                    original_title=hit.title,
                    original_description=hit.snippet,
                    category=query.category,
                    page_type=classification.page_type,
                    classification_reason=classification.reason,
                    raw_data={
                        "query": query.generated_query_en,
                        "domain": hit.domain,
                        "adapter_type": "govdeals_web_discovery_fallback",
                        "source_type": "auction_restricted_web_discovery",
                        "source_access_mode": "web_discovery_fallback",
                        "source_access_status": direct_status,
                        "source_access_note": (
                            "GovDeals direct search is restricted for backend HTTP in this environment; "
                            "public search discovery is used and Manual Import can ingest known GovDeals listing URLs."
                        ),
                        "public_search_discovery": True,
                        "page_type": classification.page_type.value,
                        "classification_reason": classification.reason,
                    },
                    fetched_at=utc_now(),
                )
            )
            if len(listings) >= request.max_results_per_query:
                break
        return listings

    async def _govdeals_direct_probe(self, keyword: str) -> str:
        urls = [
            f"https://www.govdeals.com/search?query={quote_plus(keyword)}",
            f"https://www.govdeals.com/en/search?query={quote_plus(keyword)}",
            f"https://www.govdeals.com/en/auctions?search={quote_plus(keyword)}",
        ]
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (compatible; NOVAIONHardwareHunter/2.7B; +https://novaion.ai)",
        }
        async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers=headers) as client:
            for url in urls:
                try:
                    response = await client.get(url)
                except httpx.TimeoutException:
                    return "direct_search_timeout"
                except Exception as exc:
                    return f"direct_search_error:{str(exc)[:80]}"
                body_sample = response.text[:1000].lower()
                if response.status_code in {401, 403} or "access denied" in body_sample:
                    return f"direct_search_restricted:{response.status_code}"
                if response.status_code < 400:
                    return "direct_search_accessible"
                if response.status_code >= 500:
                    return f"direct_search_server_error:{response.status_code}"
        return "direct_search_unavailable"

    async def _gsa_auctions_search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        keyword = self._marketplace_keyword(query)
        api_status, api_results = await self._gsa_public_api_search(query, request, keyword)
        if api_results:
            return api_results

        try:
            hits = await self.web_search.search(query.generated_query_en, max_results=request.max_results_per_query)
        except Exception:
            hits = await self._bing_search(query.generated_query_en, max_results=request.max_results_per_query)

        listings: list[RawHardwareListing] = []
        for hit in hits:
            if "gsaauctions.gov" not in (hit.domain or "").lower() and "gsaauctions.gov" not in hit.url.lower():
                continue
            if not self._is_relevant(hit.title, hit.snippet, hit.domain):
                continue
            if not self._is_category_relevant(query.category.value, hit.title, hit.snippet):
                continue
            classification = self.quality.classify("GSA Auctions", hit.url, hit.title, hit.snippet)
            listings.append(
                RawHardwareListing(
                    source_name="GSA Auctions",
                    source_url=hit.url,
                    original_title=hit.title,
                    original_description=hit.snippet,
                    category=query.category,
                    page_type=classification.page_type,
                    classification_reason=classification.reason,
                    raw_data={
                        "query": query.generated_query_en,
                        "domain": hit.domain,
                        "adapter_type": "gsa_auctions_public_search_fallback",
                        "source_type": "auction_public_json_or_search",
                        "gsa_api_status": api_status,
                        "public_search_discovery": True,
                        "page_type": classification.page_type.value,
                        "classification_reason": classification.reason,
                    },
                    fetched_at=utc_now(),
                )
            )
            if len(listings) >= request.max_results_per_query:
                break
        if not listings and api_status.startswith(("unauthorized", "http_error", "server_error", "error")):
            raise RuntimeError(f"GSA public JSON endpoint unavailable ({api_status}); public search fallback returned 0 results.")
        return listings

    async def _gsa_public_api_search(self, query, request: HardwareScanRequest, keyword: str) -> tuple[str, list[RawHardwareListing]]:
        base = "https://www.ppms.gov/gw/auction/ppms"
        state = query.state_code or ""
        endpoints = [
            f"{base}/api/v1/sales?searchText={quote_plus(keyword)}&state={quote_plus(state)}&page=0&size={request.max_results_per_query}",
            f"{base}/api/v1/sales?keyword={quote_plus(keyword)}&state={quote_plus(state)}&page=0&size={request.max_results_per_query}",
            f"{base}/api/v1/sales?page=0&size={request.max_results_per_query}",
        ]
        headers = {
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://gsaauctions.gov/",
            "User-Agent": "Mozilla/5.0 (compatible; NOVAIONHardwareHunter/2.6B; +https://novaion.ai)",
        }
        last_status = "not_attempted"
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            for endpoint in endpoints:
                try:
                    response = await client.get(endpoint)
                except httpx.TimeoutException:
                    last_status = "timeout"
                    continue
                except Exception as exc:
                    last_status = f"error:{str(exc)[:120]}"
                    continue
                if response.status_code in {401, 403}:
                    last_status = f"unauthorized:{response.status_code}"
                    continue
                if response.status_code >= 500:
                    last_status = f"server_error:{response.status_code}"
                    continue
                if response.status_code >= 400:
                    last_status = f"http_error:{response.status_code}"
                    continue
                try:
                    payload = response.json()
                except ValueError:
                    last_status = "non_json_response"
                    continue
                records = self._gsa_extract_records(payload)
                listings = [item for record in records if (item := self._gsa_record_to_listing(record, query, endpoint))]
                return "public_json_ok", listings[: request.max_results_per_query]
        return last_status, []

    def _gsa_extract_records(self, payload) -> list[dict]:
        records: list[dict] = []

        def walk(value) -> None:
            if isinstance(value, dict):
                keys = {str(key).lower() for key in value.keys()}
                if keys & {"salenumber", "sale_no", "lotnumber", "lot_no", "itemcontrolnumber", "itemname", "bidamount", "enddate"}:
                    records.append(value)
                    return
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(payload)
        return records

    def _gsa_record_to_listing(self, record: dict, query, endpoint: str) -> RawHardwareListing | None:
        title = self._first_value(record, ["itemName", "title", "description", "saleTitle", "assetName", "lotTitle"])
        description = self._first_value(record, ["itemDescription", "description", "longDescription", "saleDescription", "propertyDescription"])
        if not title:
            return None
        text = f"{title} {description or ''}"
        if not self._is_category_relevant(query.category.value, title, description):
            return None
        sale_no = self._first_value(record, ["saleNumber", "saleNo", "sale_no"])
        lot_no = self._first_value(record, ["lotNumber", "lotNo", "lot_no"])
        listing_id = self._first_value(record, ["itemControlNumber", "icn", "id", "saleLotId"]) or "-".join(part for part in [sale_no, lot_no] if part)
        source_url = self._gsa_source_url(sale_no, lot_no, listing_id)
        classification = self.quality.classify("GSA Auctions", source_url, title, description)
        location_state = self._first_value(record, ["state", "locationState", "stateCode", "propertyState"])
        location_city = self._first_value(record, ["city", "locationCity", "propertyCity"])
        end_time = self._first_value(record, ["endDate", "auctionEndDate", "auction_end_date", "closeDate", "closingDate"])
        current_bid = self._first_value(record, ["bidAmount", "currentBid", "current_bid", "highBid"])
        detail = {
            "source_listing_id": listing_id,
            "sale_no": sale_no,
            "lot_number": lot_no,
            "title": title,
            "description": description,
            "current_price": self._money_float(current_bid),
            "total_price": self._money_float(current_bid),
            "auction_end_time": self._parse_gsa_datetime(end_time),
            "end_time_utc": self._parse_gsa_datetime(end_time),
            "end_time_raw": str(end_time) if end_time else None,
            "end_time_verification": "source_confirmed" if end_time else "unknown",
            "location_city": location_city,
            "location_state": location_state,
            "seller_name": self._first_value(record, ["agency", "agencyName", "seller", "region"]) or "GSA Auctions",
            "listing_status": self._gsa_listing_status(record, end_time),
            "listing_status_reason": "GSA Auctions public JSON endpoint parsed" if endpoint else "GSA Auctions public search discovery",
        }
        return RawHardwareListing(
            source_name="GSA Auctions",
            source_url=source_url,
            original_title=title,
            original_description=description,
            category=query.category,
            source_listing_id=listing_id,
            seller_name=detail["seller_name"],
            page_type=HardwareResultPageType.SPECIFIC_LISTING,
            classification_reason=f"GSA public JSON record mapped as a specific listing. {classification.reason}",
            raw_data={
                "query": query.generated_query_en,
                "domain": "gsaauctions.gov",
                "adapter_type": "gsa_auctions_public_json",
                "source_type": "auction_public_json_or_search",
                "api_endpoint": endpoint,
                "sale_no": sale_no,
                "lot_no": lot_no,
                "raw_payload": record,
                "detail": detail,
                "page_type": classification.page_type.value,
                "classification_reason": classification.reason,
            },
            fetched_at=utc_now(),
        )

    def _gsa_source_url(self, sale_no: str | None, lot_no: str | None, listing_id: str | None) -> str:
        query_parts = [part for part in [sale_no, lot_no, listing_id] if part]
        if query_parts:
            return f"https://gsaauctions.gov/auctions/auctions-list?search={quote_plus(' '.join(query_parts))}"
        return "https://gsaauctions.gov/auctions/auctions-list"

    def _first_value(self, payload: dict, keys: list[str]) -> str | None:
        lower_lookup = {str(key).lower(): value for key, value in payload.items()}
        for key in keys:
            value = lower_lookup.get(key.lower())
            if value is None or value == "":
                continue
            return str(value).strip()
        return None

    def _money_float(self, value: str | None) -> float | None:
        if not value:
            return None
        try:
            return float(str(value).replace("$", "").replace(",", "").strip())
        except ValueError:
            return None

    def _extract_price(self, text: str | None) -> float | None:
        if not text:
            return None
        match = re.search(r"\$\s?([0-9][0-9,]*(?:\.\d{2})?)", text)
        if not match:
            return None
        return self._money_float(match.group(1))

    def _parse_gsa_datetime(self, value: str | None) -> str | None:
        if not value:
            return None
        raw = str(value).strip()
        for candidate in [raw, raw.replace("Z", "+00:00")]:
            try:
                parsed = datetime.fromisoformat(candidate)
                if not parsed.tzinfo:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.isoformat()
            except ValueError:
                continue
        return None

    def _gsa_listing_status(self, record: dict, end_time: str | None) -> str:
        raw_status = (self._first_value(record, ["status", "saleStatus", "auctionStatus"]) or "").lower()
        if any(token in raw_status for token in ["closed", "ended", "sold", "removed"]):
            if "sold" in raw_status:
                return "sold"
            if "removed" in raw_status:
                return "removed"
            return "ended"
        parsed = self._parse_gsa_datetime(end_time)
        if parsed:
            end_dt = datetime.fromisoformat(parsed)
            now = utc_now()
            if end_dt <= now:
                return "ended"
            if end_dt - now <= timedelta(hours=24):
                return "ending_soon"
            return "active"
        return "unknown"

    async def _govauctions_app_search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        keyword = self._marketplace_keyword(query)
        feed_url = f"https://govauctions.app/feed?q={quote_plus(keyword)}&sort=relevance"
        max_pages, max_results = self._govauctions_paging_limits()
        html, page_meta = await self._govauctions_rendered_html(feed_url, keyword, max_pages=max_pages, max_results=max_results)
        access_mode = "playwright_interactive_search" if html else "direct_html_fallback"
        response_status: int | str | None = None
        if not html:
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "User-Agent": "Mozilla/5.0 (compatible; NOVAIONHardwareHunter/2.8A; +https://novaion.ai)",
            }
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                response = await client.get(feed_url)
                response_status = response.status_code
                response.raise_for_status()
                html = response.text
                page_meta = {
                    "pages_scanned": 1,
                    "visible_cards": 0,
                    "stopped_reason": "direct_html_fallback",
                }

        soup = BeautifulSoup(html, "html.parser")
        listings: list[RawHardwareListing] = []
        seen_keys: set[str] = set()
        links = soup.select('a[href^="/auction/"], a[href*="govauctions.app/auction/"]')
        if not links:
            links = self._govauctions_links_from_next_chunks(html)
        parsed_titles: list[str] = []
        original_url_count = 0
        for link in links:
            href = link.get("href") if hasattr(link, "get") else str(link)
            if not href:
                continue
            govauctions_url = urljoin("https://govauctions.app", href)
            container_text = self._govauctions_card_text(link)
            parsed = self._parse_govauctions_card(govauctions_url, container_text, query.category, keyword)
            if not parsed:
                continue
            if not parsed["canonical_source_url"]:
                discovered_url = await self._govauctions_detail_original_url(govauctions_url)
                if discovered_url:
                    parsed["canonical_source_url"] = discovered_url
                    parsed["original_source_platform"] = parsed["original_source_platform"] or self._govauctions_platform_from_url(discovered_url)
                    parsed["source_listing_id"] = self._govauctions_source_listing_id_from_url(discovered_url) or parsed["source_listing_id"]
            title = parsed["title"]
            snippet = parsed["snippet"]
            if not self._is_category_relevant(query.category.value, title, snippet):
                continue
            fallback_key = "|".join(
                str(value or "").strip().lower()
                for value in [title, parsed["location_text"], parsed["calculated_end_time"] or parsed["time_remaining"]]
            )
            dedupe_keys = [govauctions_url, parsed["canonical_source_url"], fallback_key]
            if any(key and key in seen_keys for key in dedupe_keys):
                continue
            for key in dedupe_keys:
                if key:
                    seen_keys.add(key)
            original_source = parsed["original_source_platform"] or "GovAuctions.app"
            source_url = parsed["canonical_source_url"] or govauctions_url
            source_listing_id = parsed["source_listing_id"]
            detail = {
                "source_listing_id": source_listing_id,
                "title": title,
                "description": snippet,
                "current_price": parsed["current_price"],
                "total_price": parsed["current_price"],
                "location_city": parsed["location_city"],
                "location_state": parsed["location_state"],
                "location_text": parsed["location_text"],
                "time_remaining": parsed["time_remaining"],
                "countdown_raw_text": parsed["time_remaining"],
                "countdown_captured_at": utc_now().isoformat() if parsed["time_remaining"] else None,
                "calculated_end_time": parsed["calculated_end_time"],
                "calculated_timezone": "UTC" if parsed["calculated_end_time"] else None,
                "calculation_confidence": "aggregator_countdown_estimated" if parsed["calculated_end_time"] else None,
                "end_time_utc": parsed["calculated_end_time"],
                "end_time_raw": parsed["time_remaining"],
                "end_time_verification": "countdown_estimated" if parsed["calculated_end_time"] else "unknown",
                "listing_status": parsed["listing_status"],
                "listing_status_reason": "GovAuctions.app aggregator discovery; original source verification is still required.",
                "needs_manual_review": True,
                "unavailable_reason": "pending_original_source_verification",
                "canonical_source_url": parsed["canonical_source_url"],
                "original_source_url": parsed["canonical_source_url"],
                "original_source_platform": original_source,
                "discovery_source": "GovAuctions.app",
                "verification_status": "pending",
            }
            listings.append(
                RawHardwareListing(
                    source_name=original_source,
                    source_url=source_url,
                    original_title=title,
                    original_description=snippet,
                    category=query.category,
                    source_listing_id=source_listing_id,
                    page_type=HardwareResultPageType.SPECIFIC_LISTING,
                    classification_reason="GovAuctions.app aggregator card mapped as a candidate specific auction listing.",
                    raw_data={
                        "query": query.generated_query_en,
                        "domain": "govauctions.app",
                        "adapter_type": "govauctions_app_feed",
                        "source_type": "aggregator_meta_source",
                        "discovery_source": "GovAuctions.app",
                        "discovery_source_url": feed_url,
                        "govauctions_url": govauctions_url,
                        "original_source_platform": original_source,
                        "original_source_url": parsed["canonical_source_url"],
                        "canonical_source_url": parsed["canonical_source_url"],
                        "verification_status": "pending",
                        "last_verified_at": None,
                        "source_access_mode": "aggregator_discovery",
                        "source_access_status": access_mode,
                        "matched_keywords": [keyword],
                        "page_type": HardwareResultPageType.SPECIFIC_LISTING.value,
                        "classification_reason": "Aggregator result requires original source verification before Telegram.",
                        "detail": detail,
                    },
                    fetched_at=utc_now(),
                )
            )
            parsed_titles.append(title)
            if parsed["canonical_source_url"]:
                original_url_count += 1
            if len(listings) >= max_results:
                break
        verification_summary = {"pending": len(listings)}
        logger.info(
            "GovAuctions.app source requested_url=%s query=%s access_mode=%s response_status=%s pages_scanned=%s visible_cards=%s links_seen=%s unique_listings=%s extracted_result_count=%s first_titles=%s original_source_url_count=%s verification_status=%s stopped_reason=%s max_pages=%s max_results=%s",
            feed_url,
            keyword,
            access_mode,
            response_status or "rendered",
            page_meta.get("pages_scanned"),
            page_meta.get("visible_cards"),
            len(links),
            len(seen_keys),
            len(listings),
            parsed_titles[:3],
            original_url_count,
            verification_summary,
            page_meta.get("stopped_reason"),
            max_pages,
            max_results,
        )
        return listings

    def _govauctions_paging_limits(self) -> tuple[int, int]:
        max_pages = self._env_int("GOVAUCTIONS_MAX_PAGES", default=3, minimum=1, maximum=10)
        max_results = self._env_int("GOVAUCTIONS_MAX_RESULTS_PER_QUERY", default=75, minimum=1, maximum=150)
        return max_pages, max_results

    def _env_int(self, name: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(os.getenv(name, str(default)))
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    async def _govauctions_rendered_html(self, feed_url: str, keyword: str | None = None, *, max_pages: int = 3, max_results: int = 75) -> tuple[str | None, dict]:
        meta = {"pages_scanned": 0, "visible_cards": 0, "stopped_reason": "unknown"}
        try:
            async with chromium_browser() as browser:
                page = await browser.new_page()
                start_url = "https://govauctions.app/feed" if keyword else feed_url
                await page.goto(start_url, wait_until="domcontentloaded", timeout=10000)
                if keyword:
                    search = page.locator('input[placeholder="Search auctions..."]')
                    await search.fill(keyword, timeout=7000)
                    await search.press("Enter", timeout=7000)
                    try:
                        await page.wait_for_url(re.compile(r".*[?&]q="), timeout=7000)
                    except Exception:
                        pass
                try:
                    await page.wait_for_selector('a[href^="/auction/"]', timeout=7000)
                except Exception:
                    pass
                if keyword:
                    try:
                        await page.wait_for_function(
                            """keyword => document.body && document.body.innerText.toLowerCase().includes(keyword.toLowerCase())""",
                            keyword,
                            timeout=7000,
                        )
                    except Exception:
                        pass
                meta = await self._govauctions_load_more_results(page, max_pages=max_pages, max_results=max_results)
                html = await asyncio.wait_for(page.content(), timeout=3)
                return html, meta
        except Exception as exc:
            logger.info("GovAuctions.app rendered search failed url=%s keyword=%s error=%s", feed_url, keyword, str(exc)[:160])
            meta["stopped_reason"] = "timeout"
            return None, meta

    async def _govauctions_load_more_results(self, page, *, max_pages: int, max_results: int) -> dict:
        selector = 'a[href^="/auction/"]'
        pages_scanned = 1
        stopped_reason = "no_more_results"
        visible_cards = await self._govauctions_visible_card_count(page, selector)
        if visible_cards >= max_results:
            return {"pages_scanned": pages_scanned, "visible_cards": visible_cards, "stopped_reason": "max_results"}
        for _ in range(max(0, max_pages - 1)):
            before_count = visible_cards
            before_height = await page.evaluate("() => document.body ? document.body.scrollHeight : 0")
            clicked = await self._govauctions_click_more(page)
            if clicked:
                await page.wait_for_timeout(1800)
            else:
                await page.evaluate("() => window.scrollTo(0, document.body ? document.body.scrollHeight : 0)")
                await page.wait_for_timeout(2200)
            visible_cards = await self._govauctions_visible_card_count(page, selector)
            after_height = await page.evaluate("() => document.body ? document.body.scrollHeight : 0")
            if visible_cards > before_count or after_height > before_height:
                pages_scanned += 1
                if visible_cards >= max_results:
                    stopped_reason = "max_results"
                    break
                if pages_scanned >= max_pages:
                    stopped_reason = "max_pages"
                    break
                continue
            stopped_reason = "no_more_results"
            break
        else:
            stopped_reason = "max_pages"
        return {"pages_scanned": pages_scanned, "visible_cards": visible_cards, "stopped_reason": stopped_reason}

    async def _govauctions_visible_card_count(self, page, selector: str) -> int:
        try:
            return int(await page.locator(selector).count())
        except Exception:
            return 0

    async def _govauctions_click_more(self, page) -> bool:
        try:
            return bool(
                await page.evaluate(
                    """() => {
                        const pattern = /^(load more|show more|more results|next|next page)$/i;
                        const elements = Array.from(document.querySelectorAll('button,a'));
                        const target = elements.find(el => {
                            const text = (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim();
                            const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
                            const visible = !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                            return visible && !disabled && pattern.test(text);
                        });
                        if (!target) return false;
                        target.click();
                        return true;
                    }"""
                )
            )
        except Exception:
            return False

    def _govauctions_links_from_next_chunks(self, html: str) -> list[str]:
        html = html.replace("\\u002F", "/").replace("\\/", "/")
        hrefs = re.findall(r'(/auction/[A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=%-]+)', html)
        return list(dict.fromkeys(hrefs))

    def _govauctions_card_text(self, link) -> str:
        if not hasattr(link, "get_text"):
            return str(link)
        parts: list[str] = []
        for node in [link, link.find_parent(), link.find_parent().find_parent() if link.find_parent() else None]:
            if not node:
                continue
            text = node.get_text(" ", strip=True)
            if text and text not in parts:
                parts.append(text)
        return " ".join(parts)[:1200]

    def _parse_govauctions_card(self, govauctions_url: str, text: str, category: HardwareCategory, keyword: str) -> dict | None:
        slug = urlparse(govauctions_url).path.rstrip("/").split("/")[-1]
        if not slug:
            return None
        platform, platform_ids = self._govauctions_platform_from_slug(slug, text)
        title = self._govauctions_title_from_text(text, slug, platform)
        snippet = text or title
        if not title:
            return None
        price = self._extract_price(snippet)
        location = self._govauctions_location(snippet, slug)
        countdown = self._govauctions_countdown(snippet)
        calculated_end = self._govauctions_calculated_end_time(countdown)
        listing_status = self._govauctions_listing_status(calculated_end, snippet)
        canonical_url = self._govauctions_original_url(platform, platform_ids)
        source_listing_id = self._govauctions_source_listing_id(platform, platform_ids, slug)
        return {
            "title": title,
            "snippet": snippet[:900],
            "current_price": price,
            "original_source_platform": platform,
            "canonical_source_url": canonical_url,
            "source_listing_id": source_listing_id,
            "location_city": location.get("city"),
            "location_state": location.get("state"),
            "location_text": location.get("text"),
            "time_remaining": countdown,
            "calculated_end_time": calculated_end,
            "listing_status": listing_status,
            "matched_keyword": keyword,
            "category": category.value,
        }

    def _govauctions_platform_from_slug(self, slug: str, text: str) -> tuple[str | None, list[str]]:
        platforms = {
            "govdeals": "GovDeals",
            "gsa-auctions": "GSA Auctions",
            "gsaauctions": "GSA Auctions",
            "public-surplus": "Public Surplus",
            "publicsurplus": "Public Surplus",
            "govplanet": "GovPlanet",
            "municibid": "Municibid",
            "allsurplus": "AllSurplus",
            "proxibid": "Proxibid",
            "bidspotter": "BidSpotter",
            "hibid": "HiBid",
        }
        lower = slug.lower()
        for token, platform in platforms.items():
            match = re.search(rf"(?:^|-){re.escape(token)}-(\d+)(?:-(\d+))?(?:$|-)", lower)
            if match:
                return platform, [value for value in match.groups() if value]
        text_lower = text.lower()
        for token, platform in platforms.items():
            if token.replace("-", " ") in text_lower or token in text_lower:
                trailing = re.findall(r"(\d{2,})", slug)
                return platform, trailing[-2:]
        return None, re.findall(r"(\d{2,})", slug)[-2:]

    def _govauctions_original_url(self, platform: str | None, ids: list[str]) -> str | None:
        if not platform or not ids:
            return None
        if platform == "GovDeals" and len(ids) >= 2:
            return f"https://www.govdeals.com/en/asset/{ids[0]}/{ids[1]}"
        if platform == "Public Surplus" and ids:
            return f"https://www.publicsurplus.com/sms/auction/view?auc={ids[-1]}"
        if platform == "GSA Auctions":
            return f"https://gsaauctions.gov/auctions/auctions-list?search={quote_plus(' '.join(ids))}"
        return None

    async def _govauctions_detail_original_url(self, govauctions_url: str) -> str | None:
        try:
            async with chromium_browser() as browser:
                page = await browser.new_page()
                await page.goto(govauctions_url, wait_until="domcontentloaded", timeout=12000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=4000)
                except Exception:
                    pass
                urls = await page.evaluate(
                    """() => {
                        const values = [];
                        const push = value => {
                            if (typeof value === 'string' && value.trim()) values.push(value.trim());
                        };
                        document.querySelectorAll('a[href]').forEach(a => push(a.href || a.getAttribute('href')));
                        document.querySelectorAll('[data-url],[data-href],[data-link],button[onclick],a[onclick]').forEach(el => {
                            push(el.getAttribute('data-url'));
                            push(el.getAttribute('data-href'));
                            push(el.getAttribute('data-link'));
                            push(el.getAttribute('onclick'));
                        });
                        Array.from(document.scripts || []).forEach(script => push(script.textContent || ''));
                        return values;
                    }"""
                )
        except Exception as exc:
            logger.info("GovAuctions.app detail original URL extraction failed url=%s error=%s", govauctions_url, str(exc)[:160])
            return None
        for candidate in self._extract_original_urls_from_values(urls, govauctions_url):
            return candidate
        return None

    def _extract_original_urls_from_values(self, values: list[str], base_url: str) -> list[str]:
        found: list[str] = []
        for value in values:
            if not value:
                continue
            for raw_url in re.findall(r"https?://[^\s'\"<>),]+", value):
                normalized = self._normalize_auction_url(raw_url)
                if normalized and "govauctions.app" not in urlparse(normalized).netloc.lower():
                    found.append(normalized)
            if value.startswith("/"):
                absolute = urljoin(base_url, value)
                normalized = self._normalize_auction_url(absolute)
                if normalized and "govauctions.app" not in urlparse(normalized).netloc.lower():
                    found.append(normalized)
        return list(dict.fromkeys(found))

    def _normalize_auction_url(self, url: str) -> str | None:
        cleaned = url.strip().rstrip(".;")
        domain = urlparse(cleaned).netloc.lower()
        allowed = [
            "publicsurplus.com",
            "govdeals.com",
            "gsaauctions.gov",
            "govplanet.com",
            "auctionzip.com",
            "ebay.com",
            "municibid.com",
            "proxibid.com",
            "bidspotter.com",
            "allsurplus.com",
            "hibid.com",
        ]
        if not any(token in domain for token in allowed):
            return None
        return cleaned

    def _govauctions_platform_from_url(self, url: str) -> str | None:
        domain = urlparse(url).netloc.lower()
        if "govdeals.com" in domain:
            return "GovDeals"
        if "publicsurplus.com" in domain:
            return "Public Surplus"
        if "gsaauctions.gov" in domain:
            return "GSA Auctions"
        if "govplanet.com" in domain:
            return "GovPlanet"
        if "auctionzip.com" in domain:
            return "AuctionZip"
        if "ebay.com" in domain:
            return "eBay"
        if "municibid.com" in domain:
            return "Municibid"
        if "proxibid.com" in domain:
            return "Proxibid"
        if "bidspotter.com" in domain:
            return "BidSpotter"
        if "allsurplus.com" in domain:
            return "AllSurplus"
        if "hibid.com" in domain:
            return "HiBid"
        return None

    def _govauctions_source_listing_id_from_url(self, url: str) -> str | None:
        platform = self._govauctions_platform_from_url(url)
        digits = re.findall(r"\d{2,}", url)
        if platform and digits:
            normalized_platform = platform.lower().replace(" ", "_")
            return f"{normalized_platform}:{':'.join(digits[-2:])}"
        return None

    def _govauctions_source_listing_id(self, platform: str | None, ids: list[str], slug: str) -> str:
        if platform and ids:
            normalized_platform = platform.lower().replace(" ", "_")
            return f"{normalized_platform}:{':'.join(ids)}"
        return f"govauctions:{slug}"

    def _govauctions_title_from_text(self, text: str, slug: str, platform: str | None) -> str:
        cleaned = re.sub(r"🔥?\s*\d+\s*bids?", "", text, flags=re.I)
        cleaned = re.sub(r"\$\s?[0-9][0-9,]*(?:\.\d{2})?", " ", cleaned)
        cleaned = re.sub(r"⏰\s*[^·]+", " ", cleaned)
        if platform:
            cleaned = re.split(re.escape(platform), cleaned, flags=re.I)[0]
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -·")
        if cleaned and len(cleaned) >= 6 and "/auction/" not in cleaned.lower() and "govauctions.app" not in cleaned.lower():
            return cleaned[:220]
        words = slug.replace("-", " ")
        for token in ["govdeals", "public surplus", "gsa auctions", "gsaauctions", "govplanet"]:
            words = words.replace(token, "")
        words = re.sub(r"\b\d+\b", "", words)
        return re.sub(r"\s+", " ", words).strip().title()[:220]

    def _govauctions_location(self, text: str, slug: str) -> dict[str, str | None]:
        location_match = re.search(r"([A-Z][A-Za-z .'-]{2,}),\s*([A-Z]{2})(?:\b| ·)", text)
        if location_match:
            city = location_match.group(1).strip()
            state = location_match.group(2).strip()
            return {"city": city, "state": state, "text": f"{city}, {state}"}
        slug_match = re.search(r"-([a-z][a-z-]+)-([a-z]{2})-(?:govdeals|public-surplus|gsa-auctions|govplanet|municibid)", slug, re.I)
        if slug_match:
            city = slug_match.group(1).replace("-", " ").title()
            state = slug_match.group(2).upper()
            return {"city": city, "state": state, "text": f"{city}, {state}"}
        return {"city": None, "state": None, "text": None}

    def _govauctions_countdown(self, text: str) -> str | None:
        match = re.search(r"(?:⏰\s*)?(\d+\s*d(?:ays?)?\s+\d+\s*h(?:ours?)?|\d+\s*h(?:ours?)?\s+\d+\s*m(?:in(?:ute)?s?)?|\d+\s*d(?:ays?)?|\d+\s*h(?:ours?)?|\d+\s*m(?:in(?:ute)?s?)?)", text, re.I)
        return match.group(1).strip() if match else None

    def _govauctions_calculated_end_time(self, countdown: str | None) -> str | None:
        if not countdown:
            return None
        lower = countdown.lower()
        days = re.search(r"(\d+)\s*d", lower) or re.search(r"(\d+)\s*day", lower)
        hours = re.search(r"(\d+)\s*h", lower) or re.search(r"(\d+)\s*hour", lower)
        minutes = re.search(r"(\d+)\s*m", lower) or re.search(r"(\d+)\s*min", lower)
        delta = timedelta(
            days=int(days.group(1)) if days else 0,
            hours=int(hours.group(1)) if hours else 0,
            minutes=int(minutes.group(1)) if minutes else 0,
        )
        if delta.total_seconds() <= 0:
            return None
        return (utc_now() + delta).isoformat()

    def _govauctions_listing_status(self, calculated_end_time: str | None, text: str) -> str:
        lower = text.lower()
        if any(token in lower for token in ["auction ended", "closed", "sold", "no longer available"]):
            return "ended"
        if not calculated_end_time:
            return "needs_manual_review"
        end_time = datetime.fromisoformat(calculated_end_time)
        if end_time <= utc_now():
            return "ended"
        if end_time - utc_now() <= timedelta(hours=24):
            return "ending_soon"
        return "active"

    def _is_relevant(self, title: str, snippet: str | None, domain: str | None) -> bool:
        haystack = f"{title} {snippet or ''} {domain or ''}".lower()
        blocked = [
            "reddit.com",
            "youtube.com",
            "facebook.com",
            "wikipedia.org",
            "indeed.com",
            "manualslib.com",
            "firmware",
            "driver download",
        ]
        if any(token in haystack for token in blocked):
            return False
        return any(
            token in haystack
            for token in [
                "auction",
                "surplus",
                "liquidation",
                "lot",
                "bulk",
                "server",
                "poweredge",
                "proliant",
                "supermicro",
                "nvidia",
                "a100",
                "h100",
                "gpu",
                "memory",
                "rdimm",
                "ecc",
                "ssd",
                "nvme",
                "hard drive",
                "xeon",
                "epyc",
                "cpu",
                "desktop",
                "laptop",
                "computer",
                "itad",
                "thinksystem",
                "ucs",
                "drive array",
                "storage array",
                "workstation",
                "switch",
                "networking",
            ]
        )

    async def _bing_search(self, query: str, max_results: int) -> list[HardwareSearchHit]:
        url = f"https://www.bing.com/search?q={quote_plus(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NOVAIONHardwareHunter/2.1; +https://novaion.ai)"}
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        hits: list[HardwareSearchHit] = []
        for item in soup.select("li.b_algo")[: max_results * 2]:
            link = item.select_one("h2 a")
            if not link:
                continue
            href = link.get("href") or ""
            title = link.get_text(" ", strip=True)
            snippet_node = item.select_one(".b_caption p") or item.select_one("p")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else None
            if not href or not title:
                continue
            domain = urlparse(href).netloc.lower().removeprefix("www.")
            hits.append(HardwareSearchHit(title=title, url=href, snippet=snippet, domain=domain))
            if len(hits) >= max_results:
                break
        return hits

    async def _public_surplus_search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        keyword = self._public_surplus_keyword(query)
        cat_id = "1" if query.category.value in {"servers", "memory", "storage", "cpu", "gpu"} else "2"
        url = (
            "https://www.publicsurplus.com/sms/browse/search?"
            f"posting=y&keyWord={quote_plus(keyword)}&catId={cat_id}&page=0&sortBy=end&sortDesc=N"
        )
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NOVAIONHardwareHunter/2.1; +https://novaion.ai)"}
        async with httpx.AsyncClient(timeout=25, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        listings: list[RawHardwareListing] = []
        seen: set[str] = set()
        for link in soup.select('a[href*="/sms/auction/view?auc="]'):
            href = link.get("href") or ""
            title = link.get_text(" ", strip=True)
            if not title or href in seen:
                continue
            seen.add(href)
            absolute_url = urljoin("https://www.publicsurplus.com", href)
            container_text = link.find_parent().get_text(" ", strip=True) if link.find_parent() else title
            snippet = container_text[:500]
            if not self._is_relevant(title, snippet, "publicsurplus.com"):
                continue
            if not self._is_category_relevant(query.category.value, title, snippet):
                continue
            classification = self.quality.classify("Public Surplus", absolute_url, title, snippet)
            listings.append(
                RawHardwareListing(
                    source_name="Public Surplus",
                    source_url=absolute_url,
                    original_title=title,
                    original_description=snippet,
                    category=query.category,
                    page_type=classification.page_type,
                    classification_reason=classification.reason,
                    raw_data={
                        "query": query.generated_query_en,
                        "direct_source_url": url,
                        "domain": "publicsurplus.com",
                        "adapter_type": "public_surplus_html",
                        "page_type": classification.page_type.value,
                        "classification_reason": classification.reason,
                    },
                )
            )
            if len(listings) >= request.max_results_per_query:
                break
        return listings

    async def _municibid_search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        keyword = self._marketplace_keyword(query)
        urls = [
            f"https://municibid.com/Search?query={quote_plus(keyword)}",
            f"https://municibid.com/Browse?search={quote_plus(keyword)}",
        ]
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NOVAIONHardwareHunter/2.5; +https://novaion.ai)"}
        listings: list[RawHardwareListing] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=25, follow_redirects=True, headers=headers) as client:
            for url in urls:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                except Exception:
                    continue
                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.select("a[href]"):
                    href = link.get("href") or ""
                    title = link.get_text(" ", strip=True)
                    absolute_url = urljoin("https://municibid.com", href)
                    parsed = urlparse(absolute_url)
                    if "municibid.com" not in parsed.netloc.lower():
                        continue
                    if absolute_url in seen or not title:
                        continue
                    container = link.find_parent()
                    snippet = container.get_text(" ", strip=True)[:500] if container else title
                    if not self._is_relevant(title, snippet, "municibid.com"):
                        continue
                    if not self._is_category_relevant(query.category.value, title, snippet):
                        continue
                    classification = self.quality.classify("Municibid", absolute_url, title, snippet)
                    if classification.page_type.value == "irrelevant":
                        continue
                    seen.add(absolute_url)
                    listings.append(
                        RawHardwareListing(
                            source_name="Municibid",
                            source_url=absolute_url,
                            original_title=title,
                            original_description=snippet,
                            category=query.category,
                            page_type=classification.page_type,
                            classification_reason=classification.reason,
                            raw_data={
                                "query": query.generated_query_en,
                                "direct_source_url": url,
                                "domain": "municibid.com",
                                "adapter_type": "municibid_html",
                                "page_type": classification.page_type.value,
                                "classification_reason": classification.reason,
                            },
                        )
                    )
                    if len(listings) >= request.max_results_per_query:
                        return listings
        return listings

    def _clean_source_query(self, query: str) -> str:
        cleaned = query
        for token in [
            "site:publicsurplus.com",
            "site:govdeals.com",
            "site:municibid.com",
            "site:gsaauctions.gov",
            "site:govauctions.app",
            "site:allsurplus.com",
            "site:bidspotter.com",
            "site:proxibid.com",
            "site:ebay.com",
            "site:hgpauction.com",
        ]:
            cleaned = cleaned.replace(token, "")
        for token in [
            "Texas",
            "California",
            "Georgia",
            "Oregon",
            "North Carolina",
            "Oklahoma",
            "TX",
            "CA",
            "GA",
            "OR",
            "NC",
            "OK",
            "lot",
            "bulk",
            "auction",
            "surplus",
        ]:
            cleaned = cleaned.replace(token, "")
        return " ".join(cleaned.split()) or "server"

    def _marketplace_keyword(self, query) -> str:
        template = getattr(query, "query_template", None)
        if template:
            return self._clean_source_query(str(template))
        return self._clean_source_query(query.generated_query_en)

    def _public_surplus_keyword(self, query) -> str:
        template = getattr(query, "query_template", None)
        if template:
            return self._clean_source_query(str(template))
        by_category = {
            "servers": "server",
            "gpu": "gpu",
            "memory": "memory",
            "storage": "hard drive",
            "cpu": "cpu",
        }
        return by_category.get(query.category.value, self._clean_source_query(query.generated_query_en))

    def _is_category_relevant(self, category: str, title: str, snippet: str | None) -> bool:
        text = f"{title} {snippet or ''}".lower()
        category_terms = {
            "servers": ["server", "poweredge", "proliant", "supermicro", "blade"],
            "gpu": ["gpu", "graphics card", "graphic card", "nvidia", "amd radeon", "a100", "h100", "rtx", "tesla"],
            "memory": ["memory", "ram", "rdimm", "dimm", "ddr4", "ddr5", "ecc"],
            "storage": ["ssd", "nvme", "hard drive", "hdd", "storage", "sas drive", "sata drive"],
            "cpu": ["cpu", "processor", "xeon", "epyc"],
            "networking": ["switch", "router", "firewall", "cisco", "juniper", "networking", "network equipment"],
            "computers_it": ["computer", "workstation", "laptop", "desktop", "electronics", "it equipment", "monitor", "printer"],
        }
        if category == "storage" and any(token in text for token in ["hard drive removed", "drives removed", "no hard drive"]):
            return False
        if category == "cpu" and any(token in text for token in ["cpu tower", "desktop", "laptop"]) and not any(token in text for token in ["processor", "xeon", "epyc"]):
            return False
        return any(token in text for token in category_terms.get(category, []))


class ManualHardwareImportAdapter(HardwareSourceAdapter):
    source_name = "Manual Import"
    adapter_type = "manual_hardware_import"

    def __init__(self) -> None:
        self.quality = HardwareResultQualityClassifier()

    async def search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        listings: list[RawHardwareListing] = []
        urls = self._extract_urls(request.manual_text or "")
        urls.extend(str(url) for url in request.manual_urls)
        seen: set[str] = set()
        for url in urls:
            normalized_url = self._normalize_url(url)
            if not normalized_url or normalized_url in seen:
                continue
            seen.add(normalized_url)
            source_name = self._infer_source(normalized_url)
            title = self._title_for_url(normalized_url, request.manual_text)
            snippet = self._snippet_for_url(normalized_url, request.manual_text)
            classification = self.quality.classify(source_name, normalized_url, title, snippet)
            manual_requires_review = source_name != self.source_name and classification.page_type != HardwareResultPageType.SPECIFIC_LISTING
            page_type = HardwareResultPageType.SPECIFIC_LISTING if manual_requires_review else classification.page_type
            classification_reason = (
                "Manual imported marketplace URL needs review; paste the specific lot URL when this is a search or collection page."
                if manual_requires_review
                else classification.reason
            )
            detail = {
                "needs_manual_review": True,
                "listing_status": "needs_manual_review",
                "listing_status_reason": classification_reason,
                "status_check_result": "manual_import_needs_specific_listing_url",
            } if manual_requires_review else {}
            listings.append(
                RawHardwareListing(
                    source_name=source_name,
                    source_url=normalized_url,
                    original_title=title,
                    original_description=snippet,
                    category=query.category,
                    page_type=page_type,
                    classification_reason=classification_reason,
                    raw_data={
                        "query": query.generated_query_en,
                        "manual": True,
                        "adapter_type": self.adapter_type,
                        "source_access_mode": "manual_import",
                        "matched_keywords": [getattr(query, "query_template", None) or "manual import"],
                        "detail": detail,
                        "page_type": page_type.value,
                        "classification_reason": classification_reason,
                    },
                )
            )
        if request.manual_text and not listings:
            listings.append(
                RawHardwareListing(
                    source_name=self.source_name,
                    source_url="manual://hardware-listing",
                    original_title="Manual hardware listing",
                    original_description=request.manual_text,
                    category=query.category,
                    raw_data={"query": query.generated_query_en, "manual": True},
                )
            )
        return listings

    def _extract_urls(self, text: str) -> list[str]:
        urls = re.findall(r"https?://[^\s\"'<>]+", text or "")
        relative_patterns = [
            r"/en/asset/[A-Za-z0-9\-_/?.=&%]+",
            r"/sms/auction/view\?auc=\d+[A-Za-z0-9\-_/?.=&%]*",
        ]
        for pattern in relative_patterns:
            for match in re.findall(pattern, text or ""):
                if match.startswith("/en/asset/"):
                    urls.append(urljoin("https://www.govdeals.com", match))
                elif match.startswith("/sms/auction/view"):
                    urls.append(urljoin("https://www.publicsurplus.com", match))
        return urls

    def _normalize_url(self, url: str) -> str | None:
        cleaned = (url or "").strip().strip(".,);]'\"")
        if not cleaned:
            return None
        parsed = urlparse(cleaned)
        if not parsed.scheme or not parsed.netloc:
            return None
        return cleaned

    def _infer_source(self, url: str) -> str:
        domain = urlparse(url).netloc.lower()
        if "govdeals.com" in domain:
            return "GovDeals"
        if "publicsurplus.com" in domain:
            return "Public Surplus"
        if "municibid.com" in domain:
            return "Municibid"
        if "gsaauctions.gov" in domain:
            return "GSA Auctions"
        if "hibid.com" in domain:
            return "HiBid"
        if "proxibid.com" in domain:
            return "Proxibid"
        if "bidspotter.com" in domain:
            return "BidSpotter"
        if "ebay.com" in domain:
            return "eBay"
        if "govauctions.app" in domain:
            return "GovAuctions.app"
        return self.source_name

    def _title_for_url(self, url: str, text: str | None) -> str:
        if text:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            for index, line in enumerate(lines):
                if url in line:
                    candidates = [line, *(lines[max(0, index - 2):index])]
                    for candidate in candidates:
                        if len(candidate) > 12 and not candidate.startswith("http"):
                            return candidate[:180]
        parsed = urlparse(url)
        source = self._infer_source(url)
        return f"{source} listing {parsed.path.rstrip('/').split('/')[-1] or parsed.netloc}"

    def _snippet_for_url(self, url: str, text: str | None) -> str | None:
        if not text:
            return None
        idx = text.find(url)
        if idx < 0:
            return text[:800]
        start = max(0, idx - 300)
        end = min(len(text), idx + len(url) + 500)
        return text[start:end].strip()
