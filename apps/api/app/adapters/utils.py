from __future__ import annotations

from datetime import datetime, timezone
import re


def parse_price(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"\$?\s*([0-9,]+(?:\.[0-9]{2})?)", value)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def infer_brand_and_model(query: str, title: str) -> tuple[str | None, str | None]:
    known_brands = [
        "NVIDIA",
        "AMD",
        "Intel",
        "Samsung",
        "Kingston",
        "Crucial",
        "Micron",
        "Seagate",
        "Western Digital",
        "ASUS",
        "MSI",
        "Gigabyte",
        "PNY",
        "Dell",
        "HPE",
    ]
    combined = f"{query} {title}".lower()
    brand = next((item for item in known_brands if item.lower() in combined), None)
    model_patterns = [
        r"RTX\s?\d{4}",
        r"EPYC\s?\d{4}",
        r"\d+(?:GB|TB)\s?[A-Z0-9\- ]{0,20}",
        r"DDR5\s?[A-Z0-9\- ]{0,20}",
    ]
    model = None
    for pattern in model_patterns:
        found = re.search(pattern, f"{query} {title}", flags=re.IGNORECASE)
        if found:
            model = found.group(0).strip()
            break
    return brand, model


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
