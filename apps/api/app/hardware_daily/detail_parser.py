from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from app.hardware_daily.models import ListingStatus, RawHardwareListing, utc_now


class HardwareListingDetailParser:
    def __init__(self) -> None:
        self.headers = {"User-Agent": "Mozilla/5.0 (compatible; NOVAIONHardwareHunter/2.2; +https://novaion.ai)"}

    async def enrich(self, raw: RawHardwareListing) -> RawHardwareListing:
        detail = dict(raw.raw_data.get("detail") or {})
        detail["checked_at"] = utc_now().isoformat()
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=self.headers) as client:
                response = await client.get(raw.source_url)
            detail["http_status"] = response.status_code
            if response.status_code >= 400:
                detail["listing_status"] = ListingStatus.UNAVAILABLE.value
                detail["unavailable_reason"] = f"HTTP {response.status_code}"
                return self._with_detail(raw, detail, "http_unavailable")
            text = response.text
            if self._looks_blocked(text):
                detail["listing_status"] = ListingStatus.UNAVAILABLE.value
                detail["unavailable_reason"] = "captcha_or_access_challenge"
                return self._with_detail(raw, detail, "blocked_or_challenged")
            domain = urlparse(raw.source_url).netloc.lower()
            if "publicsurplus.com" in domain:
                detail.update(self._parse_public_surplus(raw.source_url, text))
            elif "govdeals.com" in domain:
                detail.update(self._parse_spa_shell(raw, text, source_name="GovDeals"))
            elif "ebay.com" in domain:
                detail.update(self._parse_spa_shell(raw, text, source_name="eBay"))
            else:
                detail.update(self._parse_generic(raw, text))
            return self._with_detail(raw, detail, "checked")
        except httpx.TimeoutException:
            detail["listing_status"] = ListingStatus.UNKNOWN.value
            detail["unavailable_reason"] = "detail_page_timeout"
            return self._with_detail(raw, detail, "timeout")
        except Exception as exc:
            detail["listing_status"] = ListingStatus.UNKNOWN.value
            detail["unavailable_reason"] = str(exc)[:240]
            return self._with_detail(raw, detail, "parse_error")

    def _with_detail(self, raw: RawHardwareListing, detail: dict, status: str) -> RawHardwareListing:
        raw.raw_data["detail"] = detail
        raw.detail_checked_at = utc_now()
        raw.detail_parse_status = status
        if detail.get("description") and not raw.original_description:
            raw.original_description = detail["description"]
        if detail.get("title"):
            raw.original_title = detail["title"]
        if detail.get("source_listing_id"):
            raw.source_listing_id = detail["source_listing_id"]
        return raw

    def _looks_blocked(self, html: str) -> bool:
        lower = html.lower()
        return any(token in lower for token in ["captcha", "access denied", "verify you are human", "robot check"])

    def _parse_public_surplus(self, url: str, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        query = parse_qs(urlparse(url).query)
        auc = (query.get("auc") or [None])[0]
        title_match = re.search(r"Auction\s+#?(\d+)\s+-\s+(.+?)(?:Auction Extended|Auction Started|Auction Ended|Pick-up Location|# of Bids)", text, re.I)
        title = title_match.group(2).strip() if title_match else None
        listing_id = auc or (title_match.group(1) if title_match else None)
        ended_match = re.search(r"Auction Ended\s+([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s+[AP]M\s+[A-Z]{2,4})", text)
        started_ended = bool(ended_match)
        time_left_match = re.search(r"Time Left\s+(.+?)(?:# of Bids|Current Price|High Bid|Final Price|Minimum bid)", text, re.I)
        price = self._extract_money_after(text, ["Current Price", "High Bid", "Final Price", "Minimum bid"])
        bid_count = self._extract_int_after(text, "# of Bids")
        location = self._parse_public_surplus_location(text)
        shipping_text = self._slice_after(text, "Shipping", 400)
        description = self._public_surplus_description(text)
        listing_status = ListingStatus.ENDED.value if started_ended else ListingStatus.ACTIVE.value
        if time_left_match:
            hours_left = self._hours_from_time_left(time_left_match.group(1))
            if hours_left is not None and hours_left <= 24:
                listing_status = ListingStatus.ENDING_SOON.value
        return {
            "source_listing_id": listing_id,
            "lot_number": listing_id,
            "title": title,
            "description": description,
            "current_price": price,
            "total_price": price,
            "bid_count": bid_count,
            "auction_end_time_raw": ended_match.group(1) if ended_match else None,
            "auction_end_time": self._parse_public_surplus_datetime(ended_match.group(1)) if ended_match else None,
            "time_remaining": time_left_match.group(1).strip() if time_left_match else None,
            "listing_status": listing_status,
            "listing_status_reason": "Public Surplus detail page parsed",
            "location_city": location.get("city"),
            "location_state": location.get("state"),
            "zip_code": location.get("zip_code"),
            "pickup_only": "buyer must pickup" in text.lower() or "local pickup" in text.lower(),
            "shipping_available": "shipping options" in text.lower() and "freight" in shipping_text.lower(),
            "seller_name": self._extract_between(text, "View ", " Auctions") or "Public Surplus seller",
        }

    def _parse_spa_shell(self, raw: RawHardwareListing, html: str, source_name: str) -> dict:
        has_listing_data = raw.original_title.lower() not in {"home", source_name.lower()}
        return {
            "title": raw.original_title if has_listing_data else None,
            "description": raw.original_description,
            "listing_status": ListingStatus.UNKNOWN.value,
            "listing_status_reason": f"{source_name} public HTML is an app shell; detail fields need official API/manual review.",
            "needs_manual_review": True,
        }

    def _parse_generic(self, raw: RawHardwareListing, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        title = soup.title.get_text(" ", strip=True) if soup.title else raw.original_title
        price = self._extract_money_after(text, ["Current Bid", "Price", "Final Price", "Buy It Now"])
        status = ListingStatus.UNKNOWN.value
        lower = text.lower()
        if any(token in lower for token in ["auction ended", "sold", "closed"]):
            status = ListingStatus.ENDED.value
        elif any(token in lower for token in ["current bid", "buy it now", "auction ends"]):
            status = ListingStatus.ACTIVE.value
        return {
            "title": title,
            "description": text[:900],
            "current_price": price,
            "total_price": price,
            "listing_status": status,
            "listing_status_reason": "Generic public HTML parsed",
        }

    def _extract_money_after(self, text: str, labels: list[str]) -> float | None:
        for label in labels:
            match = re.search(rf"{re.escape(label)}\s*:?\s*\$?\s*([0-9][0-9,]*(?:\.\d{{2}})?)", text, re.I)
            if match:
                return float(match.group(1).replace(",", ""))
        return None

    def _extract_int_after(self, text: str, label: str) -> int | None:
        match = re.search(rf"{re.escape(label)}\s*:?\s*(\d+)", text, re.I)
        return int(match.group(1)) if match else None

    def _extract_between(self, text: str, start: str, end: str) -> str | None:
        try:
            _, tail = text.split(start, 1)
            value, _ = tail.split(end, 1)
            return value.strip()
        except ValueError:
            return None

    def _slice_after(self, text: str, label: str, length: int) -> str:
        index = text.lower().find(label.lower())
        return text[index : index + length] if index >= 0 else ""

    def _parse_public_surplus_location(self, text: str) -> dict[str, str | None]:
        match = re.search(r"Pick-up Location.+?\[\s*(.+?)\s+([A-Za-z .'-]+),\s*([A-Z]{2})\s+(\d{5})\s*\]", text, re.I)
        if not match:
            return {"city": None, "state": None, "zip_code": None}
        return {"city": match.group(2).strip(), "state": match.group(3), "zip_code": match.group(4)}

    def _public_surplus_description(self, text: str) -> str | None:
        title_index = text.lower().find("description")
        if title_index >= 0:
            return text[title_index : title_index + 900]
        return text[:900]

    def _hours_from_time_left(self, value: str) -> float | None:
        lower = value.lower()
        days = re.search(r"(\d+)\s*day", lower)
        hours = re.search(r"(\d+)\s*hour", lower)
        minutes = re.search(r"(\d+)\s*min", lower)
        total = 0.0
        if days:
            total += int(days.group(1)) * 24
        if hours:
            total += int(hours.group(1))
        if minutes:
            total += int(minutes.group(1)) / 60
        return total if any([days, hours, minutes]) else None

    def _parse_public_surplus_datetime(self, value: str) -> str | None:
        zones = {"MDT": timezone(timedelta(hours=-6)), "MST": timezone(timedelta(hours=-7)), "PDT": timezone(timedelta(hours=-7)), "PST": timezone(timedelta(hours=-8))}
        match = re.match(r"(.+)\s+([A-Z]{2,4})$", value)
        if not match:
            return None
        timestamp, zone = match.groups()
        try:
            parsed = datetime.strptime(timestamp, "%b %d, %Y %I:%M %p")
        except ValueError:
            try:
                parsed = datetime.strptime(timestamp, "%B %d, %Y %I:%M %p")
            except ValueError:
                return None
        return parsed.replace(tzinfo=zones.get(zone, timezone.utc)).astimezone(timezone.utc).isoformat()
