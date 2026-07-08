from __future__ import annotations

import hashlib
from datetime import timedelta, timezone
from typing import Any

import httpx

from app.core.config import get_settings
from app.hardware_daily.models import (
    AuctionEndVerificationLevel,
    HardwareDailyReport,
    HardwareScanJob,
    ListingStatus,
    TelegramDeliveryLog,
    TelegramDeliveryStatus,
    TelegramReportAction,
    utc_now,
)
from app.hardware_daily.store import hardware_daily_store


class TelegramHardwareDailyReporter:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def build_and_send(
        self,
        job: HardwareScanJob,
        action: str | TelegramReportAction = TelegramReportAction.PREVIEW,
        message_override: str | None = None,
    ) -> HardwareDailyReport:
        action = TelegramReportAction(action)
        message = message_override or self._build_message(job)
        message_hash = hashlib.sha256(message.encode("utf-8")).hexdigest()
        status = TelegramDeliveryStatus.DISABLED
        error_message = None
        sent_at = None
        telegram_message_id = None

        if action == TelegramReportAction.PREVIEW:
            status = TelegramDeliveryStatus.DRY_RUN
        elif hardware_daily_store.has_telegram_message(job.id, "daily_hardware_report", message_hash):
            status = TelegramDeliveryStatus.DUPLICATE_SKIPPED
        elif action == TelegramReportAction.APPROVE_AND_SEND and not self.settings.hardware_hunter_telegram_enabled:
            status = TelegramDeliveryStatus.DISABLED
        elif not self.settings.hardware_hunter_telegram_bot_token or not self.settings.hardware_hunter_telegram_chat_id:
            status = TelegramDeliveryStatus.DRY_RUN
        else:
            try:
                response_data = await self._send_telegram(message)
                telegram_message_id = self._extract_message_id(response_data)
                status = TelegramDeliveryStatus.SENT
                sent_at = utc_now()
            except Exception as exc:
                status = TelegramDeliveryStatus.FAILED
                error_message = str(exc)[:500]

        log = TelegramDeliveryLog(
            scan_job_id=job.id,
            message_hash=message_hash,
            status=status,
            chat_id=self.settings.hardware_hunter_telegram_chat_id,
            telegram_message_id=telegram_message_id,
            error_message=error_message,
            sent_at=sent_at,
        )
        hardware_daily_store.add_telegram_log(log)
        return HardwareDailyReport(
            scan_job_id=job.id,
            title="NOVAION Hardware Hunter 日报",
            message_zh=message,
            delivery_log=log,
        )

    async def _send_telegram(self, message: str) -> dict[str, Any]:
        token = self.settings.hardware_hunter_telegram_bot_token
        chat_id = self.settings.hardware_hunter_telegram_chat_id
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message[:3900],
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
            return response.json()

    def _extract_message_id(self, response_data: dict[str, Any]) -> str | None:
        result = response_data.get("result")
        if not isinstance(result, dict):
            return None
        message_id = result.get("message_id")
        return str(message_id) if message_id is not None else None

    def _build_message(self, job: HardwareScanJob) -> str:
        stats = job.quality_stats
        lines = [
            "NOVAION Hardware Hunter V2 日报",
            f"扫描Job: {job.id}",
            f"状态: {job.status.value}",
            f"原始结果: {stats.raw_results} | 具体listing: {stats.specific_listings} | 当前有效机会: {stats.final_opportunities} | 新机会: {stats.new_opportunities}",
            f"分类页: {stats.listing_collections} | 来源页: {stats.source_pages} | 无关: {stats.irrelevant}",
            f"Active: {stats.active_opportunities} | Ending soon: {stats.ending_soon} | 已过滤过期: {stats.expired_removed} | 失效链接: {stats.unavailable_links}",
            f"Needs review: {stats.needs_manual_review} | 变化机会: {stats.changed_opportunities} | 价格变化: {stats.price_changes} | 失败来源: {stats.failed_sources}",
            "",
            "Top重点机会:",
        ]
        current_opportunities = [
            item
            for item in job.opportunities
            if self._eligible_for_top_report(item)
        ]
        for index, item in enumerate(current_opportunities[:8], start=1):
            price = f"${item.current_total_cost or item.total_price or item.current_price:,.0f}" if item.current_total_cost or item.total_price or item.current_price else "unknown"
            location = item.location_text or ", ".join(part for part in [item.location_city, item.location_state] if part) or "unknown"
            keywords = ", ".join(self._matched_keywords(item)[:6]) or "unknown"
            end_time = item.end_time_raw or (item.end_time_utc.isoformat() if item.end_time_utc else item.time_remaining) or "unknown"
            lines.extend(
                [
                    "🔥 Hardware Opportunity",
                    f"Title: {item.title[:140]}",
                    f"Source: {item.source}",
                    f"Location: {location}",
                    f"Ends: {end_time}",
                    f"Quantity: {item.quantity or 'unknown'}",
                    f"Current Bid: {price}",
                    f"AI Score: {item.opportunity_score:.0f}/100",
                    f"Matched Keywords: {keywords}",
                    f"URL: {item.source_url}",
                ]
            )
        if not current_opportunities:
            lines.append("本轮没有发现当前有效的具体硬件机会。")
        lines.extend(
            [
                "",
                "说明: 公开搜索发现结果需要人工核查；系统不会自动购买、出价、联系卖家或判断最终可采购性。",
            ]
        )
        return "\n".join(lines)

    def _matched_keywords(self, item) -> list[str]:
        values = item.matched_keywords or item.raw_data_json.get("matched_keywords") or []
        if isinstance(values, str):
            values = [values]
        return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))

    def _eligible_for_top_report(self, item) -> bool:
        if item.raw_data_json.get("discovery_source") == "GovAuctions.app" and item.raw_data_json.get("verification_status") != "verified":
            return False
        if self._has_review_blocker(item) or self._has_past_end_time(item):
            return False
        if item.listing_status in {ListingStatus.ACTIVE, ListingStatus.ENDING_SOON}:
            if self._has_unconfirmed_blocked_source(item):
                return False
            return True
        if item.listing_status == ListingStatus.UNKNOWN and not item.needs_manual_review:
            if self._has_unconfirmed_blocked_source(item) or not item.first_seen_at or not item.last_status_check_at:
                return False
            return (
                utc_now() - item.first_seen_at <= timedelta(hours=24)
                and utc_now() - item.last_status_check_at <= timedelta(hours=24)
            )
        return False

    def _has_review_blocker(self, item) -> bool:
        return bool(
            item.needs_manual_review
            or item.listing_status in {ListingStatus.NEEDS_MANUAL_REVIEW, ListingStatus.UNAVAILABLE, ListingStatus.IGNORED}
            or item.end_time_verification == AuctionEndVerificationLevel.CONFLICTING
            or item.unavailable_reason
        )

    def _confirmed_end_time(self, item):
        return item.end_time_utc or item.auction_end_time or item.calculated_end_time

    def _has_past_end_time(self, item) -> bool:
        end_time = self._confirmed_end_time(item)
        if not end_time:
            return False
        now = utc_now()
        try:
            return end_time <= now
        except TypeError:
            return end_time.replace(tzinfo=timezone.utc) <= now

    def _has_unconfirmed_blocked_source(self, item) -> bool:
        if self._confirmed_end_time(item):
            return False
        source = (item.source or "").lower()
        status_note = " ".join(
            str(value or "").lower()
            for value in [
                item.unavailable_reason,
                item.status_check_result,
                item.status_check_error,
                item.raw_data_json.get("detail_parse_status"),
                item.raw_data_json.get("detail_error"),
            ]
        )
        blocked = any(token in status_note for token in ["blocked", "captcha", "403", "login", "unavailable"])
        return blocked or ("govdeals" in source and item.end_time_verification == AuctionEndVerificationLevel.UNKNOWN)
