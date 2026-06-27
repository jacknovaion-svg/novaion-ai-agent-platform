from __future__ import annotations

from datetime import datetime, timedelta

from app.hardware_daily.detail_parser import HardwareListingDetailParser
from app.hardware_daily.models import (
    AuctionEndVerificationLevel,
    HardwareListingRecheckSummary,
    HardwareManualStatusReviewRequest,
    HardwareOpportunity,
    HardwareResultPageType,
    ListingStatus,
    RawHardwareListing,
    utc_now,
)
from app.hardware_daily.normalizer import HardwareListingNormalizer
from app.hardware_daily.scoring import HardwareOpportunityScoringService
from app.hardware_daily.store import hardware_daily_store


class ListingStatusRecheckService:
    def __init__(self) -> None:
        self.parser = HardwareListingDetailParser()
        self.normalizer = HardwareListingNormalizer()
        self.scoring = HardwareOpportunityScoringService()

    async def recheck_opportunity(self, opportunity: HardwareOpportunity) -> HardwareOpportunity:
        raw = RawHardwareListing(
            source_name=opportunity.source,
            source_url=opportunity.source_url,
            original_title=opportunity.raw_title or opportunity.title,
            original_description=opportunity.raw_description,
            category=opportunity.category,
            source_listing_id=opportunity.source_listing_id,
            seller_name=opportunity.seller_name,
            page_type=HardwareResultPageType.SPECIFIC_LISTING,
            classification_reason=opportunity.classification_reason,
            raw_data=opportunity.raw_data_json or {},
        )
        checked = await self.parser.enrich(raw)
        updated = self.normalizer.normalize(checked)
        updated.opportunity_id = opportunity.opportunity_id
        updated.first_seen_at = opportunity.first_seen_at
        updated.last_seen_at = utc_now()
        updated.status_check_attempts = (opportunity.status_check_attempts or 0) + 1
        updated.manual_result = opportunity.manual_result or {}
        updated.manual_status = opportunity.manual_status
        updated.manual_end_time = opportunity.manual_end_time
        updated.manual_timezone = opportunity.manual_timezone
        updated.manual_notes = opportunity.manual_notes
        updated.verified_by = opportunity.verified_by
        updated.verified_at = opportunity.verified_at
        updated = self._apply_status_rules(updated, previous=opportunity)
        updated = self.scoring.score([updated])[0]
        key = self.normalizer.opportunity_key(updated)
        hardware_daily_store.remember_opportunity(key, updated)
        return updated

    async def bulk_recheck(self, limit: int = 80) -> HardwareListingRecheckSummary:
        candidates = [
            item
            for item in hardware_daily_store.opportunities_by_key.values()
            if item.listing_status in {ListingStatus.ACTIVE, ListingStatus.ENDING_SOON, ListingStatus.UNKNOWN, ListingStatus.NEEDS_MANUAL_REVIEW, ListingStatus.UNAVAILABLE}
        ][:limit]
        summary = HardwareListingRecheckSummary()
        for opportunity in candidates:
            try:
                updated = await self.recheck_opportunity(opportunity)
                self._add_to_summary(summary, updated)
            except Exception:
                summary.errors += 1
            finally:
                summary.checked += 1
        return summary

    def apply_manual_review(self, opportunity_id: str, payload: HardwareManualStatusReviewRequest) -> HardwareOpportunity | None:
        for key, item in hardware_daily_store.opportunities_by_key.items():
            if str(item.opportunity_id) != opportunity_id:
                continue
            now = utc_now()
            item.manual_status = payload.manual_status
            item.manual_end_time = payload.manual_end_time
            item.manual_timezone = payload.manual_timezone
            item.manual_notes = payload.manual_notes
            item.verified_by = payload.verified_by
            item.verified_at = now
            item.manual_result = {
                "manual_status": payload.manual_status.value,
                "manual_end_time": payload.manual_end_time.isoformat() if payload.manual_end_time else None,
                "manual_timezone": payload.manual_timezone,
                "manual_notes": payload.manual_notes,
                "verified_by": payload.verified_by,
                "verified_at": now.isoformat(),
            }
            item.end_time_verification = AuctionEndVerificationLevel.MANUALLY_VERIFIED
            if payload.manual_end_time:
                item.end_time_utc = payload.manual_end_time
                item.auction_end_time = payload.manual_end_time
                item.end_time_user_timezone = payload.manual_end_time.isoformat()
            item.listing_status = payload.manual_status
            item.final_status = payload.manual_status
            item.needs_manual_review = payload.manual_status == ListingStatus.NEEDS_MANUAL_REVIEW
            item.last_status_check_at = now
            item.status_check_result = "manual_review_applied"
            item = self.scoring.score([item])[0]
            hardware_daily_store.opportunities_by_key[key] = item
            return item
        return None

    def _apply_status_rules(self, current: HardwareOpportunity, previous: HardwareOpportunity | None = None) -> HardwareOpportunity:
        now = utc_now()
        status = current.listing_status
        if current.end_time_utc and current.end_time_utc <= now:
            if status in {ListingStatus.ACTIVE, ListingStatus.ENDING_SOON}:
                current.end_time_verification = AuctionEndVerificationLevel.CONFLICTING
                current.status_check_result = "active_text_but_end_time_elapsed"
            status = ListingStatus.ENDED
        elif current.end_time_utc and current.end_time_utc > now:
            if current.end_time_utc - now <= timedelta(hours=24):
                status = ListingStatus.ENDING_SOON
            elif status in {ListingStatus.ENDED, ListingStatus.SOLD, ListingStatus.UNKNOWN, ListingStatus.NEEDS_MANUAL_REVIEW}:
                status = ListingStatus.ACTIVE
                current.status_check_result = current.status_check_result or "future_end_time_overrode_page_template_status"
        elif current.end_time_utc and current.end_time_utc - now <= timedelta(hours=24):
            status = ListingStatus.ENDING_SOON
        elif status == ListingStatus.UNAVAILABLE and previous and previous.end_time_utc and previous.end_time_utc <= now:
            status = ListingStatus.ENDED
            current.status_check_result = "unavailable_but_historical_end_time_elapsed"
        elif status == ListingStatus.UNAVAILABLE and not current.end_time_utc:
            status = ListingStatus.NEEDS_MANUAL_REVIEW
            current.needs_manual_review = True
            current.status_check_result = current.status_check_result or "detail_page_blocked_or_unavailable"
        elif status == ListingStatus.UNKNOWN:
            reference_time = current.last_status_check_at or current.first_seen_at
            if reference_time and now - reference_time > timedelta(hours=48):
                status = ListingStatus.NEEDS_MANUAL_REVIEW
                current.needs_manual_review = True
                current.status_check_result = "unknown_older_than_48h"
        current.listing_status = status
        current.final_status = status
        if status == ListingStatus.NEEDS_MANUAL_REVIEW:
            current.needs_manual_review = True
        return current

    def _add_to_summary(self, summary: HardwareListingRecheckSummary, item: HardwareOpportunity) -> None:
        if item.end_time_verification == AuctionEndVerificationLevel.CONFLICTING:
            summary.conflicting += 1
        if item.listing_status == ListingStatus.ACTIVE:
            summary.auto_active += 1
        elif item.listing_status == ListingStatus.ENDING_SOON:
            summary.ending_soon += 1
        elif item.listing_status == ListingStatus.ENDED:
            summary.auto_ended += 1
        elif item.listing_status == ListingStatus.NEEDS_MANUAL_REVIEW:
            summary.needs_manual_review += 1


listing_status_recheck_service = ListingStatusRecheckService()
