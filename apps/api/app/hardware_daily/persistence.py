from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.hardware_daily.models import (
    HardwareChangeType,
    HardwareOpportunity,
    HardwareSchedulerState,
    HardwareScanJob,
    HardwareSourceRun,
    ListingStatus,
    TelegramDeliveryLog,
    utc_now,
)


@dataclass
class HardwarePersistenceStatus:
    mode: str
    database_health: str
    database_url_configured: bool
    warning: str | None = None
    error: str | None = None
    last_successful_write_at: datetime | None = None
    migration_version: str | None = None
    stored_opportunities: int = 0
    stored_history_records: int = 0
    stored_needs_review_records: int = 0


class HardwareDailyPersistence:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.engine: Engine | None = None
        self.status = HardwarePersistenceStatus(
            mode="memory_fallback",
            database_health="not_configured",
            database_url_configured=bool(self.settings.database_url),
            warning="DATABASE_URL is not configured; Hardware Hunter history is stored in local memory only.",
        )
        if not self.settings.database_url:
            return
        try:
            connect_args = {
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000 -c lock_timeout=5000",
            }
            if self.settings.database_ssl_mode:
                connect_args["sslmode"] = self.settings.database_ssl_mode
            pool_min = max(1, self.settings.database_pool_min)
            pool_max = max(pool_min, self.settings.database_pool_max)
            self.engine = create_engine(
                self._sqlalchemy_url(self.settings.database_url),
                pool_pre_ping=True,
                pool_size=pool_min,
                max_overflow=max(0, pool_max - pool_min),
                connect_args=connect_args,
            )
            with self.engine.connect() as connection:
                connection.execute(text("select 1"))
            self._run_migrations()
            self._ensure_job_tracking_columns()
            self.status = HardwarePersistenceStatus(
                mode="postgresql",
                database_health="healthy",
                database_url_configured=True,
                migration_version=self._latest_migration_version(),
            )
            self.refresh_counts()
        except Exception as exc:
            self.engine = None
            self.status = HardwarePersistenceStatus(
                mode="memory_fallback",
                database_health="error",
                database_url_configured=True,
                warning=f"PostgreSQL unavailable; using local memory fallback. {self._safe_error(exc)[:240]}",
                error=self._safe_error(exc)[:500],
            )

    @property
    def enabled(self) -> bool:
        return self.engine is not None and self.status.mode == "postgresql"

    def create_job(self, job: HardwareScanJob) -> None:
        self.save_scan_job(job)

    def save_scan_job(self, job: HardwareScanJob) -> None:
        if not self.engine:
            return
        payload = job.model_dump(mode="json")
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        insert into hardware_scan_jobs
                          (id, mode, status, categories, states, generated_queries, quality_stats, report, error_message, created_at, updated_at, completed_at)
                        values
                          (:id, :mode, :status, cast(:categories as jsonb), cast(:states as jsonb), cast(:generated_queries as jsonb),
                           cast(:quality_stats as jsonb), cast(:report as jsonb), :error_message, :created_at, :updated_at, :completed_at)
                        on conflict (id) do update set
                          mode = excluded.mode,
                          status = excluded.status,
                          categories = excluded.categories,
                          states = excluded.states,
                          generated_queries = excluded.generated_queries,
                          quality_stats = excluded.quality_stats,
                          report = excluded.report,
                          error_message = excluded.error_message,
                          updated_at = excluded.updated_at,
                          completed_at = excluded.completed_at
                        """
                    ),
                    {
                        "id": str(job.id),
                        "mode": job.mode.value,
                        "status": job.status.value,
                        "categories": json.dumps([category.value for category in job.categories]),
                        "states": json.dumps(job.states),
                        "generated_queries": json.dumps(payload["generated_queries"]),
                        "quality_stats": json.dumps(payload["quality_stats"]),
                        "report": json.dumps(payload.get("report")),
                        "error_message": job.error_message,
                        "created_at": job.created_at,
                        "updated_at": job.updated_at,
                        "completed_at": job.completed_at,
                    },
                )
                for run in job.source_runs:
                    self._upsert_source_run(connection, job.id, run)
                for opportunity in job.opportunities:
                    self._upsert_opportunity(connection, self.identity_key(opportunity), opportunity, scan_job_id=job.id)
            self._mark_write_success()
        except Exception as exc:
            self._mark_write_error(exc)

    def remember_opportunity(
        self,
        key: str,
        current: HardwareOpportunity,
        scan_job_id: UUID | None = None,
    ) -> tuple[HardwareOpportunity, list[HardwareChangeType]]:
        if not self.engine:
            return current, [HardwareChangeType.NEW]
        identity = self.identity_key(current) or key
        try:
            with self.engine.begin() as connection:
                previous = self._load_opportunity_by_key(connection, identity)
                changes = self._detect_changes(previous, current)
                if previous:
                    current.opportunity_id = previous.opportunity_id
                    current.first_seen_at = previous.first_seen_at
                    current.first_seen_job_id = previous.first_seen_job_id
                    current.last_seen_job_id = scan_job_id or previous.last_seen_job_id
                    current.last_updated_job_id = previous.last_updated_job_id
                    current.last_seen_at = utc_now()
                    if changes:
                        current.last_changed_at = utc_now()
                        current.last_updated_job_id = scan_job_id or previous.last_updated_job_id
                else:
                    changes = [HardwareChangeType.NEW]
                    current.first_seen_job_id = scan_job_id
                    current.last_seen_job_id = scan_job_id
                    current.last_updated_job_id = scan_job_id
                self._upsert_opportunity(connection, identity, current, scan_job_id=scan_job_id)
                self._insert_snapshot(connection, current)
                self._insert_price_status_history(connection, identity, previous, current, changes)
            self._mark_write_success()
            return current, changes
        except Exception as exc:
            self._mark_write_error(exc)
            return current, [HardwareChangeType.NEW]

    def load_jobs(self) -> dict[UUID, HardwareScanJob]:
        if not self.engine:
            return {}
        try:
            with self.engine.connect() as connection:
                rows = connection.execute(
                    text("select * from hardware_scan_jobs order by created_at desc limit 100")
                ).mappings()
                jobs = {UUID(str(row["id"])): self._row_to_job(dict(row)) for row in rows}
                source_rows = connection.execute(
                    text("select * from hardware_source_runs order by started_at nulls last, completed_at nulls last")
                ).mappings()
                for row in source_rows:
                    scan_job_id = row.get("scan_job_id")
                    if scan_job_id and UUID(str(scan_job_id)) in jobs:
                        jobs[UUID(str(scan_job_id))].source_runs.append(HardwareSourceRun.model_validate(dict(row)))
                return jobs
        except Exception as exc:
            self._mark_write_error(exc)
            return {}

    def load_opportunities_by_key(self) -> dict[str, HardwareOpportunity]:
        if not self.engine:
            return {}
        try:
            with self.engine.connect() as connection:
                rows = connection.execute(
                    text("select * from hardware_opportunities order by updated_at desc")
                ).mappings()
                output: dict[str, HardwareOpportunity] = {}
                for row in rows:
                    try:
                        item = self._row_to_opportunity(dict(row))
                    except Exception:
                        continue
                    output[str(row.get("unique_key") or self.identity_key(item))] = item
                return output
        except Exception as exc:
            self._mark_write_error(exc)
            return {}

    def load_scheduler_state(self) -> HardwareSchedulerState | None:
        if not self.engine:
            return None
        try:
            with self.engine.connect() as connection:
                row = connection.execute(
                    text("select * from hardware_scheduler_state where id = 'daily_scheduler'")
                ).mappings().first()
                if not row:
                    return None
                payload = dict(row)
                payload.pop("id", None)
                payload.pop("updated_at", None)
                state = HardwareSchedulerState.model_validate(payload)
                state.restored_from_disk = True
                return state
        except Exception as exc:
            self._mark_write_error(exc)
            return None

    def save_scheduler_state(self, state: HardwareSchedulerState) -> None:
        if not self.engine:
            return
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        insert into hardware_scheduler_state
                          (id, status, enabled, is_job_running, last_run_at, next_run_at, current_job_id, last_job_id, last_error,
                           daily_report_hour, timezone, restored_from_disk, updated_at)
                        values
                          ('daily_scheduler', :status, :enabled, :is_job_running, :last_run_at, :next_run_at, :current_job_id,
                           :last_job_id, :last_error, :daily_report_hour, :timezone, :restored_from_disk, now())
                        on conflict (id) do update set
                          status = excluded.status,
                          enabled = excluded.enabled,
                          is_job_running = excluded.is_job_running,
                          last_run_at = excluded.last_run_at,
                          next_run_at = excluded.next_run_at,
                          current_job_id = excluded.current_job_id,
                          last_job_id = excluded.last_job_id,
                          last_error = excluded.last_error,
                          daily_report_hour = excluded.daily_report_hour,
                          timezone = excluded.timezone,
                          restored_from_disk = excluded.restored_from_disk,
                          updated_at = now()
                        """
                    ),
                    {
                        "status": state.status.value,
                        "enabled": state.enabled,
                        "is_job_running": state.is_job_running,
                        "last_run_at": state.last_run_at,
                        "next_run_at": state.next_run_at,
                        "current_job_id": str(state.current_job_id) if state.current_job_id else None,
                        "last_job_id": str(state.last_job_id) if state.last_job_id else None,
                        "last_error": state.last_error,
                        "daily_report_hour": state.daily_report_hour,
                        "timezone": state.timezone,
                        "restored_from_disk": state.restored_from_disk,
                    },
                )
            self._mark_write_success()
        except Exception as exc:
            self._mark_write_error(exc)

    def add_telegram_log(self, log: TelegramDeliveryLog) -> None:
        if not self.engine:
            return
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        insert into telegram_delivery_logs
                          (id, scan_job_id, report_type, message_hash, status, chat_id, telegram_message_id, error_message, sent_at, created_at)
                        values
                          (:id, :scan_job_id, :report_type, :message_hash, :status, :chat_id, :telegram_message_id, :error_message, :sent_at, :created_at)
                        on conflict (scan_job_id, report_type, message_hash) do update set
                          status = excluded.status,
                          telegram_message_id = excluded.telegram_message_id,
                          error_message = excluded.error_message,
                          sent_at = excluded.sent_at
                        """
                    ),
                    {
                        "id": str(log.id),
                        "scan_job_id": str(log.scan_job_id),
                        "report_type": log.report_type,
                        "message_hash": log.message_hash,
                        "status": log.status.value,
                        "chat_id": log.chat_id,
                        "telegram_message_id": log.telegram_message_id,
                        "error_message": log.error_message,
                        "sent_at": log.sent_at,
                        "created_at": log.created_at,
                    },
                )
            self._mark_write_success()
        except Exception as exc:
            self._mark_write_error(exc)

    def has_telegram_message(self, scan_job_id: UUID, report_type: str, message_hash: str) -> bool:
        if not self.engine:
            return False
        try:
            with self.engine.connect() as connection:
                count = connection.execute(
                    text(
                        """
                        select count(*) from telegram_delivery_logs
                        where scan_job_id = :scan_job_id
                          and report_type = :report_type
                          and message_hash = :message_hash
                          and status = 'sent'
                        """
                    ),
                    {"scan_job_id": str(scan_job_id), "report_type": report_type, "message_hash": message_hash},
                ).scalar_one()
                return bool(count)
        except Exception as exc:
            self._mark_write_error(exc)
            return False

    def refresh_counts(self) -> None:
        if not self.engine:
            return
        try:
            with self.engine.connect() as connection:
                self.status.stored_opportunities = int(connection.execute(text("select count(*) from hardware_opportunities")).scalar_one())
                self.status.stored_history_records = int(
                    connection.execute(
                        text(
                            """
                            select count(*) from hardware_opportunities
                            where listing_status in ('ended', 'sold', 'removed', 'unavailable')
                               or (end_time_utc is not null and end_time_utc <= now())
                            """
                        )
                    ).scalar_one()
                )
                self.status.stored_needs_review_records = int(
                    connection.execute(
                        text(
                            """
                            select count(*) from hardware_opportunities
                            where needs_manual_review = true
                               or listing_status = 'needs_manual_review'
                               or end_time_verification = 'conflicting'
                            """
                        )
                    ).scalar_one()
                )
                self.status.migration_version = self._latest_migration_version(connection=connection)
        except Exception as exc:
            self._mark_write_error(exc)

    def identity_key(self, opportunity: HardwareOpportunity) -> str:
        source = self._norm(opportunity.source)
        if opportunity.source_listing_id:
            return f"{source}:listing:{self._norm(opportunity.source_listing_id)}"
        if opportunity.lot_number:
            return f"{source}:lot:{self._norm(opportunity.lot_number)}"
        canonical_url = opportunity.canonical_url or opportunity.source_url
        if canonical_url:
            return f"url:{self._normalize_url(canonical_url)}"
        text_key = "|".join(
            self._norm(part)
            for part in [
                opportunity.title,
                opportunity.seller_name or "",
                opportunity.location_city or "",
                opportunity.location_state or "",
            ]
            if part
        )
        return f"text:{text_key}"

    def _run_migrations(self) -> None:
        if not self.engine:
            return
        migration_dir = Path(__file__).resolve().parents[4] / "supabase" / "migrations"
        files = sorted(migration_dir.glob("*hardware*.sql"))
        with self.engine.begin() as connection:
            connection.exec_driver_sql("create extension if not exists pgcrypto")
            connection.exec_driver_sql(
                "create table if not exists schema_migrations (version text primary key, applied_at timestamptz not null default now())"
            )

        with self.engine.connect() as connection:
            applied_versions = {
                row[0]
                for row in connection.execute(text("select version from schema_migrations")).all()
            }

        legacy_schema_ready = "20260701_hardware_hunter_v23_persistence" in applied_versions

        for path in files:
            if path.stem in applied_versions:
                continue
            with self.engine.begin() as connection:
                if not legacy_schema_ready:
                    self._repair_schema_for_legacy_tables(connection)
                sql = path.read_text(encoding="utf-8")
                for statement in self._split_sql(sql):
                    connection.exec_driver_sql(statement)
                if not legacy_schema_ready:
                    self._repair_schema_for_legacy_tables(connection)
                connection.execute(
                    text("insert into schema_migrations(version) values (:version) on conflict (version) do nothing"),
                    {"version": path.stem},
                )
                if path.stem == "20260701_hardware_hunter_v23_persistence":
                    legacy_schema_ready = True

    def _ensure_job_tracking_columns(self) -> None:
        if not self.engine:
            return
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                """
                alter table hardware_opportunities
                  add column if not exists first_seen_job_id uuid,
                  add column if not exists last_seen_job_id uuid,
                  add column if not exists last_updated_job_id uuid;

                update hardware_opportunities
                set
                  first_seen_job_id = coalesce(first_seen_job_id, scan_job_id),
                  last_seen_job_id = coalesce(last_seen_job_id, scan_job_id),
                  last_updated_job_id = coalesce(last_updated_job_id, scan_job_id)
                where scan_job_id is not null
                  and (first_seen_job_id is null or last_seen_job_id is null or last_updated_job_id is null);

                alter table manual_verification_records
                  add column if not exists previous_status text,
                  add column if not exists review_action text,
                  add column if not exists manual_fields_json jsonb not null default '{}'::jsonb,
                  add column if not exists notes text,
                  add column if not exists reviewed_by text,
                  add column if not exists reviewed_at timestamptz;

                alter table hardware_source_runs
                  add column if not exists expanded_query text,
                  add column if not exists query_template_id text,
                  add column if not exists query_template text,
                  add column if not exists state_code text,
                  add column if not exists state_name text,
                  add column if not exists scan_depth text not null default 'standard',
                  add column if not exists specific_listing_count integer not null default 0,
                  add column if not exists zero_result_reason text;
                """
            )

    def _upsert_source_run(self, connection, job_id: UUID, run: HardwareSourceRun) -> None:
        connection.execute(
            text(
                """
                insert into hardware_source_runs
                  (id, scan_job_id, source_name, adapter_type, query, expanded_query, query_template_id, query_template, state_code,
                   state_name, scan_depth, category, status, result_count, specific_listing_count, zero_result_reason,
                   started_at, completed_at, error_message)
                values
                  (:id, :scan_job_id, :source_name, :adapter_type, :query, :expanded_query, :query_template_id, :query_template,
                   :state_code, :state_name, :scan_depth, :category, :status, :result_count, :specific_listing_count,
                   :zero_result_reason, :started_at, :completed_at, :error_message)
                on conflict (id) do update set
                  scan_job_id = excluded.scan_job_id,
                  status = excluded.status,
                  result_count = excluded.result_count,
                  specific_listing_count = excluded.specific_listing_count,
                  zero_result_reason = excluded.zero_result_reason,
                  completed_at = excluded.completed_at,
                  error_message = excluded.error_message
                """
            ),
            {
                "id": str(run.id),
                "scan_job_id": str(job_id),
                "source_name": run.source_name,
                "adapter_type": run.adapter_type,
                "query": run.query,
                "expanded_query": run.expanded_query,
                "query_template_id": run.query_template_id,
                "query_template": run.query_template,
                "state_code": run.state_code,
                "state_name": run.state_name,
                "scan_depth": run.scan_depth.value,
                "category": run.category.value if run.category else None,
                "status": run.status.value,
                "result_count": run.result_count,
                "specific_listing_count": run.specific_listing_count,
                "zero_result_reason": run.zero_result_reason.value if run.zero_result_reason else None,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "error_message": run.error_message,
            },
        )

    def _upsert_opportunity(self, connection, unique_key: str, opportunity: HardwareOpportunity, scan_job_id: UUID | None = None) -> None:
        payload = opportunity.model_dump(mode="json")
        connection.execute(
            text(
                """
                insert into hardware_opportunities
                  (
                    id, scan_job_id, first_seen_job_id, last_seen_job_id, last_updated_job_id,
                    unique_key, source, source_url, canonical_url, source_listing_id, lot_number, category,
                    title, manufacturer, model, part_number, generation, configuration, quantity, quantity_status,
                    unit_price, total_price, current_price, current_total_cost, buyer_premium, buyer_premium_amount,
                    estimated_tax, estimated_shipping, estimated_landed_cost, cost_per_unit, cost_per_gb, cost_confidence,
                    bid_count, condition, working_status, testing_status, warranty_status, location_city, location_state,
                    zip_code, pickup_only, shipping_available, auction_end_time, seller_name, seller_type,
                    listing_status, end_time_verification, end_time_raw, end_time_timezone_raw, end_time_utc,
                    end_time_user_timezone, timezone_needs_verification, countdown_raw_text, countdown_captured_at,
                    calculated_end_time, calculated_timezone, calculation_confidence, last_status_check_at,
                    next_status_check_at, status_check_attempts, status_check_result, status_check_error,
                    automated_result, manual_result, final_status, manual_end_time, manual_timezone, manual_status,
                    manual_notes, verified_by, verified_at, page_type, classification_reason, status,
                    component_completeness, component_details, recommendation, recommendation_reasons,
                    last_checked_at, unavailable_reason, needs_manual_review, confidence_level, risk_flags,
                    change_types, opportunity_score, risk_score, score_reasons, raw_title, raw_description,
                    raw_data_json, raw_data, first_seen_at, last_seen_at, last_changed_at, updated_at
                  )
                values
                  (
                    :id, :scan_job_id, :first_seen_job_id, :last_seen_job_id, :last_updated_job_id,
                    :unique_key, :source, :source_url, :canonical_url, :source_listing_id, :lot_number, :category,
                    :title, :manufacturer, :model, :part_number, :generation, :configuration, :quantity, :quantity_status,
                    :unit_price, :total_price, :current_price, :current_total_cost, :buyer_premium, :buyer_premium_amount,
                    :estimated_tax, :estimated_shipping, :estimated_landed_cost, :cost_per_unit, :cost_per_gb, :cost_confidence,
                    :bid_count, :condition, :working_status, :testing_status, :warranty_status, :location_city, :location_state,
                    :zip_code, :pickup_only, :shipping_available, :auction_end_time, :seller_name, :seller_type,
                    :listing_status, :end_time_verification, :end_time_raw, :end_time_timezone_raw, :end_time_utc,
                    :end_time_user_timezone, :timezone_needs_verification, :countdown_raw_text, :countdown_captured_at,
                    :calculated_end_time, :calculated_timezone, :calculation_confidence, :last_status_check_at,
                    :next_status_check_at, :status_check_attempts, :status_check_result, :status_check_error,
                    cast(:automated_result as jsonb), cast(:manual_result as jsonb), :final_status, :manual_end_time, :manual_timezone, :manual_status,
                    :manual_notes, :verified_by, :verified_at, :page_type, :classification_reason, :status,
                    :component_completeness, cast(:component_details as jsonb), :recommendation, cast(:recommendation_reasons as jsonb),
                    :last_checked_at, :unavailable_reason, :needs_manual_review, :confidence_level, cast(:risk_flags as jsonb),
                    cast(:change_types as jsonb), :opportunity_score, :risk_score, cast(:score_reasons as jsonb), :raw_title, :raw_description,
                    cast(:raw_data_json as jsonb), cast(:raw_data as jsonb), :first_seen_at, :last_seen_at, :last_changed_at, now()
                  )
                on conflict (unique_key) where unique_key is not null do update set
                  scan_job_id = coalesce(excluded.scan_job_id, hardware_opportunities.scan_job_id),
                  first_seen_job_id = coalesce(hardware_opportunities.first_seen_job_id, excluded.first_seen_job_id),
                  last_seen_job_id = coalesce(excluded.last_seen_job_id, hardware_opportunities.last_seen_job_id),
                  last_updated_job_id = case
                    when excluded.last_changed_at is not null then coalesce(excluded.last_updated_job_id, hardware_opportunities.last_updated_job_id)
                    else hardware_opportunities.last_updated_job_id
                  end,
                  source_url = excluded.source_url,
                  canonical_url = excluded.canonical_url,
                  title = excluded.title,
                  manufacturer = excluded.manufacturer,
                  model = excluded.model,
                  part_number = excluded.part_number,
                  quantity = excluded.quantity,
                  unit_price = excluded.unit_price,
                  total_price = excluded.total_price,
                  current_price = excluded.current_price,
                  current_total_cost = excluded.current_total_cost,
                  bid_count = excluded.bid_count,
                  listing_status = excluded.listing_status,
                  end_time_verification = excluded.end_time_verification,
                  end_time_utc = excluded.end_time_utc,
                  next_status_check_at = excluded.next_status_check_at,
                  status_check_attempts = excluded.status_check_attempts,
                  status_check_result = excluded.status_check_result,
                  status_check_error = excluded.status_check_error,
                  automated_result = excluded.automated_result,
                  manual_result = excluded.manual_result,
                  final_status = excluded.final_status,
                  component_completeness = excluded.component_completeness,
                  component_details = excluded.component_details,
                  recommendation = excluded.recommendation,
                  recommendation_reasons = excluded.recommendation_reasons,
                  last_checked_at = excluded.last_checked_at,
                  unavailable_reason = excluded.unavailable_reason,
                  needs_manual_review = excluded.needs_manual_review,
                  confidence_level = excluded.confidence_level,
                  risk_flags = excluded.risk_flags,
                  change_types = excluded.change_types,
                  opportunity_score = excluded.opportunity_score,
                  risk_score = excluded.risk_score,
                  score_reasons = excluded.score_reasons,
                  raw_data_json = excluded.raw_data_json,
                  raw_data = excluded.raw_data,
                  last_seen_at = excluded.last_seen_at,
                  last_changed_at = excluded.last_changed_at,
                  updated_at = now()
                """
            ),
            self._opportunity_params(unique_key, opportunity, payload, scan_job_id),
        )

    def _insert_snapshot(self, connection, opportunity: HardwareOpportunity) -> None:
        connection.execute(
            text(
                """
                insert into hardware_listing_snapshots
                  (opportunity_id, listing_status, quantity, unit_price, total_price, current_price, bid_count, raw_data, checked_at)
                values
                  (:opportunity_id, :listing_status, :quantity, :unit_price, :total_price, :current_price, :bid_count, cast(:raw_data as jsonb), :checked_at)
                """
            ),
            {
                "opportunity_id": str(opportunity.opportunity_id),
                "listing_status": opportunity.listing_status.value,
                "quantity": opportunity.quantity,
                "unit_price": opportunity.unit_price,
                "total_price": opportunity.total_price,
                "current_price": opportunity.current_price,
                "bid_count": opportunity.bid_count,
                "raw_data": json.dumps(opportunity.model_dump(mode="json")),
                "checked_at": opportunity.last_checked_at or utc_now(),
            },
        )

    def _insert_price_status_history(
        self,
        connection,
        identity: str,
        previous: HardwareOpportunity | None,
        current: HardwareOpportunity,
        changes: list[HardwareChangeType],
    ) -> None:
        if previous is None or HardwareChangeType.PRICE_CHANGED in changes or HardwareChangeType.QUANTITY_CHANGED in changes:
            connection.execute(
                text(
                    """
                    insert into hardware_price_history
                      (opportunity_id, opportunity_key, source_url, unit_price, total_price, quantity, status,
                       old_unit_price, new_unit_price, old_total_price, new_total_price, listing_status, observed_at)
                    values
                      (:opportunity_id, :opportunity_key, :source_url, :unit_price, :total_price, :quantity, :status,
                       :old_unit_price, :new_unit_price, :old_total_price, :new_total_price, :listing_status, :observed_at)
                    """
                ),
                {
                    "opportunity_id": str(current.opportunity_id),
                    "opportunity_key": identity,
                    "source_url": current.source_url,
                    "unit_price": current.unit_price,
                    "total_price": current.total_price,
                    "quantity": current.quantity,
                    "status": current.status.value,
                    "old_unit_price": previous.unit_price if previous else None,
                    "new_unit_price": current.unit_price,
                    "old_total_price": previous.total_price if previous else None,
                    "new_total_price": current.total_price,
                    "listing_status": current.listing_status.value,
                    "observed_at": utc_now(),
                },
            )
        if previous is None or any(change in changes for change in [HardwareChangeType.STATUS_CHANGED, HardwareChangeType.RELISTED]):
            connection.execute(
                text(
                    """
                    insert into hardware_status_history
                      (opportunity_id, old_status, new_status, old_end_time, new_end_time, change_type, source, raw_data)
                    values
                      (:opportunity_id, :old_status, :new_status, :old_end_time, :new_end_time, :change_type, :source, cast(:raw_data as jsonb))
                    """
                ),
                {
                    "opportunity_id": str(current.opportunity_id),
                    "old_status": previous.listing_status.value if previous else None,
                    "new_status": current.listing_status.value,
                    "old_end_time": previous.end_time_utc if previous else None,
                    "new_end_time": current.end_time_utc,
                    "change_type": ",".join(change.value for change in changes),
                    "source": current.source,
                    "raw_data": json.dumps(current.model_dump(mode="json")),
                },
            )
        if current.manual_result:
                connection.execute(
                    text(
                        """
                        insert into manual_verification_records
                          (opportunity_id, previous_status, manual_status, review_action, manual_fields_json,
                           manual_end_time, manual_timezone, manual_notes, notes, verified_by, reviewed_by, verified_at, reviewed_at, raw_data)
                        values
                          (:opportunity_id, :previous_status, :manual_status, :review_action, cast(:manual_fields_json as jsonb),
                           :manual_end_time, :manual_timezone, :manual_notes, :notes, :verified_by, :reviewed_by, :verified_at, :reviewed_at, cast(:raw_data as jsonb))
                        """
                    ),
                    {
                        "opportunity_id": str(current.opportunity_id),
                        "previous_status": current.manual_result.get("previous_status"),
                        "manual_status": current.manual_status.value if current.manual_status else None,
                        "review_action": current.review_action,
                        "manual_fields_json": json.dumps(
                            {
                                "manual_quantity": current.manual_quantity,
                                "manual_current_price": current.manual_current_price,
                                "manual_total_price": current.manual_total_price,
                                "manual_location": current.manual_location,
                                "manual_condition": current.manual_condition,
                                "manual_component_completeness": current.manual_component_completeness,
                                "final_status": current.final_status.value,
                                "final_end_time": current.final_end_time.isoformat() if current.final_end_time else None,
                                "final_price": current.final_price,
                                "final_quantity": current.final_quantity,
                            }
                        ),
                        "manual_end_time": current.manual_end_time,
                        "manual_timezone": current.manual_timezone,
                        "manual_notes": current.manual_notes,
                        "notes": current.review_notes or current.manual_notes,
                        "verified_by": current.verified_by,
                        "reviewed_by": current.reviewed_by or current.verified_by,
                        "verified_at": current.verified_at,
                        "reviewed_at": current.reviewed_at or current.verified_at,
                        "raw_data": json.dumps(current.manual_result),
                    },
                )

    def _detect_changes(self, previous: HardwareOpportunity | None, current: HardwareOpportunity) -> list[HardwareChangeType]:
        if previous is None:
            return [HardwareChangeType.NEW]
        changes: list[HardwareChangeType] = []
        if current.total_price != previous.total_price or current.unit_price != previous.unit_price or current.current_price != previous.current_price:
            changes.append(HardwareChangeType.PRICE_CHANGED)
        if current.quantity != previous.quantity:
            changes.append(HardwareChangeType.QUANTITY_CHANGED)
        if current.status != previous.status or current.listing_status != previous.listing_status:
            changes.append(HardwareChangeType.STATUS_CHANGED)
        if current.end_time_utc != previous.end_time_utc:
            changes.append(HardwareChangeType.END_TIME_CHANGED)
        enriched_fields = ["model", "manufacturer", "part_number", "quantity", "location_city", "location_state"]
        if any(getattr(previous, field) in {None, "", "unknown"} and getattr(current, field) not in {None, "", "unknown"} for field in enriched_fields):
            changes.append(HardwareChangeType.DETAILS_ENRICHED)
        if previous.listing_status in {ListingStatus.ENDED, ListingStatus.SOLD, ListingStatus.REMOVED} and current.listing_status in {ListingStatus.ACTIVE, ListingStatus.ENDING_SOON}:
            changes.append(HardwareChangeType.RELISTED)
        return list(dict.fromkeys(changes))

    def _load_opportunity_by_key(self, connection, identity: str) -> HardwareOpportunity | None:
        row = connection.execute(
            text("select * from hardware_opportunities where unique_key = :unique_key"),
            {"unique_key": identity},
        ).mappings().first()
        return self._row_to_opportunity(dict(row)) if row else None

    def _row_to_job(self, row: dict) -> HardwareScanJob:
        payload = {
            "id": row["id"],
            "mode": row["mode"],
            "status": row["status"],
            "categories": self._json_value(row.get("categories"), []),
            "states": self._json_value(row.get("states"), []),
            "generated_queries": self._json_value(row.get("generated_queries"), []),
            "source_runs": [],
            "opportunities": [],
            "quality_stats": self._json_value(row.get("quality_stats"), {}),
            "report": self._json_value(row.get("report"), None),
            "error_message": row.get("error_message"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "completed_at": row.get("completed_at"),
        }
        return HardwareScanJob.model_validate(payload)

    def _row_to_opportunity(self, row: dict) -> HardwareOpportunity:
        payload = self._json_value(row.get("raw_data"), {}) or self._json_value(row.get("raw_data_json"), {}) or {}
        if "opportunity_id" not in payload:
            payload["opportunity_id"] = row.get("id")
        column_map = {
            "id": "opportunity_id",
            "raw_data_json": "raw_data_json",
        }
        for key, value in row.items():
            if value is None or key in {"raw_data", "unique_key", "scan_job_id", "created_at", "updated_at"}:
                continue
            payload[column_map.get(key, key)] = self._json_value(value, value)
        for field_name in [
            "source_listing_id",
            "lot_number",
            "source_url",
            "canonical_url",
            "title",
            "raw_title",
            "source",
            "manufacturer",
            "model",
            "part_number",
            "location_city",
            "location_state",
            "zip_code",
            "seller_name",
        ]:
            if payload.get(field_name) is not None:
                payload[field_name] = str(payload[field_name])
        return HardwareOpportunity.model_validate(payload)

    def _opportunity_params(self, unique_key: str, opportunity: HardwareOpportunity, payload: dict, scan_job_id: UUID | None) -> dict:
        first_seen_job_id = opportunity.first_seen_job_id or scan_job_id
        last_seen_job_id = scan_job_id or opportunity.last_seen_job_id
        last_updated_job_id = scan_job_id if opportunity.last_changed_at else opportunity.last_updated_job_id
        return {
            "id": str(opportunity.opportunity_id),
            "scan_job_id": str(scan_job_id) if scan_job_id else None,
            "first_seen_job_id": str(first_seen_job_id) if first_seen_job_id else None,
            "last_seen_job_id": str(last_seen_job_id) if last_seen_job_id else None,
            "last_updated_job_id": str(last_updated_job_id) if last_updated_job_id else None,
            "unique_key": unique_key,
            "source": opportunity.source,
            "source_url": opportunity.source_url,
            "canonical_url": opportunity.canonical_url,
            "source_listing_id": opportunity.source_listing_id,
            "lot_number": opportunity.lot_number,
            "category": opportunity.category.value,
            "title": opportunity.title,
            "manufacturer": opportunity.manufacturer,
            "model": opportunity.model,
            "part_number": opportunity.part_number,
            "generation": opportunity.generation,
            "configuration": opportunity.configuration,
            "quantity": opportunity.quantity,
            "quantity_status": opportunity.quantity_status,
            "unit_price": opportunity.unit_price,
            "total_price": opportunity.total_price,
            "current_price": opportunity.current_price,
            "current_total_cost": opportunity.current_total_cost,
            "buyer_premium": opportunity.buyer_premium,
            "buyer_premium_amount": opportunity.buyer_premium_amount,
            "estimated_tax": opportunity.estimated_tax,
            "estimated_shipping": opportunity.estimated_shipping,
            "estimated_landed_cost": opportunity.estimated_landed_cost,
            "cost_per_unit": opportunity.cost_per_unit,
            "cost_per_gb": opportunity.cost_per_gb,
            "cost_confidence": opportunity.cost_confidence,
            "bid_count": opportunity.bid_count,
            "condition": opportunity.condition.value,
            "working_status": opportunity.working_status,
            "testing_status": opportunity.testing_status,
            "warranty_status": opportunity.warranty_status,
            "location_city": opportunity.location_city,
            "location_state": opportunity.location_state,
            "zip_code": opportunity.zip_code,
            "pickup_only": opportunity.pickup_only,
            "shipping_available": opportunity.shipping_available,
            "auction_end_time": opportunity.auction_end_time,
            "seller_name": opportunity.seller_name,
            "seller_type": opportunity.seller_type,
            "listing_status": opportunity.listing_status.value,
            "end_time_verification": opportunity.end_time_verification.value,
            "end_time_raw": opportunity.end_time_raw,
            "end_time_timezone_raw": opportunity.end_time_timezone_raw,
            "end_time_utc": opportunity.end_time_utc,
            "end_time_user_timezone": opportunity.end_time_user_timezone,
            "timezone_needs_verification": opportunity.timezone_needs_verification,
            "countdown_raw_text": opportunity.countdown_raw_text,
            "countdown_captured_at": opportunity.countdown_captured_at,
            "calculated_end_time": opportunity.calculated_end_time,
            "calculated_timezone": opportunity.calculated_timezone,
            "calculation_confidence": opportunity.calculation_confidence,
            "last_status_check_at": opportunity.last_status_check_at,
            "next_status_check_at": opportunity.next_status_check_at,
            "status_check_attempts": opportunity.status_check_attempts,
            "status_check_result": opportunity.status_check_result,
            "status_check_error": opportunity.status_check_error,
            "automated_result": json.dumps(opportunity.automated_result),
            "manual_result": json.dumps(opportunity.manual_result),
            "final_status": opportunity.final_status.value,
            "manual_end_time": opportunity.manual_end_time,
            "manual_timezone": opportunity.manual_timezone,
            "manual_status": opportunity.manual_status.value if opportunity.manual_status else None,
            "manual_notes": opportunity.manual_notes,
            "verified_by": opportunity.verified_by,
            "verified_at": opportunity.verified_at,
            "page_type": opportunity.page_type.value,
            "classification_reason": opportunity.classification_reason,
            "status": opportunity.status.value,
            "component_completeness": opportunity.component_completeness.value,
            "component_details": json.dumps(opportunity.component_details),
            "recommendation": opportunity.recommendation.value,
            "recommendation_reasons": json.dumps(opportunity.recommendation_reasons or []),
            "last_checked_at": opportunity.last_checked_at,
            "unavailable_reason": opportunity.unavailable_reason,
            "needs_manual_review": opportunity.needs_manual_review,
            "confidence_level": opportunity.confidence_level.value,
            "risk_flags": json.dumps(opportunity.risk_flags or []),
            "change_types": json.dumps([change.value if hasattr(change, "value") else str(change) for change in (opportunity.change_types or [])]),
            "opportunity_score": opportunity.opportunity_score,
            "risk_score": opportunity.risk_score,
            "score_reasons": json.dumps(opportunity.score_reasons or []),
            "raw_title": opportunity.raw_title,
            "raw_description": opportunity.raw_description,
            "raw_data_json": json.dumps(opportunity.raw_data_json),
            "raw_data": json.dumps(payload),
            "first_seen_at": opportunity.first_seen_at,
            "last_seen_at": opportunity.last_seen_at,
            "last_changed_at": opportunity.last_changed_at,
        }

    def _latest_migration_version(self, connection=None) -> str | None:
        if not self.engine:
            return None
        try:
            if connection is not None:
                return connection.execute(text("select version from schema_migrations order by version desc limit 1")).scalar_one_or_none()
            with self.engine.connect() as conn:
                return conn.execute(text("select version from schema_migrations order by version desc limit 1")).scalar_one_or_none()
        except Exception:
            return None

    def _mark_write_success(self) -> None:
        self.status.last_successful_write_at = utc_now()
        self.status.mode = "postgresql"
        self.status.database_health = "healthy"
        self.status.warning = None
        self.status.error = None
        self.refresh_counts()

    def _mark_write_error(self, exc: Exception) -> None:
        self.status.database_health = "error"
        safe_error = self._safe_error(exc)
        self.status.warning = f"PostgreSQL write/read failed; using in-memory state for this operation. {safe_error[:240]}"
        self.status.error = safe_error[:500]

    def _split_sql(self, sql: str) -> list[str]:
        return [statement.strip() for statement in sql.split(";") if statement.strip()]

    def _repair_schema_for_legacy_tables(self, connection) -> None:
        connection.exec_driver_sql(
            """
            do $$
            begin
              if to_regclass('public.hardware_scan_jobs') is not null then
                alter table hardware_scan_jobs
                  add column if not exists generated_queries jsonb not null default '[]'::jsonb,
                  add column if not exists scheduler_state jsonb;
              end if;

              if to_regclass('public.hardware_opportunities') is not null then
                alter table hardware_opportunities
                  add column if not exists scan_job_id uuid,
                  add column if not exists first_seen_job_id uuid,
                  add column if not exists last_seen_job_id uuid,
                  add column if not exists last_updated_job_id uuid,
                  add column if not exists subcategory text,
                  add column if not exists canonical_url text,
                  add column if not exists unique_key text,
                  add column if not exists source_listing_id text,
                  add column if not exists lot_number text,
                  add column if not exists generation text,
                  add column if not exists configuration text,
                  add column if not exists quantity_status text not null default 'unknown',
                  add column if not exists current_price numeric,
                  add column if not exists current_total_cost numeric,
                  add column if not exists buyer_premium text,
                  add column if not exists buyer_premium_amount numeric,
                  add column if not exists estimated_tax numeric,
                  add column if not exists estimated_shipping numeric,
                  add column if not exists estimated_landed_cost numeric,
                  add column if not exists cost_per_unit numeric,
                  add column if not exists cost_per_gb numeric,
                  add column if not exists cost_confidence text not null default 'unknown',
                  add column if not exists bid_count integer,
                  add column if not exists condition text not null default 'unknown',
                  add column if not exists working_status text not null default 'unknown',
                  add column if not exists testing_status text not null default 'unknown',
                  add column if not exists warranty_status text not null default 'unknown',
                  add column if not exists listing_status text not null default 'unknown',
                  add column if not exists end_time_verification text not null default 'unknown',
                  add column if not exists end_time_raw text,
                  add column if not exists end_time_timezone_raw text,
                  add column if not exists end_time_utc timestamptz,
                  add column if not exists end_time_user_timezone text,
                  add column if not exists timezone_needs_verification boolean not null default false,
                  add column if not exists countdown_raw_text text,
                  add column if not exists countdown_captured_at timestamptz,
                  add column if not exists calculated_end_time timestamptz,
                  add column if not exists calculated_timezone text,
                  add column if not exists calculation_confidence text,
                  add column if not exists last_status_check_at timestamptz,
                  add column if not exists next_status_check_at timestamptz,
                  add column if not exists status_check_attempts integer not null default 0,
                  add column if not exists status_check_result text,
                  add column if not exists status_check_error text,
                  add column if not exists automated_result jsonb not null default '{}'::jsonb,
                  add column if not exists manual_result jsonb not null default '{}'::jsonb,
                  add column if not exists final_status text not null default 'unknown',
                  add column if not exists manual_end_time timestamptz,
                  add column if not exists manual_timezone text,
                  add column if not exists manual_status text,
                  add column if not exists manual_notes text,
                  add column if not exists verified_by text,
                  add column if not exists verified_at timestamptz,
                  add column if not exists page_type text not null default 'specific_listing',
                  add column if not exists classification_reason text,
                  add column if not exists component_completeness text not null default 'unknown',
                  add column if not exists component_details jsonb not null default '{}'::jsonb,
                  add column if not exists recommendation text not null default 'information_incomplete',
                  add column if not exists recommendation_reasons jsonb not null default '[]'::jsonb,
                  add column if not exists last_checked_at timestamptz,
                  add column if not exists unavailable_reason text,
                  add column if not exists needs_manual_review boolean not null default false,
                  add column if not exists confidence_level text not null default 'needs_verification',
                  add column if not exists change_types jsonb not null default '[]'::jsonb,
                  add column if not exists score_reasons jsonb not null default '[]'::jsonb,
                  add column if not exists raw_title text,
                  add column if not exists raw_description text,
                  add column if not exists raw_data_json jsonb not null default '{}'::jsonb,
                  add column if not exists raw_data jsonb not null default '{}'::jsonb;
              end if;

              if to_regclass('public.telegram_delivery_logs') is not null then
                alter table telegram_delivery_logs
                  add column if not exists telegram_message_id text;
              end if;
            end $$;
            """
        )

    def _sqlalchemy_url(self, database_url: str) -> str:
        if database_url.startswith("postgresql://"):
            return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return database_url

    def _safe_error(self, exc: Exception) -> str:
        message = str(exc)
        if self.settings.database_url:
            message = message.replace(self.settings.database_url, "[DATABASE_URL_REDACTED]")
        message = re.sub(r"(postgres(?:ql)?(?:\\+psycopg)?://[^:\\s/]+:)([^@\\s]+)(@)", r"\\1[REDACTED]\\3", message)
        return message

    def _json_value(self, value, fallback):
        if value is None:
            return fallback
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    def _normalize_url(self, url: str) -> str:
        cleaned = url.strip()
        cleaned = re.sub(r"([?&])(utm_[^=&]+|fbclid|gclid|msclkid)=[^&]+", "", cleaned, flags=re.I)
        cleaned = cleaned.split("#", 1)[0]
        return cleaned.rstrip("/").lower()

    def _norm(self, value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())


hardware_daily_persistence = HardwareDailyPersistence()
