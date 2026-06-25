from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.hardware_daily.models import (
    ConfidenceLevel,
    HardwareCategory,
    HardwareCondition,
    HardwareOpportunity,
    OpportunityStatus,
    RawHardwareListing,
)


class HardwareListingNormalizer:
    def normalize(self, raw: RawHardwareListing) -> HardwareOpportunity:
        text = f"{raw.original_title} {raw.original_description or ''}"
        lower = text.lower()
        manufacturer, model = self._extract_manufacturer_model(text, raw.category)
        total_price = self._extract_price(text)
        quantity = self._extract_quantity(text)
        location_state = self._extract_state(text)
        condition = self._extract_condition(lower)
        seller_name = raw.seller_name or self._seller_from_url(raw.source_url)
        source_listing_id = raw.source_listing_id or self._listing_id_from_url(raw.source_url)
        confidence = self._confidence(raw.source_name, raw.raw_data.get("domain"))
        risk_flags = self._risk_flags(lower, raw.source_url)
        canonical_url = self.canonical_url(raw.source_url)
        return HardwareOpportunity(
            category=raw.category,
            subcategory=self._subcategory(raw.category, lower),
            title=raw.original_title,
            manufacturer=manufacturer,
            model=model,
            part_number=self._extract_part_number(text),
            generation=self._extract_generation(text),
            configuration=self._extract_configuration(text),
            quantity=quantity,
            quantity_status="known" if quantity is not None else "unknown",
            unit_price=round(total_price / quantity, 2) if total_price and quantity and quantity > 0 else None,
            total_price=total_price,
            condition=condition,
            working_status=self._working_status(lower),
            testing_status=self._testing_status(lower),
            warranty_status="unknown",
            location_state=location_state,
            pickup_only="pickup only" in lower or "local pickup" in lower,
            shipping_available=None if "shipping" not in lower else "no shipping" not in lower,
            seller_name=seller_name,
            seller_type=self._seller_type(lower, raw.source_name),
            source=raw.source_name,
            source_url=raw.source_url,
            canonical_url=canonical_url,
            source_listing_id=source_listing_id,
            page_type=raw.page_type,
            classification_reason=raw.classification_reason,
            status=OpportunityStatus.ACTIVE if "ended" not in lower and "sold" not in lower else OpportunityStatus.ENDED,
            confidence_level=confidence,
            risk_flags=risk_flags,
            raw_title=raw.original_title,
            raw_description=raw.original_description,
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
