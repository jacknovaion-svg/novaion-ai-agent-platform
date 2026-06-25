from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from app.hardware_daily.models import (
    HardwareChangeType,
    HardwareOpportunity,
    HardwarePriceHistoryRecord,
    HardwareSchedulerState,
    HardwareScanJob,
    TelegramDeliveryLog,
    utc_now,
)


class HardwareDailyMemoryStore:
    def __init__(self) -> None:
        self.jobs: dict[UUID, HardwareScanJob] = {}
        self.opportunities_by_key: dict[str, HardwareOpportunity] = {}
        self.price_history: list[HardwarePriceHistoryRecord] = []
        self.telegram_logs: list[TelegramDeliveryLog] = []
        self.scheduler_state_path = Path(__file__).resolve().parents[2] / "data" / "hardware_scheduler_state.json"
        self.scheduler_state = self._load_scheduler_state()

    def create_job(self, job: HardwareScanJob) -> HardwareScanJob:
        self.jobs[job.id] = job
        return job

    def update_job(self, job: HardwareScanJob) -> HardwareScanJob:
        job.updated_at = utc_now()
        self.jobs[job.id] = job
        return job

    def get_job(self, job_id: UUID) -> HardwareScanJob | None:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[HardwareScanJob]:
        return sorted(self.jobs.values(), key=lambda job: job.created_at, reverse=True)

    def remember_opportunity(self, key: str, current: HardwareOpportunity) -> tuple[HardwareOpportunity, list[HardwareChangeType]]:
        previous = self.opportunities_by_key.get(key)
        changes: list[HardwareChangeType] = []
        if previous is None:
            changes.append(HardwareChangeType.NEW)
            self.opportunities_by_key[key] = current
            self._record_history(key, current)
            return current, changes

        current.opportunity_id = previous.opportunity_id
        current.first_seen_at = previous.first_seen_at
        current.last_seen_at = utc_now()
        if current.total_price != previous.total_price or current.unit_price != previous.unit_price:
            changes.append(HardwareChangeType.PRICE_CHANGED)
        if current.quantity != previous.quantity:
            changes.append(HardwareChangeType.QUANTITY_CHANGED)
        if current.status != previous.status:
            changes.append(HardwareChangeType.STATUS_CHANGED)
        if changes:
            current.last_changed_at = utc_now()
            self._record_history(key, current)
        self.opportunities_by_key[key] = current
        return current, changes

    def add_telegram_log(self, log: TelegramDeliveryLog) -> TelegramDeliveryLog:
        self.telegram_logs.append(log)
        return log

    def has_telegram_message(self, scan_job_id: UUID, report_type: str, message_hash: str) -> bool:
        return any(
            log.scan_job_id == scan_job_id
            and log.report_type == report_type
            and log.message_hash == message_hash
            and log.status.value == "sent"
            for log in self.telegram_logs
        )

    def save_scheduler_state(self, state: HardwareSchedulerState) -> HardwareSchedulerState:
        self.scheduler_state = state
        self.scheduler_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.scheduler_state_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        return state

    def _record_history(self, key: str, opportunity: HardwareOpportunity) -> None:
        self.price_history.append(
            HardwarePriceHistoryRecord(
                opportunity_key=key,
                source_url=opportunity.source_url,
                unit_price=opportunity.unit_price,
                total_price=opportunity.total_price,
                quantity=opportunity.quantity,
                status=opportunity.status.value,
            )
        )

    def _load_scheduler_state(self) -> HardwareSchedulerState:
        if not self.scheduler_state_path.exists():
            return HardwareSchedulerState()
        try:
            payload = json.loads(self.scheduler_state_path.read_text(encoding="utf-8"))
            state = HardwareSchedulerState.model_validate(payload)
            state.restored_from_disk = True
            return state
        except Exception:
            return HardwareSchedulerState(last_error="Failed to restore scheduler state from disk.")


hardware_daily_store = HardwareDailyMemoryStore()
