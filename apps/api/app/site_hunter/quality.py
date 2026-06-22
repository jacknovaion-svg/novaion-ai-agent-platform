from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from app.site_hunter.models import (
    NormalizedSiteListing,
    ResultCategory,
    ResultQualityStats,
    SiteHunterStructuredCriteria,
    SourceType,
)


class ResultQualityService:
    def process(
        self,
        listings: list[NormalizedSiteListing],
        criteria: SiteHunterStructuredCriteria,
    ) -> tuple[list[NormalizedSiteListing], list[NormalizedSiteListing], ResultQualityStats]:
        stats = ResultQualityStats(raw_results=len(listings))
        categorized: list[NormalizedSiteListing] = []

        for listing in listings:
            listing.result_category = self._classify(listing)
            self._apply_quality_flags(listing)
            categorized.append(listing)
            if listing.result_category == ResultCategory.SPECIFIC_LISTING:
                stats.specific_listings += 1
            elif listing.result_category == ResultCategory.LISTING_COLLECTION:
                stats.listing_collections += 1
            elif listing.result_category == ResultCategory.SOURCE_PAGE:
                stats.source_pages += 1
            else:
                stats.irrelevant_results += 1

        final_candidates: list[NormalizedSiteListing] = []
        discovery_candidates: list[NormalizedSiteListing] = []
        seen_specific: set[str] = set()
        seen_discovery: set[str] = set()

        for listing in categorized:
            if listing.result_category == ResultCategory.IRRELEVANT:
                continue
            if self._state_mismatch(listing, criteria):
                stats.state_mismatch_removed += 1
                continue
            if listing.result_category == ResultCategory.SPECIFIC_LISTING:
                if self._size_mismatch(listing, criteria):
                    stats.size_mismatch_removed += 1
                    continue
                if self._budget_mismatch(listing, criteria):
                    stats.budget_mismatch_removed += 1
                    continue
                key = self._specific_key(listing)
                if key in seen_specific:
                    stats.duplicates_removed += 1
                    continue
                seen_specific.add(key)
                final_candidates.append(listing)
                continue

            key = self._discovery_key(listing)
            if key in seen_discovery:
                stats.duplicates_removed += 1
                continue
            seen_discovery.add(key)
            discovery_candidates.append(listing)

        stats.final_candidates = len(final_candidates)
        return final_candidates, discovery_candidates, stats

    def _classify(self, listing: NormalizedSiteListing) -> ResultCategory:
        url = listing.source_url.lower()
        parsed = urlparse(url)
        domain = parsed.netloc.removeprefix("www.")
        path = parsed.path.lower().rstrip("/")
        text = f"{listing.original_title} {listing.original_description or ''}".lower()

        if self._is_irrelevant(domain, path, text):
            return ResultCategory.IRRELEVANT
        if self._is_specific_listing(domain, path, text, listing):
            return ResultCategory.SPECIFIC_LISTING
        if self._is_listing_collection(domain, path, text):
            return ResultCategory.LISTING_COLLECTION
        if self._is_source_page(listing, domain, path, text):
            return ResultCategory.SOURCE_PAGE
        return ResultCategory.SOURCE_PAGE

    def _is_irrelevant(self, domain: str, path: str, text: str) -> bool:
        if any(blocked in domain for blocked in ["texags.com", "reddit.com", "facebook.com", "youtube.com", "wikipedia.org"]):
            return True
        if any(token in text for token in ["forum", "news", "restaurant", "franchise", "residential", "single family", "apartment"]):
            return True
        if "businesses for sale" in text and not any(token in text for token in ["real estate", "land", "property", "acre"]):
            return True
        if any(token in domain for token in ["bizquest.com", "bizbuysell.com", "tworld.com", "linkbusiness.com"]):
            return not any(token in text for token in ["real estate", "land", "property", "acre"])
        return False

    def _is_specific_listing(self, domain: str, path: str, text: str, listing: NormalizedSiteListing) -> bool:
        if "commercial.century21.com" in domain and "/listing/" in path:
            return True
        if "crexi.com" in domain and re.search(r"/properties/\d+", path):
            return True
        if any(token in path for token in ["/listing/", "/property/"]) and not self._collection_path(path):
            return True
        has_address_signal = bool(listing.address_line_1 and listing.city and listing.state)
        has_listing_facts = bool(listing.land_acres or listing.building_sqft or listing.asking_price_usd)
        return has_address_signal and has_listing_facts and not self._collection_text(text)

    def _is_listing_collection(self, domain: str, path: str, text: str) -> bool:
        if self._collection_path(path) or self._collection_text(text):
            return True
        if any(token in domain for token in ["landsearch.com", "commercialcafe.com", "realmo.com", "kwland.com", "ranchflip.com"]):
            return True
        if "crexi.com" in domain and "/properties/" in path:
            return True
        return False

    def _is_source_page(self, listing: NormalizedSiteListing, domain: str, path: str, text: str) -> bool:
        if listing.source_type in {
            SourceType.STATE_GOVERNMENT,
            SourceType.COUNTY_GOVERNMENT,
            SourceType.CITY_GOVERNMENT,
            SourceType.ECONOMIC_DEVELOPMENT,
            SourceType.INDUSTRIAL_PARK,
            SourceType.UTILITY,
        }:
            return True
        if any(token in text for token in ["economic development", "industrial park", "available sites", "utility-served", "powered land"]):
            return True
        if path in {"", "/"}:
            return True
        return False

    def _collection_path(self, path: str) -> bool:
        return any(
            token in path
            for token in [
                "/real-estate/",
                "/for-sale",
                "/properties/tx/",
                "/properties/ga/",
                "/commercial",
                "/industrial",
                "/land",
                "/search",
            ]
        )

    def _collection_text(self, text: str) -> bool:
        return any(
            token in text
            for token in [
                "properties for sale",
                "real estate for sale",
                "for sale and lease",
                "land for sale in",
                "commercial lots for sale",
                "search land for sale",
                "browse",
                "listings",
                "currently listed",
            ]
        )

    def _state_mismatch(self, listing: NormalizedSiteListing, criteria: SiteHunterStructuredCriteria) -> bool:
        target_states = {state.lower() for state in criteria.regions.states}
        if not target_states or not listing.state:
            return False
        return listing.state.lower() not in target_states

    def _size_mismatch(self, listing: NormalizedSiteListing, criteria: SiteHunterStructuredCriteria) -> bool:
        return bool(criteria.min_land_acres and listing.land_acres and listing.land_acres < criteria.min_land_acres)

    def _budget_mismatch(self, listing: NormalizedSiteListing, criteria: SiteHunterStructuredCriteria) -> bool:
        return bool(criteria.max_price_usd and listing.asking_price_usd and listing.asking_price_usd > criteria.max_price_usd)

    def _specific_key(self, listing: NormalizedSiteListing) -> str:
        if listing.address_line_1 and listing.city and listing.state:
            return f"{listing.address_line_1}|{listing.city}|{listing.state}".lower()
        return self._normalized_url(listing.source_url)

    def _discovery_key(self, listing: NormalizedSiteListing) -> str:
        return self._normalized_url(listing.source_url)

    def _normalized_url(self, url: str) -> str:
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc.lower().removeprefix("www."), parsed.path.rstrip("/"), "", "", ""))

    def _apply_quality_flags(self, listing: NormalizedSiteListing) -> None:
        flags: list[str] = []
        if listing.result_category == ResultCategory.SPECIFIC_LISTING:
            if not listing.land_acres:
                flags.append("needs_verification: land_acres unknown")
            if not listing.address_line_1:
                flags.append("needs_verification: address unknown")
            if not listing.asking_price_usd:
                flags.append("needs_verification: price unknown")
        if listing.result_category == ResultCategory.LISTING_COLLECTION:
            flags.append("not_formal_candidate: listing_collection")
        if listing.result_category == ResultCategory.SOURCE_PAGE:
            flags.append("not_formal_candidate: source_page")
        listing.quality_flags = flags
