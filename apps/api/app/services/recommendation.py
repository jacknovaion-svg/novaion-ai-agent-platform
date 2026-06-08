from __future__ import annotations

from app.models.schemas import NormalizedResult


class RecommendationService:
    def score(self, results: list[NormalizedResult]) -> list[NormalizedResult]:
        priced = [item.price for item in results if item.price is not None and item.price > 0]
        min_price = min(priced) if priced else None
        max_price = max(priced) if priced else None

        for item in results:
            inventory_score = self._inventory_score(item) * 40
            price_score = self._price_score(item.price, min_price, max_price) * 30
            distance_score = self._distance_score(item.distance) * 20
            promo_score = (1 if item.promotion else 0) * 10
            item.recommendation_score = round(inventory_score + price_score + distance_score + promo_score, 2)

        return sorted(results, key=lambda item: item.recommendation_score, reverse=True)

    def _inventory_score(self, item: NormalizedResult) -> float:
        status = (item.inventory_status or "").lower()
        if any(token in status for token in ["in stock", "available", "ready"]):
            return 1
        if any(token in status for token in ["limited", "check"]):
            return 0.5
        return 0

    def _price_score(self, price: float | None, min_price: float | None, max_price: float | None) -> float:
        if price is None:
            return 0.3
        if min_price is None or max_price is None or min_price == max_price:
            return 1
        return max(0, 1 - ((price - min_price) / (max_price - min_price)))

    def _distance_score(self, distance: float | None) -> float:
        if distance is None:
            return 0.6
        if distance <= 5:
            return 1
        if distance <= 25:
            return 0.7
        if distance <= 50:
            return 0.4
        return 0.1
