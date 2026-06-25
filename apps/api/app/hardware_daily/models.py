from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HardwareScanJobStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    FAILED = "failed"


class HardwareSourceRunStatus(str, Enum):
    PENDING = "pending"
    SEARCHING = "searching"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    DISABLED = "disabled"


class HardwareScanMode(str, Enum):
    ASSET_LISTING_SEARCH = "asset_listing_search"
    SUPPLIER_LEAD_SEARCH = "supplier_lead_search"
    BOTH = "both"


class HardwareCategory(str, Enum):
    SERVERS = "servers"
    GPU = "gpu"
    MEMORY = "memory"
    STORAGE = "storage"
    CPU = "cpu"


class HardwareCondition(str, Enum):
    NEW = "new"
    OPEN_BOX = "open_box"
    USED_WORKING = "used_working"
    REFURBISHED = "refurbished"
    TESTED = "tested"
    UNTESTED = "untested"
    CUSTOMER_RETURN = "customer_return"
    SALVAGE = "salvage"
    PARTS_ONLY = "parts_only"
    BROKEN = "broken"
    UNKNOWN = "unknown"


class OpportunityStatus(str, Enum):
    ACTIVE = "active"
    ENDED = "ended"
    SOLD = "sold"
    NEEDS_VERIFICATION = "needs_verification"


class ConfidenceLevel(str, Enum):
    OFFICIAL_SOURCE = "official_source"
    MARKETPLACE_LISTING = "marketplace_listing"
    PUBLIC_SEARCH_DISCOVERY = "public_search_discovery"
    NEEDS_VERIFICATION = "needs_verification"
    UNKNOWN = "unknown"


class HardwareChangeType(str, Enum):
    NEW = "NEW"
    PRICE_CHANGED = "PRICE_CHANGED"
    QUANTITY_CHANGED = "QUANTITY_CHANGED"
    STATUS_CHANGED = "STATUS_CHANGED"
    AUCTION_ENDING = "AUCTION_ENDING"
    RELISTED = "RELISTED"
    SUPPLIER_DISCOVERED = "SUPPLIER_DISCOVERED"


class HardwareResultPageType(str, Enum):
    SPECIFIC_LISTING = "specific_listing"
    LISTING_COLLECTION = "listing_collection"
    SOURCE_PAGE = "source_page"
    NEWS_OR_ARTICLE = "news_or_article"
    IRRELEVANT = "irrelevant"


class HardwareScanRequest(BaseModel):
    mode: HardwareScanMode = HardwareScanMode.BOTH
    categories: list[HardwareCategory] = Field(default_factory=list)
    states: list[str] = Field(default_factory=list)
    test_run: bool = True
    max_results_per_query: int = Field(default=4, ge=1, le=20)
    max_queries_per_category: int = Field(default=8, ge=1, le=40)
    send_telegram: bool = False
    manual_urls: list[HttpUrl] = Field(default_factory=list)
    manual_text: str | None = None


class HardwareGeneratedQuery(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    category: HardwareCategory
    source_group: str
    generated_query_en: str
    status: HardwareSourceRunStatus = HardwareSourceRunStatus.PENDING
    result_count: int = 0


class HardwareSourceRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_name: str
    adapter_type: str
    query: str | None = None
    category: HardwareCategory | None = None
    status: HardwareSourceRunStatus = HardwareSourceRunStatus.PENDING
    result_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class RawHardwareListing(BaseModel):
    source_name: str
    source_url: str
    original_title: str
    original_description: str | None = None
    category: HardwareCategory
    source_listing_id: str | None = None
    seller_name: str | None = None
    page_type: HardwareResultPageType = HardwareResultPageType.IRRELEVANT
    classification_reason: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=utc_now)


class HardwareOpportunity(BaseModel):
    opportunity_id: UUID = Field(default_factory=uuid4)
    category: HardwareCategory
    subcategory: str | None = None
    title: str
    manufacturer: str | None = None
    model: str | None = None
    part_number: str | None = None
    generation: str | None = None
    configuration: str | None = None
    quantity: int | None = None
    quantity_status: str = "unknown"
    unit_price: float | None = None
    total_price: float | None = None
    condition: HardwareCondition = HardwareCondition.UNKNOWN
    working_status: str = "unknown"
    testing_status: str = "unknown"
    warranty_status: str = "unknown"
    location_city: str | None = None
    location_state: str | None = None
    zip_code: str | None = None
    pickup_only: bool | None = None
    shipping_available: bool | None = None
    auction_end_time: datetime | None = None
    seller_name: str | None = None
    seller_type: str = "unknown"
    source: str
    source_url: str
    canonical_url: str | None = None
    source_listing_id: str | None = None
    page_type: HardwareResultPageType = HardwareResultPageType.SPECIFIC_LISTING
    classification_reason: str | None = None
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)
    last_changed_at: datetime | None = None
    status: OpportunityStatus = OpportunityStatus.NEEDS_VERIFICATION
    confidence_level: ConfidenceLevel = ConfidenceLevel.NEEDS_VERIFICATION
    risk_flags: list[str] = Field(default_factory=list)
    change_types: list[HardwareChangeType] = Field(default_factory=list)
    opportunity_score: float = 0
    risk_score: float = 0
    score_reasons: list[str] = Field(default_factory=list)
    raw_title: str
    raw_description: str | None = None
    raw_data_json: dict[str, Any] = Field(default_factory=dict)


class HardwarePriceHistoryRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    opportunity_key: str
    source_url: str
    unit_price: float | None = None
    total_price: float | None = None
    quantity: int | None = None
    status: str | None = None
    observed_at: datetime = Field(default_factory=utc_now)


class HardwareQualityStats(BaseModel):
    raw_results: int = 0
    normalized_listings: int = 0
    specific_listings: int = 0
    listing_collections: int = 0
    source_pages: int = 0
    news_or_articles: int = 0
    irrelevant: int = 0
    duplicates_removed: int = 0
    new_opportunities: int = 0
    changed_opportunities: int = 0
    price_changes: int = 0
    quantity_changes: int = 0
    status_changes: int = 0
    final_opportunities: int = 0
    high_score_opportunities: int = 0
    failed_sources: int = 0


class TelegramDeliveryStatus(str, Enum):
    DISABLED = "disabled"
    DRY_RUN = "dry_run"
    SENT = "sent"
    FAILED = "failed"
    DUPLICATE_SKIPPED = "duplicate_skipped"


class TelegramDeliveryLog(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    scan_job_id: UUID
    report_type: str = "daily_hardware_report"
    message_hash: str
    status: TelegramDeliveryStatus
    chat_id: str | None = None
    telegram_message_id: str | None = None
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class HardwareDailyReport(BaseModel):
    scan_job_id: UUID
    report_type: str = "daily_hardware_report"
    title: str
    message_zh: str
    generated_at: datetime = Field(default_factory=utc_now)
    delivery_log: TelegramDeliveryLog | None = None


class TelegramReportAction(str, Enum):
    PREVIEW = "preview"
    TEST = "test"
    APPROVE_AND_SEND = "approve_and_send"


class TelegramReportRequest(BaseModel):
    action: TelegramReportAction = TelegramReportAction.PREVIEW
    message: str | None = None


class SchedulerStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"


class HardwareSchedulerState(BaseModel):
    status: SchedulerStatus = SchedulerStatus.PAUSED
    enabled: bool = False
    is_job_running: bool = False
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    current_job_id: UUID | None = None
    last_job_id: UUID | None = None
    last_error: str | None = None
    daily_report_hour: int = 8
    timezone: str = "America/Los_Angeles"
    restored_from_disk: bool = False


class HardwareScanJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    mode: HardwareScanMode = HardwareScanMode.BOTH
    status: HardwareScanJobStatus = HardwareScanJobStatus.CREATED
    categories: list[HardwareCategory] = Field(default_factory=list)
    states: list[str] = Field(default_factory=list)
    generated_queries: list[HardwareGeneratedQuery] = Field(default_factory=list)
    source_runs: list[HardwareSourceRun] = Field(default_factory=list)
    opportunities: list[HardwareOpportunity] = Field(default_factory=list)
    quality_stats: HardwareQualityStats = Field(default_factory=HardwareQualityStats)
    report: HardwareDailyReport | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class HardwareDashboard(BaseModel):
    total_jobs: int
    total_opportunities_seen: int
    active_opportunities: int
    latest_job: HardwareScanJob | None = None
    telegram_enabled: bool
    daily_report_hour: int
    timezone: str
    immediate_alerts: bool
    scheduler: HardwareSchedulerState
    top_opportunities: list[HardwareOpportunity] = Field(default_factory=list)
