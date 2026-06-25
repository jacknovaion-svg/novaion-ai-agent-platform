from __future__ import annotations

from app.hardware_daily.models import HardwareCondition, HardwareOpportunity


class HardwareOpportunityScoringService:
    def score(self, opportunities: list[HardwareOpportunity]) -> list[HardwareOpportunity]:
        for item in opportunities:
            score = 0.0
            reasons: list[str] = []
            if item.category.value in item.title.lower() or item.model:
                score += 20
                reasons.append("型号或品类识别清晰")
            if item.quantity and item.quantity >= 5:
                score += 15
                reasons.append("疑似批量机会")
            if item.total_price or item.unit_price:
                score += 15
                reasons.append("价格可见")
            if item.condition in {HardwareCondition.USED_WORKING, HardwareCondition.REFURBISHED, HardwareCondition.TESTED}:
                score += 15
                reasons.append("成色/测试状态较好")
            elif item.condition in {HardwareCondition.UNTESTED, HardwareCondition.PARTS_ONLY, HardwareCondition.SALVAGE}:
                score += 4
            if item.seller_type in {"government_surplus", "auctioneer", "itad_supplier"}:
                score += 15
                reasons.append("来源类型有采购价值")
            if item.shipping_available is True or item.pickup_only is False:
                score += 8
            if item.location_state:
                score += 5
            if item.confidence_level.value in {"marketplace_listing", "official_source"}:
                score += 7
            risk_score = 0.0
            risk_score += 12 * len(item.risk_flags)
            if item.condition in {HardwareCondition.UNTESTED, HardwareCondition.PARTS_ONLY, HardwareCondition.SALVAGE, HardwareCondition.BROKEN}:
                risk_score += 25
            if not item.total_price:
                risk_score += 10
            item.opportunity_score = min(score, 100)
            item.risk_score = min(risk_score, 100)
            item.score_reasons = reasons
        return sorted(opportunities, key=lambda opportunity: (opportunity.opportunity_score, -opportunity.risk_score), reverse=True)
