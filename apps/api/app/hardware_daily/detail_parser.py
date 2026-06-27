from __future__ import annotations

import re
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from app.hardware_daily.models import AuctionEndVerificationLevel, ListingStatus, RawHardwareListing, utc_now


TZ_OFFSETS = {
    "UTC": timezone.utc,
    "GMT": timezone.utc,
    "EDT": timezone(timedelta(hours=-4)),
    "EST": timezone(timedelta(hours=-5)),
    "CDT": timezone(timedelta(hours=-5)),
    "CST": timezone(timedelta(hours=-6)),
    "MDT": timezone(timedelta(hours=-6)),
    "MST": timezone(timedelta(hours=-7)),
    "PDT": timezone(timedelta(hours=-7)),
    "PST": timezone(timedelta(hours=-8)),
}


class HardwareListingDetailParser:
    def __init__(self) -> None:
        self.headers = {"User-Agent": "Mozilla/5.0 (compatible; NOVAIONHardwareHunter/2.2; +https://novaion.ai)"}

    async def enrich(self, raw: RawHardwareListing) -> RawHardwareListing:
        detail = dict(raw.raw_data.get("detail") or {})
        captured_at = utc_now()
        detail["checked_at"] = captured_at.isoformat()
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=self.headers) as client:
                response = await client.get(raw.source_url)
            detail["http_status"] = response.status_code
            if response.status_code >= 400:
                detail["listing_status"] = ListingStatus.REMOVED.value if response.status_code == 404 else ListingStatus.UNAVAILABLE.value
                detail["unavailable_reason"] = f"HTTP {response.status_code}"
                detail.update(self._extract_secondary_signals(raw, captured_at))
                return self._with_detail(raw, detail, "http_unavailable")
            text = response.text
            if self._looks_blocked(text):
                detail["listing_status"] = ListingStatus.NEEDS_MANUAL_REVIEW.value
                detail["unavailable_reason"] = "captcha_or_access_challenge"
                detail["needs_manual_review"] = True
                detail.update(self._extract_secondary_signals(raw, captured_at))
                return self._with_detail(raw, detail, "blocked_or_challenged")
            domain = urlparse(raw.source_url).netloc.lower()
            if "publicsurplus.com" in domain:
                detail.update(self._parse_public_surplus(raw.source_url, text, captured_at))
            elif "govdeals.com" in domain:
                detail.update(self._parse_spa_shell(raw, text, source_name="GovDeals", captured_at=captured_at))
            elif "ebay.com" in domain:
                detail.update(self._parse_spa_shell(raw, text, source_name="eBay", captured_at=captured_at))
            else:
                detail.update(self._parse_generic(raw, text, captured_at))
            detail.update(self._finalize_status(detail, captured_at))
            return self._with_detail(raw, detail, "checked")
        except httpx.TimeoutException:
            detail["listing_status"] = ListingStatus.NEEDS_MANUAL_REVIEW.value
            detail["needs_manual_review"] = True
            detail["unavailable_reason"] = "detail_page_timeout"
            detail.update(self._extract_secondary_signals(raw, captured_at))
            detail.update(self._finalize_status(detail, captured_at))
            return self._with_detail(raw, detail, "timeout")
        except Exception as exc:
            detail["listing_status"] = ListingStatus.NEEDS_MANUAL_REVIEW.value
            detail["needs_manual_review"] = True
            detail["unavailable_reason"] = str(exc)[:240]
            detail.update(self._extract_secondary_signals(raw, captured_at))
            detail.update(self._finalize_status(detail, captured_at))
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

    def _parse_public_surplus(self, url: str, html: str, captured_at: datetime) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        query = parse_qs(urlparse(url).query)
        auc = (query.get("auc") or [None])[0]
        title_match = re.search(r"Auction\s+#?(\d+)\s+-\s+(.+?)(?:Auction Extended|Auction Started|Auction Ended|Pick-up Location|# of Bids)", text, re.I)
        title = title_match.group(2).strip() if title_match else None
        listing_id = auc or (title_match.group(1) if title_match else None)
        structured_text = " ".join(self._structured_text_fragments(soup))
        searchable_text = f"{text} {structured_text}"
        ended_match = re.search(r"Auction Ended\s+([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s+[AP]M\s+[A-Z]{2,4})", searchable_text)
        started_ended = bool(ended_match)
        time_left_match = self._extract_countdown(searchable_text)
        price = self._extract_money_after(text, ["Current Price", "High Bid", "Final Price", "Minimum bid"])
        bid_count = self._extract_int_after(text, "# of Bids")
        location = self._parse_public_surplus_location(text)
        shipping_text = self._slice_after(text, "Shipping", 400)
        description = self._public_surplus_description(text)
        signals = self._extract_end_time_signals(searchable_text, captured_at)
        if ended_match:
            signals.update(self._absolute_end_time_payload(ended_match.group(1), AuctionEndVerificationLevel.SOURCE_CONFIRMED))
        elif time_left_match:
            signals.update(self._countdown_payload(time_left_match, captured_at))
        return {
            "source_listing_id": listing_id,
            "lot_number": listing_id,
            "title": title,
            "description": description,
            "current_price": price,
            "total_price": price,
            "bid_count": bid_count,
            **signals,
            "listing_status": signals.get("listing_status") if signals.get("countdown_raw_text") else (ListingStatus.ENDED.value if started_ended else signals.get("listing_status", ListingStatus.ACTIVE.value)),
            "listing_status_reason": "Public Surplus detail page parsed",
            "location_city": location.get("city"),
            "location_state": location.get("state"),
            "zip_code": location.get("zip_code"),
            "pickup_only": "buyer must pickup" in text.lower() or "local pickup" in text.lower(),
            "shipping_available": "shipping options" in text.lower() and "freight" in shipping_text.lower(),
            "seller_name": self._extract_between(text, "View ", " Auctions") or "Public Surplus seller",
        }

    def _parse_spa_shell(self, raw: RawHardwareListing, html: str, source_name: str, captured_at: datetime) -> dict:
        has_listing_data = raw.original_title.lower() not in {"home", source_name.lower()}
        secondary = self._extract_secondary_signals(raw, captured_at)
        status = secondary.get("listing_status") or ListingStatus.NEEDS_MANUAL_REVIEW.value
        return {
            "title": raw.original_title if has_listing_data else None,
            "description": raw.original_description,
            **secondary,
            "listing_status": status,
            "listing_status_reason": f"{source_name} public HTML is an app shell; detail fields need official API/manual review.",
            "needs_manual_review": not bool(secondary.get("end_time_utc")),
        }

    def _parse_generic(self, raw: RawHardwareListing, html: str, captured_at: datetime) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        structured_text = " ".join(self._structured_text_fragments(soup))
        searchable_text = f"{text} {structured_text}"
        title = soup.title.get_text(" ", strip=True) if soup.title else raw.original_title
        price = self._extract_money_after(text, ["Current Bid", "Price", "Final Price", "Buy It Now"])
        signals = self._extract_end_time_signals(searchable_text, captured_at)
        return {
            "title": title,
            "description": text[:900],
            "current_price": price,
            "total_price": price,
            **signals,
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
        duration = self._duration_from_countdown(value)
        return duration.total_seconds() / 3600 if duration else None

    def _duration_from_countdown(self, value: str) -> timedelta | None:
        lower = value.lower()
        days = re.search(r"(\d+)\s*(?:day|d)\b", lower)
        hours = re.search(r"(\d+)\s*(?:hour|hr|h)\b", lower)
        minutes = re.search(r"(\d+)\s*(?:min|minute|m)\b", lower)
        total = 0.0
        if days:
            total += int(days.group(1)) * 24
        if hours:
            total += int(hours.group(1))
        if minutes:
            total += int(minutes.group(1)) / 60
        return timedelta(hours=total) if any([days, hours, minutes]) else None

    def _parse_public_surplus_datetime(self, value: str) -> str | None:
        parsed = self._parse_datetime_with_zone(value)
        return parsed.isoformat() if parsed else None

    def _extract_secondary_signals(self, raw: RawHardwareListing, captured_at: datetime) -> dict:
        text = f"{raw.original_title} {raw.original_description or ''}"
        signals = self._extract_end_time_signals(text, captured_at)
        if signals.get("end_time_utc"):
            signals["end_time_verification"] = AuctionEndVerificationLevel.SECONDARY_SOURCE_CONFIRMED.value
        return signals

    def _extract_end_time_signals(self, text: str, captured_at: datetime) -> dict:
        lower = text.lower()
        payload: dict = {}
        if re.search(r"\b(?:status\s*:?\s*sold|sold\s+for|item\s+sold|auction\s+sold)\b", lower):
            payload["listing_status"] = ListingStatus.SOLD.value
        elif any(token in lower for token in ["no longer available", "removed", "not available"]):
            payload["listing_status"] = ListingStatus.REMOVED.value
        elif any(token in lower for token in ["auction ended", "auction closed", "bidding closed", "closed", "final price"]):
            payload["listing_status"] = ListingStatus.ENDED.value
        absolute = self._find_absolute_end_time(text)
        countdown = self._extract_countdown(text)
        if absolute:
            payload.update(self._absolute_end_time_payload(absolute, AuctionEndVerificationLevel.SOURCE_CONFIRMED))
        elif countdown:
            payload.update(self._countdown_payload(countdown, captured_at))
        if not payload.get("listing_status") and payload.get("end_time_utc"):
            payload.update(self._status_from_end_time(payload["end_time_utc"], captured_at))
        elif not payload.get("listing_status") and countdown:
            payload.update(self._status_from_countdown(payload.get("calculated_end_time"), captured_at))
        elif not payload.get("listing_status"):
            payload["listing_status"] = ListingStatus.UNKNOWN.value
            payload["end_time_verification"] = AuctionEndVerificationLevel.UNKNOWN.value
        return payload

    def _find_absolute_end_time(self, text: str) -> str | None:
        label_patterns = [
            r"(?:Auction ends?|Auction end time|Closing date|Closing time|Bidding closes|Sale ends?)\s*:?\s*([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s+[AP]M\s+[A-Z]{2,4})",
            r"(?:Auction ends?|Auction end time|Closing date|Closing time|Bidding closes|Sale ends?)\s*:?\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+[AP]M\s+[A-Z]{2,4})",
            r"\(([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s+[AP]M\s+[A-Z]{2,4})\)",
        ]
        for pattern in label_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(1).strip()
        return None

    def _extract_countdown(self, text: str) -> str | None:
        patterns = [
            r"(?:Time Left|Time remaining|Days remaining|Hours remaining|Ends in)\s*:?\s*((?:\d+\s*(?:days?|d)\s*)?(?:\d+\s*(?:hours?|hrs?|h)\s*)?(?:\d+\s*(?:minutes?|mins?|m)\s*)?)",
            r"(\d+\s*days?\s+\d+\s*hours?(?:\s+\d+\s*mins?)?\s*(?:remaining|left)?)",
            r"(\d+\s*hours?\s*(?:\d+\s*mins?)?\s*(?:remaining|left))",
            r"(Ends in\s+\d+\s*(?:minutes?|hours?|days?))",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                value = (match.group(1) or "").strip()
                if self._duration_from_countdown(value):
                    return value
        return None

    def _absolute_end_time_payload(self, raw_value: str, verification: AuctionEndVerificationLevel) -> dict:
        parsed = self._parse_datetime_with_zone(raw_value)
        timezone_raw = self._extract_timezone(raw_value)
        payload = {
            "end_time_raw": raw_value,
            "end_time_timezone_raw": timezone_raw,
            "end_time_verification": verification.value,
            "timezone_needs_verification": timezone_raw is None,
        }
        if parsed:
            payload["end_time_utc"] = parsed.isoformat()
            payload["auction_end_time"] = parsed.isoformat()
        return payload

    def _countdown_payload(self, raw_value: str, captured_at: datetime) -> dict:
        duration = self._duration_from_countdown(raw_value)
        payload = {
            "countdown_raw_text": raw_value,
            "countdown_captured_at": captured_at.isoformat(),
            "calculated_timezone": "captured_at_utc",
            "calculation_confidence": "medium",
            "end_time_verification": AuctionEndVerificationLevel.COUNTDOWN_ESTIMATED.value,
            "time_remaining": raw_value,
        }
        if duration:
            calculated = captured_at + duration
            payload["calculated_end_time"] = calculated.isoformat()
            payload["end_time_utc"] = calculated.isoformat()
            payload["auction_end_time"] = calculated.isoformat()
            payload.update(self._status_from_countdown(calculated.isoformat(), captured_at))
        return payload

    def _finalize_status(self, detail: dict, captured_at: datetime) -> dict:
        status = detail.get("listing_status")
        if detail.get("end_time_utc"):
            computed = self._status_from_end_time(detail["end_time_utc"], captured_at)
            if status in {ListingStatus.ACTIVE.value, ListingStatus.ENDING_SOON.value} and computed["listing_status"] == ListingStatus.ENDED.value:
                return {"listing_status": ListingStatus.ENDED.value, "end_time_verification": AuctionEndVerificationLevel.CONFLICTING.value, "status_check_result": "active_text_but_end_time_elapsed"}
            if status in {None, ListingStatus.UNKNOWN.value}:
                return computed
        if status == ListingStatus.UNKNOWN.value and detail.get("unavailable_reason"):
            return {"listing_status": ListingStatus.NEEDS_MANUAL_REVIEW.value, "needs_manual_review": True}
        return {}

    def _status_from_countdown(self, end_time_value, captured_at: datetime) -> dict:
        return self._status_from_end_time(end_time_value, captured_at)

    def _status_from_end_time(self, end_time_value, now: datetime) -> dict:
        parsed = self._parse_iso_datetime(end_time_value)
        if not parsed:
            return {"listing_status": ListingStatus.UNKNOWN.value}
        if parsed <= now:
            return {"listing_status": ListingStatus.ENDED.value}
        if parsed - now <= timedelta(hours=24):
            return {"listing_status": ListingStatus.ENDING_SOON.value}
        return {"listing_status": ListingStatus.ACTIVE.value}

    def _parse_datetime_with_zone(self, value: str) -> datetime | None:
        match = re.match(r"(.+)\s+([A-Z]{2,4})$", value)
        if not match:
            return None
        timestamp, zone = match.groups()
        formats = ["%b %d, %Y %I:%M %p", "%B %d, %Y %I:%M %p", "%m/%d/%Y %I:%M %p"]
        parsed = None
        for fmt in formats:
            try:
                parsed = datetime.strptime(timestamp.strip(), fmt)
                break
            except ValueError:
                continue
        if not parsed:
            return None
        tzinfo = TZ_OFFSETS.get(zone)
        if not tzinfo:
            return None
        return parsed.replace(tzinfo=tzinfo).astimezone(timezone.utc)

    def _extract_timezone(self, value: str) -> str | None:
        match = re.search(r"\b([A-Z]{2,4})$", value.strip())
        return match.group(1) if match and match.group(1) in TZ_OFFSETS else None

    def _parse_iso_datetime(self, value) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    def _structured_text_fragments(self, soup: BeautifulSoup) -> list[str]:
        fragments: list[str] = []
        for script in soup.select('script[type="application/ld+json"]'):
            raw = script.string or script.get_text(" ", strip=True)
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
                fragments.append(json.dumps(parsed))
            except Exception:
                fragments.append(raw[:2000])
        for script in soup.select("script"):
            raw = script.string or ""
            if any(token in raw.lower() for token in ["auction", "closing", "endtime", "end_time", "timeleft", "time remaining"]):
                fragments.append(raw[:4000])
        return fragments
