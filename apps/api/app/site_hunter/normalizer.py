from __future__ import annotations

import re

from app.site_hunter.models import NormalizedSiteListing, RawPropertyResult, TrustLevel


STATE_PATTERN = (
    r"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|"
    r"Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|"
    r"Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|"
    r"New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|"
    r"Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|"
    r"West Virginia|Wisconsin|Wyoming|Washington, D.C."
)


class PropertyNormalizer:
    def normalize(self, raw: RawPropertyResult) -> NormalizedSiteListing:
        text = f"{raw.original_title} {raw.original_description or ''}"
        listing = NormalizedSiteListing(
            site_name=raw.original_title,
            translated_title_zh=self._title_zh(raw.original_title),
            translated_summary_zh=self._summary_zh(raw),
            source_name=raw.source_name,
            source_type=raw.source_type,
            source_url=raw.source_url,
            original_title=raw.original_title,
            original_description=raw.original_description,
            property_type=self._property_type(text),
            land_acres=self._land_acres(text),
            building_sqft=self._building_sqft(text),
            asking_price_usd=self._price(text),
            city=self._city(text),
            state=self._state(text),
            zip_code=self._zip(text),
            source_confidence=TrustLevel.UNVERIFIED,
            raw_data_json=raw.raw_data,
        )
        listing.missing_fields = self._missing_fields(listing)
        listing.field_confidence = {
            "title": TrustLevel.SOURCE_CONFIRMED,
            "source_url": TrustLevel.SOURCE_CONFIRMED,
            "land_acres": TrustLevel.SOURCE_CONFIRMED if listing.land_acres else TrustLevel.UNKNOWN,
            "asking_price_usd": TrustLevel.SOURCE_CONFIRMED if listing.asking_price_usd else TrustLevel.UNKNOWN,
            "address": TrustLevel.UNKNOWN,
            "zoning": TrustLevel.UNKNOWN,
        }
        listing.warnings.append("Utility capacity is not assessed in Site Hunter V1 phase 1.")
        return listing

    def dedupe(self, listings: list[NormalizedSiteListing]) -> list[NormalizedSiteListing]:
        seen: set[str] = set()
        output: list[NormalizedSiteListing] = []
        for listing in listings:
            key = (listing.source_url or listing.site_name).strip().lower()
            if key in seen:
                continue
            seen.add(key)
            output.append(listing)
        return output

    def _title_zh(self, title: str) -> str:
        return f"工业地产候选：{title[:90]}"

    def _summary_zh(self, raw: RawPropertyResult) -> str:
        desc = raw.original_description or "来源页面未提供摘要。"
        return f"来源 {raw.source_name} 发现的真实网页候选。英文摘要：{desc[:220]}"

    def _property_type(self, text: str) -> str | None:
        lowered = text.lower()
        if "manufacturing" in lowered or "factory" in lowered:
            return "manufacturing facility"
        if "warehouse" in lowered:
            return "warehouse"
        if "industrial land" in lowered or "acre" in lowered:
            return "industrial land"
        if "industrial" in lowered:
            return "industrial property"
        return None

    def _land_acres(self, text: str) -> float | None:
        match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:\+|-)?\s*ac(?:res?)?\b", text, re.IGNORECASE)
        return float(match.group(1).replace(",", "")) if match else None

    def _building_sqft(self, text: str) -> float | None:
        match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:sf|sq\.?\s*ft|sqft|square feet)\b", text, re.IGNORECASE)
        return float(match.group(1).replace(",", "")) if match else None

    def _price(self, text: str) -> float | None:
        match = re.search(r"\$\s*(\d+(?:,\d{3})+(?:\.\d+)?)", text)
        if match:
            return float(match.group(1).replace(",", ""))
        million = re.search(r"\$\s*(\d+(?:\.\d+)?)\s*(?:M|million)", text, re.IGNORECASE)
        return float(million.group(1)) * 1_000_000 if million else None

    def _state(self, text: str) -> str | None:
        match = re.search(rf"\b({STATE_PATTERN})\b", text, re.IGNORECASE)
        return match.group(1) if match else None

    def _city(self, text: str) -> str | None:
        match = re.search(r"\b([A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+)?)\s*,\s*(" + STATE_PATTERN + r")\b", text)
        return match.group(1) if match else None

    def _zip(self, text: str) -> str | None:
        match = re.search(r"\b\d{5}(?:-\d{4})?\b", text)
        return match.group(0) if match else None

    def _missing_fields(self, listing: NormalizedSiteListing) -> list[str]:
        fields = {
            "address": listing.address_line_1,
            "land_acres": listing.land_acres,
            "building_sqft": listing.building_sqft,
            "asking_price_usd": listing.asking_price_usd,
            "zoning": listing.zoning,
        }
        return [field for field, value in fields.items() if value is None]
