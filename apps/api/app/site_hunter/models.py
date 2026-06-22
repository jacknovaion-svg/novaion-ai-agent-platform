from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SiteHunterJobStatus(str, Enum):
    CREATED = "created"
    PARSING_REQUIREMENTS = "parsing_requirements"
    GENERATING_QUERIES = "generating_queries"
    DISCOVERING_SOURCES = "discovering_sources"
    SEARCHING_PROPERTIES = "searching_properties"
    NORMALIZING_RESULTS = "normalizing_results"
    SCORING = "scoring"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


class SourceRunStatus(str, Enum):
    PENDING = "pending"
    SEARCHING = "searching"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    DISABLED = "disabled"


class SourceType(str, Enum):
    NATIONAL_MARKETPLACE = "national_marketplace"
    NATIONAL_BROKERAGE = "national_brokerage"
    LOCAL_BROKERAGE = "local_brokerage"
    STATE_GOVERNMENT = "state_government"
    COUNTY_GOVERNMENT = "county_government"
    CITY_GOVERNMENT = "city_government"
    ECONOMIC_DEVELOPMENT = "economic_development"
    INDUSTRIAL_PARK = "industrial_park"
    UTILITY = "utility"
    AUCTION = "auction"
    OTHER = "other"


class TrustLevel(str, Enum):
    VERIFIED = "verified"
    SOURCE_CONFIRMED = "source_confirmed"
    ESTIMATED = "estimated"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"


class SiteReviewStatus(str, Enum):
    KEPT = "kept"
    REJECTED = "rejected"
    INVESTIGATE = "investigate"
    DUPLICATE = "duplicate"
    INCORRECT = "incorrect"


class SiteHunterRegions(BaseModel):
    states: list[str] = Field(default_factory=list)
    counties: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    zip_codes: list[str] = Field(default_factory=list)
    custom_area: str | None = None
    radius_miles: float | None = None


class SiteHunterStructuredCriteria(BaseModel):
    regions: SiteHunterRegions = Field(default_factory=SiteHunterRegions)
    property_types: list[str] = Field(default_factory=list)
    transaction_types: list[str] = Field(default_factory=lambda: ["for sale"])
    min_land_acres: float | None = None
    max_land_acres: float | None = None
    min_building_sqft: float | None = None
    max_building_sqft: float | None = None
    max_price_usd: float | None = None
    target_load_mw: float | None = None
    preferred_substation_distance_miles: float | None = None
    preferred_transmission_voltage_kv: float | None = None
    project_use: str | None = None
    raw_user_query_zh: str | None = None
    parsed_summary_zh: str | None = None


class SiteHunterSearchRequest(BaseModel):
    natural_language_query_zh: str | None = None
    structured_criteria: SiteHunterStructuredCriteria | None = None
    manual_urls: list[HttpUrl] = Field(default_factory=list)
    manual_text: str | None = None
    max_results_per_source: int = Field(default=8, ge=1, le=25)


class GeneratedSearchQuery(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    generated_query_en: str
    source_group: str
    state: str | None = None
    county: str | None = None
    city: str | None = None
    property_type: str | None = None
    status: SourceRunStatus = SourceRunStatus.PENDING
    result_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    error_message: str | None = None


class DiscoveredSource(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_name: str
    domain: str
    source_type: SourceType
    state: str | None = None
    county: str | None = None
    city: str | None = None
    discovery_method: str
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    adapter_type: str = "generic_web_search"
    status: SourceRunStatus = SourceRunStatus.PENDING
    last_success_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SearchSourceRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_name: str
    source_type: SourceType
    adapter_type: str
    query: str | None = None
    status: SourceRunStatus = SourceRunStatus.PENDING
    result_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class RawPropertyResult(BaseModel):
    source_name: str
    source_url: str
    source_type: SourceType = SourceType.OTHER
    original_title: str
    original_description: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=utc_now)


class NormalizedSiteListing(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    site_name: str
    translated_title_zh: str | None = None
    translated_summary_zh: str | None = None
    address_line_1: str | None = None
    city: str | None = None
    county: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str = "US"
    latitude: float | None = None
    longitude: float | None = None
    property_type: str | None = None
    zoning: str | None = None
    land_acres: float | None = None
    building_sqft: float | None = None
    asking_price_usd: float | None = None
    transaction_type: str | None = None
    source_name: str
    source_url: str
    source_type: SourceType = SourceType.OTHER
    original_title: str
    original_description: str | None = None
    broker_name: str | None = None
    broker_company: str | None = None
    source_confidence: TrustLevel = TrustLevel.UNVERIFIED
    field_confidence: dict[str, TrustLevel] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    raw_data_json: dict[str, Any] = Field(default_factory=dict)
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_checked_at: datetime = Field(default_factory=utc_now)
    preliminary_score: float = 0
    preliminary_grade: str = "D"
    score_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    review_status: SiteReviewStatus | None = None


class SiteHunterJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    status: SiteHunterJobStatus = SiteHunterJobStatus.CREATED
    natural_language_query_zh: str | None = None
    parsed_criteria: SiteHunterStructuredCriteria | None = None
    generated_queries: list[GeneratedSearchQuery] = Field(default_factory=list)
    discovered_sources: list[DiscoveredSource] = Field(default_factory=list)
    source_runs: list[SearchSourceRun] = Field(default_factory=list)
    results: list[NormalizedSiteListing] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class SiteReviewRequest(BaseModel):
    status: SiteReviewStatus
    note: str | None = None
