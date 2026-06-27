from __future__ import annotations

from app.hardware_daily.models import (
    ComponentCompleteness,
    HardwareCondition,
    HardwareOpportunity,
    ListingStatus,
    OpportunityRecommendation,
)


class HardwareOpportunityScoringService:
    def score(self, opportunities: list[HardwareOpportunity]) -> list[HardwareOpportunity]:
        for item in opportunities:
            score = 0.0
            reasons: list[str] = []
            recommendation_reasons: list[str] = []
            if item.listing_status in {ListingStatus.ENDED, ListingStatus.SOLD, ListingStatus.REMOVED, ListingStatus.UNAVAILABLE}:
                item.opportunity_score = 0
                item.risk_score = 100 if item.listing_status == ListingStatus.UNAVAILABLE else 75
                item.recommendation = OpportunityRecommendation.EXPIRED
                item.recommendation_reasons = ["expired_or_unavailable"]
                item.score_reasons = ["Listing is not currently actionable"]
                continue
            if item.category.value in item.title.lower() or item.model:
                score += 20
                reasons.append("型号或品类识别清晰")
            if item.quantity and item.quantity >= 5:
                score += 15
                reasons.append("疑似批量机会")
                recommendation_reasons.append("large_quantity")
            if item.current_total_cost or item.total_price or item.unit_price:
                score += 15
                reasons.append("价格可见")
                if item.cost_per_unit and item.cost_per_unit < 500:
                    recommendation_reasons.append("attractive_unit_cost")
            if item.condition in {HardwareCondition.USED_WORKING, HardwareCondition.REFURBISHED, HardwareCondition.TESTED}:
                score += 15
                reasons.append("成色/测试状态较好")
                recommendation_reasons.append("tested_inventory")
            elif item.condition in {HardwareCondition.UNTESTED, HardwareCondition.PARTS_ONLY, HardwareCondition.SALVAGE}:
                score += 4
                recommendation_reasons.append("unknown_condition" if item.condition == HardwareCondition.UNTESTED else "salvage_or_parts_only")
            if item.seller_type in {"government_surplus", "auctioneer", "itad_supplier"}:
                score += 15
                reasons.append("来源类型有采购价值")
                recommendation_reasons.append("data_center_grade" if item.category.value in {"servers", "gpu", "memory", "storage"} else "auction_source")
            if item.shipping_available is True or item.pickup_only is False:
                score += 8
            if item.pickup_only:
                recommendation_reasons.append("pickup_only")
            if item.location_state:
                score += 5
            if item.confidence_level.value in {"marketplace_listing", "official_source"}:
                score += 7
            if item.listing_status == ListingStatus.ENDING_SOON:
                score += 5
                recommendation_reasons.append("auction_ending_soon")
            if not item.buyer_premium:
                recommendation_reasons.append("buyer_premium_unknown")
            if item.component_completeness in {
                ComponentCompleteness.MISSING_CPU,
                ComponentCompleteness.MISSING_MEMORY,
                ComponentCompleteness.MISSING_STORAGE,
                ComponentCompleteness.MISSING_PSU,
                ComponentCompleteness.BAREBONE,
                ComponentCompleteness.MIXED_LOT,
            }:
                recommendation_reasons.append("missing_manifest")
            risk_score = 0.0
            risk_score += 12 * len(item.risk_flags)
            if item.condition in {HardwareCondition.UNTESTED, HardwareCondition.PARTS_ONLY, HardwareCondition.SALVAGE, HardwareCondition.BROKEN}:
                risk_score += 25
            if item.component_completeness in {
                ComponentCompleteness.MISSING_CPU,
                ComponentCompleteness.MISSING_MEMORY,
                ComponentCompleteness.MISSING_STORAGE,
                ComponentCompleteness.MISSING_PSU,
                ComponentCompleteness.BAREBONE,
                ComponentCompleteness.MIXED_LOT,
            }:
                risk_score += 15
            if not item.total_price and not item.current_price:
                risk_score += 10
            if item.needs_manual_review:
                risk_score += 10
            item.opportunity_score = min(score, 100)
            item.risk_score = min(risk_score, 100)
            item.score_reasons = reasons
            if item.risk_score >= 70:
                item.recommendation = OpportunityRecommendation.HIGH_RISK
            elif item.needs_manual_review or not item.quantity or not (item.total_price or item.current_price):
                item.recommendation = OpportunityRecommendation.INFORMATION_INCOMPLETE
            elif item.listing_status == ListingStatus.ENDING_SOON and item.opportunity_score >= 50:
                item.recommendation = OpportunityRecommendation.URGENT_REVIEW
            elif item.opportunity_score >= 45:
                item.recommendation = OpportunityRecommendation.WORTH_TRACKING
            else:
                item.recommendation = OpportunityRecommendation.IGNORE
            item.recommendation_reasons = list(dict.fromkeys(recommendation_reasons))
        return sorted(opportunities, key=lambda opportunity: (opportunity.opportunity_score, -opportunity.risk_score), reverse=True)
