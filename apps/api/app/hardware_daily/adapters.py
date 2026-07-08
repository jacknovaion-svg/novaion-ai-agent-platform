from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.hardware_daily.models import HardwareResultPageType, HardwareScanRequest, RawHardwareListing, utc_now
from app.hardware_daily.quality import HardwareResultQualityClassifier
from app.site_hunter.web_search import WebSearchClient


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
        for url in request.manual_urls:
            classification = self.quality.classify(self.source_name, str(url), str(url), request.manual_text)
            listings.append(
                RawHardwareListing(
                    source_name=self.source_name,
                    source_url=str(url),
                    original_title=str(url),
                    original_description=request.manual_text,
                    category=query.category,
                    page_type=classification.page_type,
                    classification_reason=classification.reason,
                    raw_data={"query": query.generated_query_en, "manual": True},
                )
            )
        if request.manual_text and not request.manual_urls:
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
