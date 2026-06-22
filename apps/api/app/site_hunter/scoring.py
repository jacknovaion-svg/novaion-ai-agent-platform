from __future__ import annotations

from app.site_hunter.models import NormalizedSiteListing


class SiteOpportunityScoringService:
    def score(self, listings: list[NormalizedSiteListing]) -> list[NormalizedSiteListing]:
        for listing in listings:
            score = 0.0
            reasons: list[str] = []
            if listing.property_type:
                score += 20
                reasons.append(f"Industrial property type identified: {listing.property_type}")
            if listing.land_acres:
                score += 15 if listing.land_acres >= 20 else 8
                reasons.append(f"Land acreage found: {listing.land_acres:g} acres")
            if listing.zoning:
                score += 15
                reasons.append("Zoning information found")
            if listing.state or listing.city or listing.zip_code:
                score += 10
                reasons.append("Regional location information found")
            if listing.asking_price_usd:
                score += 10
                reasons.append(f"Asking price extracted: ${listing.asking_price_usd:,.0f}")
            if listing.original_description:
                score += 10
                reasons.append("Source description or search snippet retained")
            if listing.source_url:
                score += 10
                reasons.append("Original source URL retained")
            score += max(0, 10 - len(listing.missing_fields))

            listing.preliminary_score = round(min(score, 100), 2)
            listing.preliminary_grade = self._grade(listing.preliminary_score)
            listing.score_reasons = reasons
            listing.warnings.append("Power assets and utility capacity are reserved for the next phase.")
        return sorted(listings, key=lambda item: item.preliminary_score, reverse=True)

    def _grade(self, score: float) -> str:
        if score >= 80:
            return "A"
        if score >= 65:
            return "B"
        if score >= 45:
            return "C"
        return "D"
