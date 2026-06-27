from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.hardware_daily.models import HardwareScanJob


@dataclass
class HardwarePersistenceStatus:
    mode: str
    warning: str | None = None


class HardwareDailyPersistence:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.engine: Engine | None = None
        self.status = HardwarePersistenceStatus(
            mode="memory_fallback",
            warning="DATABASE_URL is not configured; Hardware Hunter history is stored in local memory only.",
        )
        if self.settings.database_url:
            try:
                self.engine = create_engine(self.settings.database_url, pool_pre_ping=True)
                with self.engine.connect() as connection:
                    connection.execute(text("select 1"))
                self.status = HardwarePersistenceStatus(mode="postgresql", warning=None)
            except Exception as exc:
                self.engine = None
                self.status = HardwarePersistenceStatus(
                    mode="memory_fallback",
                    warning=f"PostgreSQL unavailable; using local memory fallback. {str(exc)[:180]}",
                )

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
                          status = excluded.status,
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
                    connection.execute(
                        text(
                            """
                            insert into hardware_source_runs
                              (id, scan_job_id, source_name, adapter_type, query, category, status, result_count, started_at, completed_at, error_message)
                            values
                              (:id, :scan_job_id, :source_name, :adapter_type, :query, :category, :status, :result_count, :started_at, :completed_at, :error_message)
                            on conflict (id) do update set
                              status = excluded.status,
                              result_count = excluded.result_count,
                              completed_at = excluded.completed_at,
                              error_message = excluded.error_message
                            """
                        ),
                        {
                            "id": str(run.id),
                            "scan_job_id": str(job.id),
                            "source_name": run.source_name,
                            "adapter_type": run.adapter_type,
                            "query": run.query,
                            "category": run.category.value if run.category else None,
                            "status": run.status.value,
                            "result_count": run.result_count,
                            "started_at": run.started_at,
                            "completed_at": run.completed_at,
                            "error_message": run.error_message,
                        },
                    )
                for opportunity in job.opportunities:
                    record = opportunity.model_dump(mode="json")
                    connection.execute(
                        text(
                            """
                            insert into hardware_opportunities
                              (
                                id, scan_job_id, source, source_url, canonical_url, source_listing_id, lot_number, category,
                                title, manufacturer, model, part_number, quantity, unit_price, total_price, current_price,
                                current_total_cost, cost_per_unit, cost_per_gb, cost_confidence, bid_count, condition,
                                listing_status, end_time_verification, end_time_raw, end_time_timezone_raw, end_time_utc,
                                timezone_needs_verification, next_status_check_at, status_check_attempts,
                                status_check_result, automated_result, manual_result, final_status,
                                component_completeness, recommendation, recommendation_reasons,
                                location_city, location_state, zip_code, pickup_only, shipping_available, seller_name,
                                opportunity_score, risk_score, risk_flags, needs_manual_review, last_checked_at, raw_data
                              )
                            values
                              (
                                :id, :scan_job_id, :source, :source_url, :canonical_url, :source_listing_id, :lot_number, :category,
                                :title, :manufacturer, :model, :part_number, :quantity, :unit_price, :total_price, :current_price,
                                :current_total_cost, :cost_per_unit, :cost_per_gb, :cost_confidence, :bid_count, :condition,
                                :listing_status, :end_time_verification, :end_time_raw, :end_time_timezone_raw, :end_time_utc,
                                :timezone_needs_verification, :next_status_check_at, :status_check_attempts,
                                :status_check_result, cast(:automated_result as jsonb), cast(:manual_result as jsonb), :final_status,
                                :component_completeness, :recommendation, cast(:recommendation_reasons as jsonb),
                                :location_city, :location_state, :zip_code, :pickup_only, :shipping_available, :seller_name,
                                :opportunity_score, :risk_score, cast(:risk_flags as jsonb), :needs_manual_review, :last_checked_at,
                                cast(:raw_data as jsonb)
                              )
                            on conflict (id) do update set
                              listing_status = excluded.listing_status,
                              end_time_verification = excluded.end_time_verification,
                              end_time_utc = excluded.end_time_utc,
                              next_status_check_at = excluded.next_status_check_at,
                              status_check_result = excluded.status_check_result,
                              final_status = excluded.final_status,
                              component_completeness = excluded.component_completeness,
                              recommendation = excluded.recommendation,
                              opportunity_score = excluded.opportunity_score,
                              risk_score = excluded.risk_score,
                              last_checked_at = excluded.last_checked_at,
                              raw_data = excluded.raw_data
                            """
                        ),
                        {
                            "id": str(opportunity.opportunity_id),
                            "scan_job_id": str(job.id),
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
                            "quantity": opportunity.quantity,
                            "unit_price": opportunity.unit_price,
                            "total_price": opportunity.total_price,
                            "current_price": opportunity.current_price,
                            "current_total_cost": opportunity.current_total_cost,
                            "cost_per_unit": opportunity.cost_per_unit,
                            "cost_per_gb": opportunity.cost_per_gb,
                            "cost_confidence": opportunity.cost_confidence,
                            "bid_count": opportunity.bid_count,
                            "condition": opportunity.condition.value,
                            "listing_status": opportunity.listing_status.value,
                            "end_time_verification": opportunity.end_time_verification.value,
                            "end_time_raw": opportunity.end_time_raw,
                            "end_time_timezone_raw": opportunity.end_time_timezone_raw,
                            "end_time_utc": opportunity.end_time_utc,
                            "timezone_needs_verification": opportunity.timezone_needs_verification,
                            "next_status_check_at": opportunity.next_status_check_at,
                            "status_check_attempts": opportunity.status_check_attempts,
                            "status_check_result": opportunity.status_check_result,
                            "automated_result": json.dumps(opportunity.automated_result),
                            "manual_result": json.dumps(opportunity.manual_result),
                            "final_status": opportunity.final_status.value,
                            "component_completeness": opportunity.component_completeness.value,
                            "recommendation": opportunity.recommendation.value,
                            "recommendation_reasons": json.dumps(opportunity.recommendation_reasons),
                            "location_city": opportunity.location_city,
                            "location_state": opportunity.location_state,
                            "zip_code": opportunity.zip_code,
                            "pickup_only": opportunity.pickup_only,
                            "shipping_available": opportunity.shipping_available,
                            "seller_name": opportunity.seller_name,
                            "opportunity_score": opportunity.opportunity_score,
                            "risk_score": opportunity.risk_score,
                            "risk_flags": json.dumps(opportunity.risk_flags),
                            "needs_manual_review": opportunity.needs_manual_review,
                            "last_checked_at": opportunity.last_checked_at,
                            "raw_data": json.dumps(record),
                        },
                    )
        except Exception as exc:
            self.status = HardwarePersistenceStatus(
                mode="memory_fallback",
                warning=f"PostgreSQL write failed; current run is still available in memory. {str(exc)[:180]}",
            )


hardware_daily_persistence = HardwareDailyPersistence()
