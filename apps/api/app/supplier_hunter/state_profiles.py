from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupplierRegionProfile:
    name: str
    cities: tuple[str, ...]
    search_phrases: tuple[str, ...]


TEXAS_SUPPLIER_REGIONS: tuple[SupplierRegionProfile, ...] = (
    SupplierRegionProfile("Dallas-Fort Worth", ("Dallas", "Fort Worth", "Arlington"), ("Dallas Texas", "Fort Worth Texas", "DFW Texas")),
    SupplierRegionProfile("Houston", ("Houston",), ("Houston Texas", "Houston metro Texas")),
    SupplierRegionProfile("Austin", ("Austin",), ("Austin Texas",)),
    SupplierRegionProfile("San Antonio", ("San Antonio",), ("San Antonio Texas",)),
    SupplierRegionProfile("El Paso", ("El Paso",), ("El Paso Texas",)),
    SupplierRegionProfile("Midland-Odessa", ("Midland", "Odessa"), ("Midland Odessa Texas", "Permian Basin Texas")),
    SupplierRegionProfile("Waco", ("Waco",), ("Waco Texas",)),
    SupplierRegionProfile("Lubbock", ("Lubbock",), ("Lubbock Texas",)),
    SupplierRegionProfile("Amarillo", ("Amarillo",), ("Amarillo Texas",)),
    SupplierRegionProfile("Corpus Christi", ("Corpus Christi",), ("Corpus Christi Texas",)),
    SupplierRegionProfile("Beaumont-Port Arthur", ("Beaumont", "Port Arthur"), ("Beaumont Port Arthur Texas", "Southeast Texas")),
    SupplierRegionProfile("Rio Grande Valley", ("McAllen", "Brownsville", "Harlingen"), ("Rio Grande Valley Texas", "McAllen Texas")),
)


SUPPLIER_STATE_PROFILES = {
    "TX": {
        "state_code": "TX",
        "state_name": "Texas",
        "regions": TEXAS_SUPPLIER_REGIONS,
        "statewide_queries": (
            "corporate laptop liquidation Texas",
            "asset remarketing company Texas",
            "bulk used laptops wholesale Texas",
            "used enterprise server supplier Texas",
            "data center equipment buyer Texas",
            "R2 certified electronics recycler Texas",
        ),
        "max_suppliers": 80,
    }
}


def get_supplier_state_profile(state_code: str | None):
    if not state_code:
        return None
    return SUPPLIER_STATE_PROFILES.get(state_code.upper())

