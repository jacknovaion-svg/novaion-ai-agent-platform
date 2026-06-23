from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StateRegionProfile:
    name: str
    region_type: str
    cities: tuple[str, ...] = ()
    counties: tuple[str, ...] = ()
    search_phrases: tuple[str, ...] = ()
    max_specific_listings: int = 15


@dataclass(frozen=True)
class StateSearchProfile:
    state_code: str
    state_name: str
    regions: tuple[StateRegionProfile, ...] = field(default_factory=tuple)
    statewide_queries: tuple[str, ...] = field(default_factory=tuple)
    utility_queries: tuple[str, ...] = field(default_factory=tuple)
    max_formal_candidates: int = 80
    power_screening_top_n: int = 20


TEXAS_PROFILE = StateSearchProfile(
    state_code="TX",
    state_name="Texas",
    regions=(
        StateRegionProfile(
            name="Dallas-Fort Worth",
            region_type="metro",
            cities=("Dallas", "Fort Worth", "Arlington"),
            counties=("Dallas", "Tarrant", "Denton", "Collin", "Ellis"),
            search_phrases=("Dallas Fort Worth Texas", "DFW industrial corridor Texas"),
        ),
        StateRegionProfile(
            name="Houston",
            region_type="metro",
            cities=("Houston", "Baytown", "Pasadena"),
            counties=("Harris", "Fort Bend", "Montgomery", "Brazoria"),
            search_phrases=("Houston Texas", "Houston industrial corridor Texas", "Port Houston industrial land Texas"),
        ),
        StateRegionProfile(
            name="San Antonio",
            region_type="metro",
            cities=("San Antonio", "New Braunfels"),
            counties=("Bexar", "Comal", "Guadalupe"),
            search_phrases=("San Antonio Texas", "I-35 industrial corridor San Antonio Texas"),
        ),
        StateRegionProfile(
            name="Austin",
            region_type="metro",
            cities=("Austin", "Round Rock", "Taylor"),
            counties=("Travis", "Williamson", "Hays"),
            search_phrases=("Austin Texas", "Austin industrial land Texas", "Taylor Texas industrial land"),
        ),
        StateRegionProfile(
            name="Midland-Odessa",
            region_type="industrial_corridor",
            cities=("Midland", "Odessa"),
            counties=("Midland", "Ector"),
            search_phrases=("Midland Odessa Texas", "Permian Basin industrial land Texas"),
        ),
        StateRegionProfile(
            name="Abilene",
            region_type="city",
            cities=("Abilene",),
            counties=("Taylor",),
            search_phrases=("Abilene Texas", "Taylor County Texas industrial land"),
        ),
        StateRegionProfile(
            name="Waco",
            region_type="city",
            cities=("Waco",),
            counties=("McLennan",),
            search_phrases=("Waco Texas", "McLennan County Texas industrial land"),
        ),
        StateRegionProfile(
            name="Temple-Killeen",
            region_type="industrial_corridor",
            cities=("Temple", "Killeen"),
            counties=("Bell",),
            search_phrases=("Temple Killeen Texas", "Bell County Texas industrial land"),
        ),
        StateRegionProfile(
            name="Amarillo",
            region_type="city",
            cities=("Amarillo",),
            counties=("Potter", "Randall"),
            search_phrases=("Amarillo Texas", "Panhandle Texas industrial land"),
        ),
        StateRegionProfile(
            name="Lubbock",
            region_type="city",
            cities=("Lubbock",),
            counties=("Lubbock",),
            search_phrases=("Lubbock Texas", "Lubbock County Texas industrial land"),
        ),
        StateRegionProfile(
            name="Corpus Christi",
            region_type="metro",
            cities=("Corpus Christi",),
            counties=("Nueces", "San Patricio"),
            search_phrases=("Corpus Christi Texas", "Corpus Christi industrial land"),
        ),
        StateRegionProfile(
            name="Beaumont-Port Arthur",
            region_type="industrial_corridor",
            cities=("Beaumont", "Port Arthur"),
            counties=("Jefferson", "Orange"),
            search_phrases=("Beaumont Port Arthur Texas", "Southeast Texas industrial land"),
        ),
        StateRegionProfile(
            name="El Paso",
            region_type="metro",
            cities=("El Paso",),
            counties=("El Paso",),
            search_phrases=("El Paso Texas", "El Paso industrial land"),
        ),
    ),
    statewide_queries=(
        "Texas economic development available sites",
        "shovel-ready industrial sites Texas",
        "Texas industrial parks available sites",
    ),
    utility_queries=(
        "utility-served industrial land Texas",
        "powered land for data center Texas",
        "Texas utility economic development industrial sites",
    ),
)


STATE_SEARCH_PROFILES = {
    "TX": TEXAS_PROFILE,
}


def get_state_search_profile(state_code: str | None) -> StateSearchProfile | None:
    if not state_code:
        return None
    return STATE_SEARCH_PROFILES.get(state_code.upper())

