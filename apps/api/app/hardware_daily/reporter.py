from __future__ import annotations

import hashlib

import httpx

from app.core.config import get_settings
from app.hardware_daily.models import (
    HardwareDailyReport,
    HardwareScanJob,
    TelegramDeliveryLog,
    TelegramDeliveryStatus,
    utc_now,
)
from app.hardware_daily.store import hardware_daily_store


class TelegramHardwareDailyReporter:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def build_and_send(self, job: HardwareScanJob, force_send: bool = False) -> HardwareDailyReport:
        message = self._build_message(job)
        message_hash = hashlib.sha256(message.encode("utf-8")).hexdigest()
        status = TelegramDeliveryStatus.DISABLED
        error_message = None
        sent_at = None

        if hardware_daily_store.has_telegram_message(job.id, "daily_hardware_report", message_hash):
            status = TelegramDeliveryStatus.DUPLICATE_SKIPPED
        elif not self.settings.hardware_hunter_telegram_enabled and not force_send:
            status = TelegramDeliveryStatus.DISABLED
        elif not self.settings.hardware_hunter_telegram_bot_token or not self.settings.hardware_hunter_telegram_chat_id:
            status = TelegramDeliveryStatus.DRY_RUN
        else:
            try:
                await self._send_telegram(message)
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

    async def _send_telegram(self, message: str) -> None:
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

    def _build_message(self, job: HardwareScanJob) -> str:
        stats = job.quality_stats
        lines = [
            "NOVAION Hardware Hunter V2 日报",
            f"扫描Job: {job.id}",
            f"状态: {job.status.value}",
            f"原始结果: {stats.raw_results} | 去重后机会: {stats.final_opportunities} | 新机会: {stats.new_opportunities}",
            f"价格变化: {stats.price_changes} | 数量变化: {stats.quantity_changes} | 失败来源: {stats.failed_sources}",
            "",
            "Top机会:",
        ]
        for index, item in enumerate(job.opportunities[:8], start=1):
            price = f"${item.total_price:,.0f}" if item.total_price else "价格 unknown"
            model = item.model or "型号 unknown"
            lines.extend(
                [
                    f"{index}. [{item.category.value}] {item.title[:96]}",
                    f"   型号: {model} | 数量: {item.quantity or 'unknown'} | {price}",
                    f"   分数: {item.opportunity_score:.0f}/100 | 风险: {item.risk_score:.0f}/100 | 来源: {item.source}",
                    f"   链接: {item.source_url}",
                ]
            )
        if not job.opportunities:
            lines.append("本轮没有发现合格硬件机会。")
        lines.extend(
            [
                "",
                "说明: 公开搜索发现结果需要人工核查；系统不会自动购买、出价、联系卖家或判断最终可采购性。",
            ]
        )
        return "\n".join(lines)
