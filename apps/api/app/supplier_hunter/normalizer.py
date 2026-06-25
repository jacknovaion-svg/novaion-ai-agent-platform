from __future__ import annotations

import re
from urllib.parse import urlparse

from app.supplier_hunter.models import RawSupplierResult, SupplierCategory, SupplierResult, VerificationStatus


STATE_PATTERN = r"Texas|TX"


class SupplierNormalizer:
    def normalize(self, raw: RawSupplierResult) -> SupplierResult:
        text = f"{raw.original_title} {raw.original_description or ''}"
        lowered = text.lower()
        company_name = self._company_name(raw)
        supplier = SupplierResult(
            company_name=company_name,
            company_type=self._company_type(lowered),
            website=self._website(raw.source_url),
            source_name=raw.source_name,
            source_url=raw.source_url,
            city=self._city(text),
            state=self._state(text, raw),
            zip_code=self._zip(text),
            phone=self._phone(text),
            email=self._email(text),
            service_area=self._service_area(text),
            data_center_decommissioning=any(token in lowered for token in ["data center decommission", "data centre decommission"]),
            enterprise_itad=any(token in lowered for token in ["itad", "it asset disposition", "enterprise it", "asset disposition"]),
            asset_remarketing=any(token in lowered for token in ["asset remarketing", "remarketing", "resale", "asset recovery"]),
            direct_asset_purchasing=any(token in lowered for token in ["equipment buyer", "we buy", "purchase", "direct asset purchasing", "buyback"]),
            server_recycling=any(token in lowered for token in ["server recycling", "server", "data center equipment"]),
            computer_refurbishing=any(token in lowered for token in ["refurbish", "refurbished", "computer refurbishing", "server refurbishment"]),
            bulk_sales=any(token in lowered for token in ["bulk", "liquidation", "pallet", "lots"]),
            wholesale=any(token in lowered for token in ["wholesale", "wholesaler"]),
            equipment_types=self._equipment_types(lowered),
            confidence_level=VerificationStatus.NEEDS_VERIFICATION,
            raw_data_json=raw.raw_data,
        )
        supplier.r2_certified = self._cert_status(lowered, raw.raw_data, "r2")
        supplier.e_stewards_certified = self._cert_status(lowered, raw.raw_data, "e-stewards")
        supplier.naid_aaa_certified = self._cert_status(lowered, raw.raw_data, "naid")
        supplier.supplier_category = self._category(supplier, lowered)
        supplier.quality_flags = self._quality_flags(supplier, lowered)
        return supplier

    def _company_name(self, raw: RawSupplierResult) -> str:
        title = re.sub(r"\s*[-|–—]\s*(ITAD|Data Center|Asset|Recycling|Texas|Home).*$", "", raw.original_title, flags=re.IGNORECASE)
        title = re.sub(r"\s*\|.*$", "", title).strip()
        if title:
            return title[:120]
        domain = urlparse(raw.source_url).netloc.removeprefix("www.")
        return domain or raw.source_url

    def _website(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else url

    def _company_type(self, lowered: str) -> str | None:
        if "data center decommission" in lowered:
            return "data_center_decommissioning_company"
        if "itad" in lowered or "asset disposition" in lowered:
            return "itad_company"
        if "server" in lowered and ("wholesale" in lowered or "refurb" in lowered):
            return "used_server_wholesaler"
        if "electronics recycler" in lowered or "recycling" in lowered:
            return "electronics_recycler"
        if "asset remarketing" in lowered or "asset recovery" in lowered:
            return "asset_remarketing_company"
        return "supplier_discovered"

    def _city(self, text: str) -> str | None:
        match = re.search(r"\b(Dallas|Fort Worth|Houston|Austin|San Antonio|El Paso|Midland|Odessa|Waco|Lubbock|Amarillo|Corpus Christi|Beaumont|Port Arthur|McAllen|Brownsville|Harlingen)\b", text, re.IGNORECASE)
        return match.group(1) if match else None

    def _state(self, text: str, raw: RawSupplierResult) -> str | None:
        if re.search(rf"\b({STATE_PATTERN})\b", text, re.IGNORECASE) or raw.raw_data.get("state") == "Texas":
            return "Texas"
        return raw.raw_data.get("state")

    def _zip(self, text: str) -> str | None:
        match = re.search(r"\b\d{5}(?:-\d{4})?\b", text)
        return match.group(0) if match else None

    def _phone(self, text: str) -> str | None:
        match = re.search(r"(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}", text)
        return match.group(0) if match else None

    def _email(self, text: str) -> str | None:
        match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        return match.group(0) if match else None

    def _service_area(self, text: str) -> str | None:
        match = re.search(r"(serving|service area|locations?)\s+([^.;|]{5,120})", text, re.IGNORECASE)
        return match.group(0)[:160] if match else None

    def _cert_status(self, lowered: str, raw_data: dict, cert: str) -> VerificationStatus:
        if cert in lowered:
            return (
                VerificationStatus.DIRECTORY_DISCOVERED
                if raw_data.get("discovery_mode") == "directory_search_discovery"
                else VerificationStatus.CLAIMED_ON_WEBSITE
            )
        return VerificationStatus.UNKNOWN

    def _equipment_types(self, lowered: str) -> list[str]:
        mapping = {
            "servers": ["server", "servers", "data center equipment"],
            "memory": ["memory", "ram"],
            "hard drives": ["hard drive", "hdd", "ssd", "storage"],
            "laptops": ["laptop", "laptops", "notebook"],
            "desktops": ["desktop", "computer"],
            "network equipment": ["switch", "router", "network equipment"],
        }
        return [name for name, tokens in mapping.items() if any(token in lowered for token in tokens)]

    def _category(self, supplier: SupplierResult, lowered: str) -> SupplierCategory:
        if supplier.data_center_decommissioning and (supplier.direct_asset_purchasing or supplier.asset_remarketing):
            return SupplierCategory.A
        if supplier.enterprise_itad or supplier.asset_remarketing or supplier.data_center_decommissioning:
            return SupplierCategory.B
        if supplier.server_recycling or supplier.computer_refurbishing or supplier.wholesale or supplier.bulk_sales:
            return SupplierCategory.C
        return SupplierCategory.D

    def _quality_flags(self, supplier: SupplierResult, lowered: str) -> list[str]:
        flags = ["needs_verification: supplier capabilities discovered from public source"]
        low_value = ["phone repair", "computer repair shop", "consumer drop-off", "residential recycling", "retail electronics store"]
        if any(token in lowered for token in low_value):
            flags.append("low_value: likely repair/consumer recycling")
        if not supplier.phone and not supplier.email:
            flags.append("needs_verification: contact details missing")
        if supplier.r2_certified != VerificationStatus.VERIFIED:
            flags.append("certification_not_officially_verified")
        return flags
