from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SupplierJobStatus(str, Enum):
    CREATED = "created"
    PARSING_REQUIREMENTS = "parsing_requirements"
    GENERATING_QUERIES = "generating_queries"
    SEARCHING_SUPPLIERS = "searching_suppliers"
    NORMALIZING_RESULTS = "normalizing_results"
    SCORING = "scoring"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


class SupplierSourceRunStatus(str, Enum):
    PENDING = "pending"
    SEARCHING = "searching"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


class SupplierCategory(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    CLAIMED_ON_WEBSITE = "claimed_on_website"
    DIRECTORY_DISCOVERED = "directory_discovered"
    NEEDS_VERIFICATION = "needs_verification"
    UNKNOWN = "unknown"


class SupplierReviewStatus(str, Enum):
    NEW = "new"
    KEPT = "kept"
    REJECTED = "rejected"
    CONTACT = "contact"
    INVESTIGATE = "investigate"


class SupplierSearchRegions(BaseModel):
    states: list[str] = Field(default_factory=list)
    state_codes: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    zip_codes: list[str] = Field(default_factory=list)
    radius_miles: float | None = None


class SupplierSearchCriteria(BaseModel):
    regions: SupplierSearchRegions = Field(default_factory=SupplierSearchRegions)
    supplier_types: list[str] = Field(default_factory=list)
    equipment_types: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    data_center_decommissioning: bool | None = None
    bulk_sales: bool | None = None
    wholesale: bool | None = None
    direct_asset_purchasing: bool | None = None
    raw_user_query_zh: str | None = None
    parsed_summary_zh: str | None = None


class SupplierSearchRequest(BaseModel):
    natural_language_query_zh: str | None = None
    structured_criteria: SupplierSearchCriteria | None = None
    manual_urls: list[HttpUrl] = Field(default_factory=list)
    manual_text: str | None = None
    max_results_per_source: int = Field(default=8, ge=1, le=25)


class SupplierGeneratedQuery(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    generated_query_en: str
    source_group: str
    state: str | None = None
    state_code: str | None = None
    city: str | None = None
    region_name: str | None = None
    supplier_type: str | None = None
    result_count: int = 0
    status: SupplierSourceRunStatus = SupplierSourceRunStatus.PENDING


class SupplierRegionSubJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    state_code: str
    state_name: str
    region_name: str
    cities: list[str] = Field(default_factory=list)
    generated_query_count: int = 0
    executed_query_count: int = 0
    raw_result_count: int = 0
    supplier_count: int = 0
    high_value_count: int = 0
    status: SupplierSourceRunStatus = SupplierSourceRunStatus.PENDING


class SupplierSourceRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_name: str
    adapter_type: str
    query: str | None = None
    status: SupplierSourceRunStatus = SupplierSourceRunStatus.PENDING
    result_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class RawSupplierResult(BaseModel):
    source_name: str
    source_url: str
    original_title: str
    original_description: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=utc_now)


class SupplierResult(BaseModel):
    supplier_id: UUID = Field(default_factory=uuid4)
    company_name: str
    company_type: str | None = None
    supplier_category: SupplierCategory = SupplierCategory.D
    website: str | None = None
    address: str | None = None
    city: str | None = None
    county: str | None = None
    state: str | None = None
    zip_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    email: str | None = None
    contact_name: str | None = None
    service_area: str | None = None
    r2_certified: VerificationStatus = VerificationStatus.UNKNOWN
    e_stewards_certified: VerificationStatus = VerificationStatus.UNKNOWN
    naid_aaa_certified: VerificationStatus = VerificationStatus.UNKNOWN
    data_center_decommissioning: bool = False
    enterprise_itad: bool = False
    asset_remarketing: bool = False
    direct_asset_purchasing: bool = False
    server_recycling: bool = False
    computer_refurbishing: bool = False
    bulk_sales: bool = False
    wholesale: bool = False
    equipment_types: list[str] = Field(default_factory=list)
    minimum_order: str | None = None
    pickup_available: bool | None = None
    shipping_available: bool | None = None
    source_name: str
    source_url: str
    last_checked_at: datetime = Field(default_factory=utc_now)
    confidence_level: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    review_status: SupplierReviewStatus = SupplierReviewStatus.NEW
    notes: str | None = None
    supplier_score: float = 0
    score_reasons: list[str] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
    raw_data_json: dict[str, Any] = Field(default_factory=dict)


class SupplierQualityStats(BaseModel):
    raw_results: int = 0
    normalized_suppliers: int = 0
    duplicates_removed: int = 0
    low_value_filtered: int = 0
    final_suppliers: int = 0
    high_value_suppliers: int = 0


class SupplierSearchJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    status: SupplierJobStatus = SupplierJobStatus.CREATED
    natural_language_query_zh: str | None = None
    parsed_criteria: SupplierSearchCriteria | None = None
    state_job: dict[str, Any] | None = None
    region_subjobs: list[SupplierRegionSubJob] = Field(default_factory=list)
    generated_queries: list[SupplierGeneratedQuery] = Field(default_factory=list)
    source_runs: list[SupplierSourceRun] = Field(default_factory=list)
    results: list[SupplierResult] = Field(default_factory=list)
    rejected_low_value_results: list[SupplierResult] = Field(default_factory=list)
    quality_stats: SupplierQualityStats = Field(default_factory=SupplierQualityStats)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class SupplierReviewRequest(BaseModel):
    status: SupplierReviewStatus
    notes: str | None = None

