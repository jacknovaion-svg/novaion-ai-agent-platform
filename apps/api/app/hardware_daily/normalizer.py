from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.hardware_daily.models import (
    ConfidenceLevel,
    ComponentCompleteness,
    HardwareCategory,
    HardwareCondition,
    HardwareOpportunity,
    ListingStatus,
    OpportunityRecommendation,
    OpportunityStatus,
    RawHardwareListing,
    utc_now,
)


class HardwareListingNormalizer:
    def normalize(self, raw: RawHardwareListing) -> HardwareOpportunity:
        detail = raw.raw_data.get("detail") or {}
        title = str(detail.get("title") or raw.original_title)
        description = detail.get("description") or raw.original_description
        text = f"{title} {description or ''}"
        lower = text.lower()
        manufacturer, model = self._extract_manufacturer_model(text, raw.category)
        total_price = self._float_or_none(detail.get("total_price")) or self._extract_price(text)
        current_price = self._float_or_none(detail.get("current_price")) or total_price
        quantity = self._int_or_none(detail.get("quantity")) or self._extract_quantity(text)
        location_state = detail.get("location_state") or self._extract_state(text)
        condition = self._extract_condition(lower)
        seller_name = detail.get("seller_name") or raw.seller_name or self._seller_from_url(raw.source_url)
        source_listing_id = detail.get("source_listing_id") or raw.source_listing_id or self._listing_id_from_url(raw.source_url)
        confidence = self._confidence(raw.source_name, raw.raw_data.get("domain"))
        risk_flags = self._risk_flags(lower, raw.source_url)
        if detail.get("needs_manual_review"):
            risk_flags.append("needs_manual_review")
        buyer_premium = self._buyer_premium(text, detail)
        if buyer_premium and "buyer_premium" not in risk_flags:
            risk_flags.append("buyer_premium")
        canonical_url = self.canonical_url(raw.source_url)
        listing_status = self._listing_status(detail, lower)
        component_completeness = self._component_completeness(lower, risk_flags)
        component_details = self._component_details(text, raw.category, quantity)
        cost_fields = self._cost_fields(total_price=total_price, current_price=current_price, quantity=quantity, category=raw.category, component_details=component_details)
        status = self._opportunity_status(listing_status)
        return HardwareOpportunity(
            category=raw.category,
            subcategory=self._subcategory(raw.category, lower),
            title=title,
            manufacturer=manufacturer,
            model=model,
            part_number=self._extract_part_number(text),
            lot_number=detail.get("lot_number"),
            generation=self._extract_generation(text),
            configuration=self._extract_configuration(text),
            quantity=quantity,
            quantity_status="known" if quantity is not None else "unknown",
            unit_price=cost_fields["unit_price"],
            total_price=total_price,
            current_price=current_price,
            current_total_cost=cost_fields["current_total_cost"],
            buyer_premium=buyer_premium,
            buyer_premium_amount=None,
            estimated_landed_cost=cost_fields["estimated_landed_cost"],
            cost_per_unit=cost_fields["cost_per_unit"],
            cost_per_gb=cost_fields["cost_per_gb"],
            cost_confidence=cost_fields["cost_confidence"],
            bid_count=self._int_or_none(detail.get("bid_count")),
            condition=condition,
            working_status=self._working_status(lower),
            testing_status=self._testing_status(lower),
            warranty_status="unknown",
            location_city=detail.get("location_city"),
            location_state=location_state,
            zip_code=detail.get("zip_code"),
            pickup_only=detail.get("pickup_only") if isinstance(detail.get("pickup_only"), bool) else ("pickup only" in lower or "local pickup" in lower),
            shipping_available=detail.get("shipping_available") if isinstance(detail.get("shipping_available"), bool) else (None if "shipping" not in lower else "no shipping" not in lower),
            auction_end_time=self._datetime_or_none(detail.get("auction_end_time")),
            seller_name=seller_name,
            seller_type=self._seller_type(lower, raw.source_name),
            source=raw.source_name,
            source_url=raw.source_url,
            canonical_url=canonical_url,
            source_listing_id=source_listing_id,
            page_type=raw.page_type,
            classification_reason=raw.classification_reason,
            status=status,
            listing_status=listing_status,
            time_remaining=detail.get("time_remaining"),
            component_completeness=component_completeness,
            component_details=component_details,
            recommendation=OpportunityRecommendation.INFORMATION_INCOMPLETE,
            last_checked_at=raw.detail_checked_at or utc_now(),
            unavailable_reason=detail.get("unavailable_reason"),
            needs_manual_review=bool(detail.get("needs_manual_review") or listing_status == ListingStatus.UNKNOWN),
            confidence_level=confidence,
            risk_flags=list(dict.fromkeys(risk_flags)),
            raw_title=raw.original_title,
            raw_description=description,
            raw_data_json=raw.raw_data,
        )

    def opportunity_key(self, opportunity: HardwareOpportunity) -> str:
        canonical_url = opportunity.canonical_url or self.canonical_url(opportunity.source_url)
        parsed = urlparse(canonical_url)
        canonical = f"{parsed.netloc.lower().removeprefix('www.')}{parsed.path.rstrip('/')}"
        if parsed.query:
            canonical = f"{canonical}?{parsed.query}"
        if canonical:
            return canonical
        parts = [opportunity.seller_name or "", opportunity.title, opportunity.model or "", opportunity.location_state or ""]
        return "|".join(part.lower().strip() for part in parts if part)

    def canonical_url(self, url: str) -> str:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)
        keep_params: dict[str, str] = {}
        for param in ["auc", "auction", "lot", "item", "asset", "id", "hash"]:
            if query.get(param):
                keep_params[param] = query[param][0]
        if "ebay.com" in domain and "/itm/" in path:
            match = re.search(r"/itm/(?:[^/]+/)?(\d{10,})", path)
            if match:
                path = f"/itm/{match.group(1)}"
        normalized_query = urlencode(keep_params)
        return urlunparse((parsed.scheme or "https", domain, path or "/", "", normalized_query, ""))

    def _extract_manufacturer_model(self, text: str, category: HardwareCategory) -> tuple[str | None, str | None]:
        patterns = [
            (r"\b(Dell)\s+(PowerEdge\s+[A-Z0-9-]+)", "Dell"),
            (r"\b(HPE|HP)\s+(ProLiant\s+[A-Z0-9-]+)", "HPE"),
            (r"\b(Supermicro)\s+([A-Z0-9-]+)", "Supermicro"),
            (r"\b(NVIDIA)\s+((?:A|H|L|RTX)\s?\d{3,4}\w*)", "NVIDIA"),
            (r"\b(AMD)\s+(EPYC\s+\d{4}\w*)", "AMD"),
            (r"\b(Intel)\s+(Xeon\s+[A-Za-z0-9 -]+)", "Intel"),
            (r"\b(Samsung|Micron|SK Hynix|Kingston)\s+([A-Za-z0-9 -]*(?:RDIMM|SSD|NVMe)[A-Za-z0-9 -]*)", None),
        ]
        for pattern, fallback in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return (fallback or match.group(1).strip(), re.sub(r"\s+", " ", match.group(2)).strip())
        if category == HardwareCategory.MEMORY:
            match = re.search(r"\b(DDR[45]\s+ECC\s+RDIMM)\b", text, flags=re.I)
            if match:
                return None, match.group(1).upper()
        if category == HardwareCategory.STORAGE:
            match = re.search(r"\b(\d+(?:\.\d+)?\s?TB\s+(?:Enterprise\s+)?(?:SSD|NVMe|HDD))\b", text, flags=re.I)
            if match:
                return None, match.group(1)
        return None, None

    def _extract_price(self, text: str) -> float | None:
        matches = re.findall(r"\$\s?([0-9][0-9,]*(?:\.\d{2})?)", text)
        if not matches:
            return None
        try:
            return float(matches[0].replace(",", ""))
        except ValueError:
            return None

    def _extract_quantity(self, text: str) -> int | None:
        patterns = [r"\b(?:lot of|qty\.?|quantity)\s*:?\s*(\d{1,5})\b", r"\b(\d{1,5})\s?x\b", r"\b(\d{1,5})\s+(?:servers|gpus|ssds|drives|cpus|modules)\b"]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return int(match.group(1))
        return None

    def _float_or_none(self, value) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).replace("$", "").replace(",", "").strip())
        except ValueError:
            return None

    def _int_or_none(self, value) -> int | None:
        if value is None:
            return None

    def _datetime_or_none(self, value) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        try:
            return int(str(value).replace(",", "").strip())
        except ValueError:
            return None

    def _listing_status(self, detail: dict, lower: str) -> ListingStatus:
        raw_status = detail.get("listing_status")
        if raw_status:
            try:
                return ListingStatus(raw_status)
            except ValueError:
                pass
        if any(token in lower for token in ["auction ended", "final price", "sold", "closed", "removed"]):
            return ListingStatus.ENDED
        if any(token in lower for token in ["current bid", "buy it now", "time left"]):
            return ListingStatus.ACTIVE
        return ListingStatus.UNKNOWN

    def _opportunity_status(self, listing_status: ListingStatus) -> OpportunityStatus:
        if listing_status == ListingStatus.SOLD:
            return OpportunityStatus.SOLD
        if listing_status in {ListingStatus.ENDED, ListingStatus.REMOVED, ListingStatus.UNAVAILABLE}:
            return OpportunityStatus.ENDED
        if listing_status in {ListingStatus.ACTIVE, ListingStatus.ENDING_SOON}:
            return OpportunityStatus.ACTIVE
        return OpportunityStatus.NEEDS_VERIFICATION

    def _buyer_premium(self, text: str, detail: dict) -> str | None:
        if detail.get("buyer_premium"):
            return str(detail["buyer_premium"])
        match = re.search(r"buyer'?s?\s+premium\s*:?\s*(\d{1,2}(?:\.\d+)?)\s?%", text, re.I)
        return f"{match.group(1)}%" if match else None

    def _cost_fields(
        self,
        *,
        total_price: float | None,
        current_price: float | None,
        quantity: int | None,
        category: HardwareCategory,
        component_details: dict,
    ) -> dict[str, float | str | None]:
        total = total_price or current_price
        unit = round(total / quantity, 2) if total and quantity and quantity > 0 else None
        cost_per_gb = None
        if category == HardwareCategory.MEMORY and total and quantity:
            capacity = component_details.get("capacity_gb")
            if isinstance(capacity, (int, float)) and capacity > 0:
                cost_per_gb = round(total / (capacity * quantity), 4)
        return {
            "current_total_cost": total,
            "estimated_landed_cost": None,
            "unit_price": unit,
            "cost_per_unit": unit,
            "cost_per_gb": cost_per_gb,
            "cost_confidence": "high" if total and quantity else "medium" if total else "unknown",
        }

    def _extract_state(self, text: str) -> str | None:
        states = {
            "Texas": "TX",
            "California": "CA",
            "Georgia": "GA",
            "Arizona": "AZ",
            "Nevada": "NV",
            "Virginia": "VA",
            "Florida": "FL",
            "Illinois": "IL",
            "Ohio": "OH",
            "New York": "NY",
        }
        for name, code in states.items():
            if re.search(rf"\b{name}\b|\b{code}\b", text, flags=re.I):
                return code
        return None

    def _extract_condition(self, lower: str) -> HardwareCondition:
        if "parts only" in lower or "for parts" in lower:
            return HardwareCondition.PARTS_ONLY
        if "untested" in lower:
            return HardwareCondition.UNTESTED
        if "refurb" in lower:
            return HardwareCondition.REFURBISHED
        if "tested" in lower:
            return HardwareCondition.TESTED
        if "salvage" in lower:
            return HardwareCondition.SALVAGE
        if "broken" in lower:
            return HardwareCondition.BROKEN
        if "open box" in lower:
            return HardwareCondition.OPEN_BOX
        if "new" in lower:
            return HardwareCondition.NEW
        if "used" in lower:
            return HardwareCondition.USED_WORKING
        return HardwareCondition.UNKNOWN

    def _working_status(self, lower: str) -> str:
        if "working" in lower or "pulled from working" in lower:
            return "claimed_working"
        if "not working" in lower or "broken" in lower:
            return "not_working"
        return "unknown"

    def _testing_status(self, lower: str) -> str:
        if "tested" in lower and "untested" not in lower:
            return "tested"
        if "untested" in lower:
            return "untested"
        return "unknown"

    def _seller_type(self, lower: str, source_name: str) -> str:
        if "gov" in source_name.lower() or "public surplus" in source_name.lower():
            return "government_surplus"
        if "auction" in lower or "auction" in source_name.lower():
            return "auctioneer"
        if "itad" in lower or "asset disposition" in lower:
            return "itad_supplier"
        return "unknown"

    def _confidence(self, source_name: str, domain: str | None) -> ConfidenceLevel:
        official_domains = ["govdeals.com", "publicsurplus.com", "ebay.com", "hgpauction.com"]
        if domain in official_domains:
            return ConfidenceLevel.MARKETPLACE_LISTING
        if source_name in {"GovDeals", "Public Surplus", "eBay", "HGP Industrial Auctions"}:
            return ConfidenceLevel.PUBLIC_SEARCH_DISCOVERY
        return ConfidenceLevel.NEEDS_VERIFICATION

    def _risk_flags(self, lower: str, url: str) -> list[str]:
        flags: list[str] = []
        if "untested" in lower:
            flags.append("untested")
        if "parts" in lower or "salvage" in lower:
            flags.append("parts_or_salvage")
        if "pickup only" in lower:
            flags.append("pickup_only")
        if "buyer premium" in lower or "buyers premium" in lower:
            flags.append("buyer_premium")
        if "bid" in lower or "auction" in lower:
            flags.append("auction_timing")
        if any(token in lower for token in ["no cpu", "missing cpu", "without cpu"]):
            flags.append("missing_cpu")
        if any(token in lower for token in ["no ram", "no memory", "missing memory", "without memory"]):
            flags.append("missing_memory")
        if any(token in lower for token in ["no hard drive", "no hdd", "no ssd", "drives removed", "without drives"]):
            flags.append("missing_storage")
        if any(token in lower for token in ["no power supply", "missing power supply", "without psu"]):
            flags.append("missing_power_supply")
        if url.startswith("manual://"):
            flags.append("manual_unverified")
        return flags

    def _component_completeness(self, lower: str, risk_flags: list[str]) -> ComponentCompleteness:
        if "barebone" in lower or "bare bone" in lower:
            return ComponentCompleteness.BAREBONE
        if "mixed lot" in lower or "pallet" in lower or "lot of assorted" in lower:
            return ComponentCompleteness.MIXED_LOT
        if "missing_cpu" in risk_flags:
            return ComponentCompleteness.MISSING_CPU
        if "missing_memory" in risk_flags:
            return ComponentCompleteness.MISSING_MEMORY
        if "missing_storage" in risk_flags:
            return ComponentCompleteness.MISSING_STORAGE
        if "missing_power_supply" in risk_flags:
            return ComponentCompleteness.MISSING_PSU
        if any(token in lower for token in ["complete system", "fully configured", "tested working"]):
            return ComponentCompleteness.COMPLETE
        if any(token in lower for token in ["server lot", "working pull", "used working"]):
            return ComponentCompleteness.MOSTLY_COMPLETE
        return ComponentCompleteness.UNKNOWN

    def _component_details(self, text: str, category: HardwareCategory, quantity: int | None) -> dict:
        lower = text.lower()
        details: dict = {"parsed_from": "title_description_rules"}
        if quantity:
            details["quantity"] = quantity
        if category == HardwareCategory.SERVERS:
            details.update(
                {
                    "cpu_model": self._first_match(text, r"\b(?:Intel\s+)?Xeon\s+[A-Za-z0-9 -]{3,24}"),
                    "cpu_count": self._int_from_match(text, r"\b(?:dual|2x|qty\s*2)\b") or self._int_from_match(text, r"\b(\d)\s*(?:CPU|processor)s?\b"),
                    "memory_total": self._first_match(text, r"\b\d{2,4}\s?GB\s+(?:RAM|Memory|DDR[45])\b"),
                    "storage_configuration": self._first_match(text, r"\b\d+(?:\.\d+)?\s?TB\s+(?:SAS|SATA|NVMe|SSD|HDD)[A-Za-z0-9 ,.-]*"),
                    "drives_included": not any(token in lower for token in ["no hard drive", "drives removed", "no drives"]),
                    "gpu_included": any(token in lower for token in ["gpu", "nvidia", "tesla", "a100", "h100"]),
                    "power_supplies": self._first_match(text, r"\b\d+\s*(?:PSU|power supplies|power supply)\b"),
                    "rails_included": "rails" in lower and "no rails" not in lower,
                }
            )
        elif category == HardwareCategory.GPU:
            details.update(
                {
                    "memory_capacity": self._first_match(text, r"\b\d{1,3}\s?GB\s+(?:GDDR|HBM)[A-Za-z0-9]*\b"),
                    "tested": "tested" in lower and "untested" not in lower,
                    "working": "working" in lower and "not working" not in lower,
                    "fault_type": self._first_match(text, r"\b(?:bad fan|artifacting|no display|dead|for parts)\b"),
                }
            )
        elif category == HardwareCategory.MEMORY:
            capacity = self._int_from_match(text, r"\b(\d{1,3})\s?GB\b")
            details.update(
                {
                    "capacity_gb": capacity,
                    "ddr_generation": self._first_match(text, r"\bDDR[45]\b"),
                    "speed_mts": self._int_from_match(text, r"\b(\d{4})\s?(?:MT/s|MHz)\b"),
                    "rdimm": "rdimm" in lower,
                    "lrdimm": "lrdimm" in lower,
                    "ecc": "ecc" in lower,
                }
            )
        elif category == HardwareCategory.STORAGE:
            details.update(
                {
                    "capacity_tb": self._float_capacity_tb(text),
                    "interface": self._first_match(text, r"\b(?:SAS|SATA|NVMe|U\.2|U\.3)\b"),
                    "form_factor": self._first_match(text, r"\b(?:2\.5\"|3\.5\"|M\.2|U\.2)\b"),
                    "tray_included": "tray" in lower and "no tray" not in lower,
                    "smart_available": "smart" in lower,
                    "data_wiped": "wiped" in lower or "sanitized" in lower,
                }
            )
        elif category == HardwareCategory.CPU:
            details.update(
                {
                    "family": self._first_match(text, r"\b(?:EPYC|Xeon)\b"),
                    "exact_model": self._first_match(text, r"\b(?:EPYC|Xeon)\s+[A-Za-z0-9 -]{3,24}"),
                    "socket": self._first_match(text, r"\b(?:SP3|SP5|LGA\s?\d{4})\b"),
                    "matched_pairs": "matched pair" in lower or "pair" in lower,
                    "tray_or_individual": "tray" if "tray" in lower else "individual",
                }
            )
        return {key: value for key, value in details.items() if value not in [None, ""]}

    def _first_match(self, text: str, pattern: str) -> str | None:
        match = re.search(pattern, text, flags=re.I)
        return re.sub(r"\s+", " ", match.group(0)).strip() if match else None

    def _int_from_match(self, text: str, pattern: str) -> int | None:
        match = re.search(pattern, text, flags=re.I)
        if not match:
            return None
        if match.groups():
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return 2

    def _float_capacity_tb(self, text: str) -> float | None:
        match = re.search(r"\b(\d+(?:\.\d+)?)\s?TB\b", text, flags=re.I)
        if match:
            return float(match.group(1))
        gb_match = re.search(r"\b(\d{3,5})\s?GB\b", text, flags=re.I)
        return round(float(gb_match.group(1)) / 1024, 3) if gb_match else None

    def _subcategory(self, category: HardwareCategory, lower: str) -> str | None:
        if category == HardwareCategory.GPU:
            if "h100" in lower:
                return "H100"
            if "a100" in lower:
                return "A100"
            if "rtx" in lower:
                return "RTX"
        if category == HardwareCategory.SERVERS:
            return "rack_server"
        if category == HardwareCategory.MEMORY:
            return "ecc_rdimm"
        if category == HardwareCategory.STORAGE:
            return "enterprise_storage"
        if category == HardwareCategory.CPU:
            return "server_cpu"
        return None

    def _extract_part_number(self, text: str) -> str | None:
        match = re.search(r"\b(?:P/N|Part(?: Number)?|MPN)[:#]?\s*([A-Z0-9-]{5,})", text, flags=re.I)
        return match.group(1).upper() if match else None

    def _extract_generation(self, text: str) -> str | None:
        match = re.search(r"\b(Gen(?:eration)?\s?\d{1,2}|14th Gen|15th Gen)\b", text, flags=re.I)
        return match.group(1) if match else None

    def _extract_configuration(self, text: str) -> str | None:
        specs = re.findall(r"\b(?:\d+\s?GB|\d+(?:\.\d+)?\s?TB|\d+\s?core|\d+\s?cores|DDR[45]|NVMe|SAS|SATA)\b", text, flags=re.I)
        return ", ".join(dict.fromkeys(specs[:8])) if specs else None

    def _seller_from_url(self, url: str) -> str | None:
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        return domain or None

    def _listing_id_from_url(self, url: str) -> str | None:
        path = urlparse(url).path.rstrip("/")
        if not path:
            return None
        return path.split("/")[-1][:80]
