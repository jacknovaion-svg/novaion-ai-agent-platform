from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from app.hardware_daily.models import HardwareCategory, HardwareResultPageType, RawHardwareListing, utc_now


class GovDealsVisibleTextParser:
    def parse(self, source_url: str, visible_text: str, category: HardwareCategory) -> RawHardwareListing:
        lines = [line.strip() for line in visible_text.splitlines() if line.strip()]
        title = self._title(lines)
        lot_number = self._value_after_label(lines, "LOT#") or self._tab_value(lines, "Lot Number")
        current_price = self._current_price(lines)
        end_time_raw = self._close_time(lines)
        end_time_utc = self._parse_close_time(end_time_raw)
        location_text = self._value_after_label(lines, "Location:")
        city, state = self._parse_location(location_text)
        quantity = self._quantity(visible_text)
        description = self._description(lines)
        listing_status = self._listing_status(end_time_utc, visible_text)
        detail = {
            "source_listing_id": lot_number,
            "lot_number": lot_number,
            "title": title,
            "description": description,
            "current_price": current_price,
            "total_price": current_price,
            "quantity": quantity,
            "auction_end_time": end_time_utc.isoformat() if end_time_utc else None,
            "end_time_utc": end_time_utc.isoformat() if end_time_utc else None,
            "end_time_raw": end_time_raw,
            "end_time_timezone_raw": self._timezone_from_raw(end_time_raw),
            "end_time_verification": "source_confirmed" if end_time_utc else "unknown",
            "location_city": city,
            "location_state": state,
            "location_text": location_text,
            "condition": self._tab_value(lines, "Condition"),
            "listing_status": listing_status,
            "listing_status_reason": "GovDeals browser-visible page text parsed",
            "pickup_only": "buyer must arrange" in visible_text.lower(),
            "shipping_available": None,
            "needs_manual_review": False if end_time_utc and title and lot_number else True,
        }
        return RawHardwareListing(
            source_name="GovDeals",
            source_url=source_url,
            original_title=title,
            original_description=description,
            category=category,
            source_listing_id=lot_number,
            page_type=HardwareResultPageType.SPECIFIC_LISTING,
            classification_reason="GovDeals browser-visible asset page parsed as a specific listing.",
            raw_data={
                "adapter_type": "govdeals_browser_visible_text",
                "source_access_mode": "browser_assisted",
                "source_access_status": "browser_visible",
                "matched_keywords": self._matched_keywords(visible_text),
                "detail": detail,
                "visible_text_excerpt": visible_text[:5000],
            },
            fetched_at=utc_now(),
        )

    def _title(self, lines: list[str]) -> str:
        for index, line in enumerate(lines):
            if line.startswith("LOT#") and index + 1 < len(lines):
                for candidate in lines[index + 1 : index + 6]:
                    if candidate and not re.search(r"^\d+\s*/\s*\d+$", candidate) and not candidate.startswith("$"):
                        return candidate
        for line in lines:
            if any(token in line.lower() for token in ["server", "poweredge", "supermicro", "proliant"]):
                return line
        return "GovDeals browser-imported listing"

    def _value_after_label(self, lines: list[str], label: str) -> str | None:
        for index, line in enumerate(lines):
            if line == label and index + 1 < len(lines):
                return lines[index + 1]
            if line.startswith(label) and line != label:
                value = line.removeprefix(label).strip()
                if value:
                    return value
        return None

    def _tab_value(self, lines: list[str], label: str) -> str | None:
        prefix = f"{label}\t"
        for line in lines:
            if line.startswith(prefix):
                return line[len(prefix) :].strip()
        return None

    def _current_price(self, lines: list[str]) -> float | None:
        for index, line in enumerate(lines):
            if line.startswith("LOT#"):
                window = lines[index : index + 10]
                for candidate in window:
                    match = re.search(r"\$([0-9][0-9,]*(?:\.\d{2})?)\s+USD", candidate)
                    if match:
                        return float(match.group(1).replace(",", ""))
        for line in lines:
            match = re.search(r"\$([0-9][0-9,]*(?:\.\d{2})?)\s+USD", line)
            if match:
                return float(match.group(1).replace(",", ""))
        return None

    def _close_time(self, lines: list[str]) -> str | None:
        for index, line in enumerate(lines):
            if line.lower().startswith("closes") and index + 1 < len(lines):
                next_line = lines[index + 1]
                match = re.search(r"\(([^)]+)\)", next_line)
                return match.group(1).strip() if match else next_line
        return None

    def _parse_close_time(self, raw: str | None) -> datetime | None:
        if not raw:
            return None
        timezone_name = self._timezone_from_raw(raw)
        cleaned = raw.replace(" PDT", "").replace(" PST", "").strip()
        for fmt in ["%b %d, %Y %I:%M %p", "%B %d, %Y %I:%M %p"]:
            try:
                parsed = datetime.strptime(cleaned, fmt)
                return parsed.replace(tzinfo=ZoneInfo(timezone_name)).astimezone(ZoneInfo("UTC"))
            except ValueError:
                continue
        return None

    def _timezone_from_raw(self, raw: str | None) -> str:
        if not raw:
            return "America/Los_Angeles"
        if raw.endswith("PDT") or raw.endswith("PST"):
            return "America/Los_Angeles"
        if raw.endswith("CDT") or raw.endswith("CST"):
            return "America/Chicago"
        if raw.endswith("EDT") or raw.endswith("EST"):
            return "America/New_York"
        if raw.endswith("MDT") or raw.endswith("MST"):
            return "America/Denver"
        return "America/Los_Angeles"

    def _parse_location(self, location: str | None) -> tuple[str | None, str | None]:
        if not location:
            return None, None
        parts = [part.strip() for part in location.split(",")]
        city = parts[0] if parts else None
        state_name = parts[1] if len(parts) > 1 else None
        state = {
            "Texas": "TX",
            "California": "CA",
            "Oregon": "OR",
            "Georgia": "GA",
            "North Carolina": "NC",
            "Oklahoma": "OK",
        }.get(state_name or "", state_name)
        return city, state

    def _quantity(self, text: str) -> int | None:
        patterns = [
            r"\blot of\s+(\d{1,5})\s+Enterprise Servers\b",
            r"\blot of\s+(\d{1,5})\s+servers\b",
            r"\b(\d{1,5})\s+Enterprise Servers\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return int(match.group(1))
        return None

    def _description(self, lines: list[str]) -> str:
        start = next((index for index, line in enumerate(lines) if line == "Description"), 0)
        end = next((index for index, line in enumerate(lines[start + 1 :], start + 1) if line == "Inspection"), min(len(lines), start + 40))
        return "\n".join(lines[start:end])[:3000]

    def _listing_status(self, end_time_utc: datetime | None, text: str) -> str:
        lower = text.lower()
        if "auction closed" in lower or "auction ended" in lower:
            return "ended"
        if not end_time_utc:
            return "unknown"
        now = utc_now()
        if end_time_utc <= now:
            return "ended"
        if (end_time_utc - now).total_seconds() <= 24 * 60 * 60:
            return "ending_soon"
        return "active"

    def _matched_keywords(self, text: str) -> list[str]:
        keywords = []
        for keyword in ["server", "servers", "supermicro", "hpe", "quanta", "ddr4", "ddr3"]:
            if keyword in text.lower():
                keywords.append(keyword)
        return keywords
