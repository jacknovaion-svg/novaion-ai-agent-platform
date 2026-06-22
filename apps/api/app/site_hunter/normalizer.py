from __future__ import annotations

import re

from app.site_hunter.models import AddressStatus, NormalizedSiteListing, PriceStatus, RawPropertyResult, TrustLevel


STATE_PATTERN = (
    r"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|"
    r"Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|"
    r"Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|"
    r"New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|"
    r"Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|"
    r"West Virginia|Wisconsin|Wyoming|Washington, D.C."
)

STATE_ABBREVIATIONS = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "Washington, D.C.",
}


class PropertyNormalizer:
    def normalize(self, raw: RawPropertyResult) -> NormalizedSiteListing:
        text = f"{raw.original_title} {raw.original_description or ''}"
        address = self._address(text)
        city_state_zip = self._city_state_zip(text)
        city, state, zip_code = city_state_zip
        city = self._city_after_address(text, address) or city
        state = state or raw.raw_data.get("state")
        price = self._price(text)
        price_status = self._price_status(text, price)
        listing = NormalizedSiteListing(
            site_name=raw.original_title,
            translated_title_zh=self._title_zh(raw.original_title),
            translated_summary_zh=self._summary_zh(raw),
            address_line_1=address,
            source_name=raw.source_name,
            source_type=raw.source_type,
            source_url=raw.source_url,
            original_title=raw.original_title,
            original_description=raw.original_description,
            property_type=self._property_type(text),
            land_acres=self._land_acres(text),
            building_sqft=self._building_sqft(text),
            asking_price_usd=price,
            city=city or self._city(text),
            state=state,
            zip_code=zip_code or self._zip(text),
            broker_company=self._broker_company(text),
            address_status=self._address_status(address, city, state),
            price_status=price_status,
            source_confidence=TrustLevel.UNVERIFIED,
            raw_data_json=raw.raw_data,
        )
        listing.data_completeness_score = self._data_completeness(listing)
        listing.missing_fields = self._missing_fields(listing)
        listing.field_confidence = {
            "title": TrustLevel.SOURCE_CONFIRMED,
            "source_url": TrustLevel.SOURCE_CONFIRMED,
            "land_acres": TrustLevel.SOURCE_CONFIRMED if listing.land_acres else TrustLevel.UNKNOWN,
            "asking_price_usd": TrustLevel.SOURCE_CONFIRMED if listing.asking_price_usd else TrustLevel.UNKNOWN,
            "address": TrustLevel.SOURCE_CONFIRMED if listing.address_line_1 else TrustLevel.UNKNOWN,
            "city": TrustLevel.SOURCE_CONFIRMED if listing.city else TrustLevel.UNKNOWN,
            "state": TrustLevel.SOURCE_CONFIRMED if listing.state else TrustLevel.UNKNOWN,
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

    def _price_status(self, text: str, price: float | None) -> PriceStatus:
        if price:
            return PriceStatus.ASKING_PRICE
        lowered = text.lower()
        if any(token in lowered for token in ["contact", "call for price", "undisclosed", "subject to offer", "request price"]):
            return PriceStatus.CONTACT_FOR_PRICE
        return PriceStatus.UNKNOWN

    def _state(self, text: str) -> str | None:
        match = re.search(rf"\b({STATE_PATTERN})\b", text, re.IGNORECASE)
        if match:
            return match.group(1)
        abbrev = re.search(r"\b(" + "|".join(STATE_ABBREVIATIONS) + r"),?\s+\d{5}(?:-\d{4})?\b", text)
        return STATE_ABBREVIATIONS.get(abbrev.group(1)) if abbrev else None

    def _city(self, text: str) -> str | None:
        match = re.search(r"\b([A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+)?)\s*,\s*(" + STATE_PATTERN + r")\b", text)
        return match.group(1) if match else None

    def _city_state_zip(self, text: str) -> tuple[str | None, str | None, str | None]:
        match = re.search(
            r"\b([A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+)?)\s*,?\s+("
            + "|".join(STATE_ABBREVIATIONS)
            + r"),?\s+(\d{5}(?:-\d{4})?)\b",
            text,
        )
        if not match:
            return None, None, None
        return self._clean_city(match.group(1)), STATE_ABBREVIATIONS.get(match.group(2)), match.group(3)

    def _address(self, text: str) -> str | None:
        county_road = re.search(r"\b(\d{1,6}\s+County\s+Road\s+\d+[A-Za-z]?)\b", text, re.IGNORECASE)
        if county_road:
            return county_road.group(1).strip()
        highway = re.search(
            r"(?<![\d,])\b(\d{1,6}\s+(?:[NSEW]\s+)?(?:US\s+Hwy|U\.S\.\s+Hwy|Hwy|Highway|IH|Interstate|FM)\s*-?\s*\d+[A-Za-z]?)\b",
            text,
            re.IGNORECASE,
        )
        if highway:
            return highway.group(1).strip()
        match = re.search(
            r"(?<![\d,])\b(\d{1,6}\s+(?:[A-Za-z0-9.'-]+\s+){0,6}(?:Road|Rd|Street|St|Avenue|Ave|Boulevard|Blvd|Highway|Hwy|Drive|Dr|Lane|Ln|Parkway|Pkwy|Way|Court|Ct)\b)",
            text,
            re.IGNORECASE,
        )
        return match.group(1).strip() if match else None

    def _city_after_address(self, text: str, address: str | None) -> str | None:
        if not address:
            return None
        match = re.search(
            re.escape(address) + r"\s+([A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+){0,2}),?\s+("
            + "|".join(STATE_ABBREVIATIONS)
            + r")\b",
            text,
        )
        return self._clean_city(match.group(1)) if match else None

    def _clean_city(self, city: str) -> str:
        road_words = {"road", "rd", "street", "st", "avenue", "ave", "drive", "dr", "parkway", "pkwy", "hwy", "highway", "way"}
        parts = city.split()
        while len(parts) > 1 and parts[0].lower().strip(".") in road_words:
            parts = parts[1:]
        return " ".join(parts)

    def _address_status(self, address: str | None, city: str | None, state: str | None) -> AddressStatus:
        if address and city and state:
            return AddressStatus.FULL
        if city or state or address:
            return AddressStatus.PARTIAL
        return AddressStatus.UNKNOWN

    def _broker_company(self, text: str) -> str | None:
        match = re.search(r"(?:Courtesy Of|Listed By)\s+([^|\\n]+?)(?:Contact|Add to Compare|$)", text, re.IGNORECASE)
        return match.group(1).strip()[:120] if match else None

    def _data_completeness(self, listing: NormalizedSiteListing) -> float:
        fields = [
            listing.source_url,
            listing.original_title,
            listing.state,
            listing.city,
            listing.address_line_1,
            listing.land_acres,
            listing.building_sqft,
            listing.asking_price_usd or listing.price_status == PriceStatus.CONTACT_FOR_PRICE,
            listing.property_type,
            listing.broker_company,
        ]
        return round(sum(1 for field in fields if field) / len(fields), 2)

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
