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


class ResultCategory(str, Enum):
    SPECIFIC_LISTING = "specific_listing"
    LISTING_COLLECTION = "listing_collection"
    SOURCE_PAGE = "source_page"
    IRRELEVANT = "irrelevant"


class AddressStatus(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class PriceStatus(str, Enum):
    ASKING_PRICE = "asking_price"
    CONTACT_FOR_PRICE = "contact_for_price"
    UNKNOWN = "unknown"


class PowerAddressStatus(str, Enum):
    VERIFIED_ADDRESS = "verified_address"
    GEOCODED_ADDRESS = "geocoded_address"
    PARTIAL_ADDRESS = "partial_address"
    ADDRESS_NEEDS_VERIFICATION = "address_needs_verification"
    GEOCODING_FAILED = "geocoding_failed"


class PowerAssetType(str, Enum):
    SUBSTATION = "substation"
    TRANSMISSION_LINE = "transmission_line"
    TOWER = "tower"
    PLANT = "plant"


class LandIdReviewStatus(str, Enum):
    NOT_REVIEWED = "not_reviewed"
    IN_REVIEW = "in_review"
    MANUALLY_VERIFIED = "manually_verified"
    MISMATCH_FOUND = "mismatch_found"


class SearchAnchorType(str, Enum):
    ZIP_CODE = "zip_code"
    COORDINATES = "coordinates"
    ADDRESS = "address"
    UNKNOWN = "unknown"


class SearchAnchorStatus(str, Enum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    FAILED = "failed"


class DataTruthVerificationStatus(str, Enum):
    OFFICIAL_VERIFIED = "official_verified"
    MANUAL_MAP_CONFIRMED = "manual_map_confirmed"
    SOURCE_CONFIRMED = "source_confirmed"
    ESTIMATED = "estimated"
    CONFLICTING = "conflicting"
    UNVERIFIED = "unverified"


class ResultQualityStats(BaseModel):
    raw_results: int = 0
    specific_listings: int = 0
    listing_collections: int = 0
    source_pages: int = 0
    irrelevant_results: int = 0
    duplicates_removed: int = 0
    state_mismatch_removed: int = 0
    size_mismatch_removed: int = 0
    budget_mismatch_removed: int = 0
    radius_mismatch_removed: int = 0
    final_candidates: int = 0


class GeocodingResult(BaseModel):
    raw_address: str | None = None
    standardized_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    county: str | None = None
    state: str | None = None
    zip_code: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    confidence: float = 0
    status: PowerAddressStatus = PowerAddressStatus.ADDRESS_NEEDS_VERIFICATION
    error_message: str | None = None
    checked_at: datetime = Field(default_factory=utc_now)


class NearbyPowerAsset(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    site_id: UUID | None = None
    asset_type: PowerAssetType
    asset_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geometry: dict[str, Any] | None = None
    distance_miles: float | None = None
    voltage_kv: float | None = None
    owner: str | None = None
    operator: str | None = None
    status: str | None = None
    source_name: str
    source_url: str | None = None
    confidence_level: TrustLevel = TrustLevel.ESTIMATED
    verification_status: TrustLevel = TrustLevel.ESTIMATED
    dataset_version: str | None = None
    source_timestamp: datetime | None = None
    checked_at: datetime = Field(default_factory=utc_now)
    raw_data_json: dict[str, Any] = Field(default_factory=dict)


class UtilityCandidate(BaseModel):
    likely_utility: str | None = None
    utility_type: str = "unknown"
    evidence: str | None = None
    source_url: str | None = None
    confidence_level: TrustLevel = TrustLevel.UNKNOWN
    status: TrustLevel = TrustLevel.UNKNOWN


class PowerSourceRecord(BaseModel):
    source_name: str
    source_url: str | None = None
    source_type: str
    generated_query: str | None = None
    confidence_level: TrustLevel = TrustLevel.UNKNOWN
    discovered_at: datetime = Field(default_factory=utc_now)


class LandIdReview(BaseModel):
    land_id_review_status: LandIdReviewStatus = LandIdReviewStatus.NOT_REVIEWED
    land_id_map_url: str | None = None
    parcel_id: str | None = None
    owner_name: str | None = None
    owner_mailing_address: str | None = None
    parcel_acres: float | None = None
    nearest_substation_name: str | None = None
    nearest_substation_distance: float | None = None
    nearest_transmission_voltage: float | None = None
    manual_notes: str | None = None
    reviewed_at: datetime | None = None


class LandIdReviewRequest(BaseModel):
    land_id_review_status: LandIdReviewStatus
    land_id_map_url: str | None = None
    parcel_id: str | None = None
    owner_name: str | None = None
    owner_mailing_address: str | None = None
    parcel_acres: float | None = None
    nearest_substation_name: str | None = None
    nearest_substation_distance: float | None = None
    nearest_transmission_voltage: float | None = None
    manual_notes: str | None = None


class DataTruthVerification(BaseModel):
    automatic_result_summary: str | None = None
    land_id_result_summary: str | None = None
    official_source_summary: str | None = None
    conflict_summary: str | None = None
    final_verification_status: DataTruthVerificationStatus = DataTruthVerificationStatus.UNVERIFIED
    verified_at: datetime | None = None
    verified_by: str | None = None
    notes: str | None = None
    field_sources: dict[str, str] = Field(default_factory=dict)
    conflicting_fields: list[str] = Field(default_factory=list)
    capacity_status: str = "unknown"
    verification_warning: str = "真实性验证不代表Utility容量、接入许可、接入成本或送电时间已经确认。"
    updated_at: datetime = Field(default_factory=utc_now)


class DataTruthVerificationRequest(BaseModel):
    automatic_result_summary: str | None = None
    land_id_result_summary: str | None = None
    official_source_summary: str | None = None
    conflict_summary: str | None = None
    final_verification_status: DataTruthVerificationStatus = DataTruthVerificationStatus.UNVERIFIED
    verified_by: str | None = None
    notes: str | None = None
    field_sources: dict[str, str] = Field(default_factory=dict)
    conflicting_fields: list[str] = Field(default_factory=list)


class SitePowerAssessment(BaseModel):
    site_id: UUID | None = None
    address_status: PowerAddressStatus = PowerAddressStatus.ADDRESS_NEEDS_VERIFICATION
    raw_address: str | None = None
    standardized_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geocoding_source: str | None = None
    geocoding_confidence: float = 0
    nearest_substation: NearbyPowerAsset | None = None
    nearest_transmission_line: NearbyPowerAsset | None = None
    nearby_assets: list[NearbyPowerAsset] = Field(default_factory=list)
    likely_utility: UtilityCandidate = Field(default_factory=UtilityCandidate)
    power_source_records: list[PowerSourceRecord] = Field(default_factory=list)
    search_radius_counts: dict[str, int] = Field(default_factory=dict)
    known_voltage_kv: float | None = None
    capacity_status: str = "unknown"
    assessment_warning: str = "周边电力设施分析仅用于项目初筛，不代表Utility容量、接入许可、接入成本或送电时间已经确认。"
    confidence_level: TrustLevel = TrustLevel.UNKNOWN
    checked_at: datetime = Field(default_factory=utc_now)
    error_message: str | None = None


class SiteHunterRegions(BaseModel):
    states: list[str] = Field(default_factory=list)
    counties: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    zip_codes: list[str] = Field(default_factory=list)
    custom_area: str | None = None
    radius_miles: float | None = None


class SiteSearchAnchor(BaseModel):
    input_type: SearchAnchorType = SearchAnchorType.UNKNOWN
    raw_input: str | None = None
    label: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_miles: float | None = None
    city: str | None = None
    county: str | None = None
    state: str | None = None
    zip_code: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    confidence: float = 0
    status: SearchAnchorStatus = SearchAnchorStatus.UNRESOLVED
    error_message: str | None = None
    resolved_at: datetime | None = None


class SiteHunterStructuredCriteria(BaseModel):
    regions: SiteHunterRegions = Field(default_factory=SiteHunterRegions)
    search_anchor: SiteSearchAnchor | None = None
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
    standardized_address: str | None = None
    geocoding_source: str | None = None
    geocoding_confidence: float = 0
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
    result_category: ResultCategory = ResultCategory.IRRELEVANT
    address_status: AddressStatus = AddressStatus.UNKNOWN
    price_status: PriceStatus = PriceStatus.UNKNOWN
    data_completeness_score: float = 0
    quality_flags: list[str] = Field(default_factory=list)
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
    distance_to_search_anchor_miles: float | None = None
    search_anchor_distance_basis: str | None = None
    power_assessment: SitePowerAssessment | None = None
    land_id_review: LandIdReview = Field(default_factory=LandIdReview)
    data_truth_verification: DataTruthVerification = Field(default_factory=DataTruthVerification)


class SiteHunterJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    status: SiteHunterJobStatus = SiteHunterJobStatus.CREATED
    natural_language_query_zh: str | None = None
    parsed_criteria: SiteHunterStructuredCriteria | None = None
    generated_queries: list[GeneratedSearchQuery] = Field(default_factory=list)
    discovered_sources: list[DiscoveredSource] = Field(default_factory=list)
    source_runs: list[SearchSourceRun] = Field(default_factory=list)
    results: list[NormalizedSiteListing] = Field(default_factory=list)
    discovery_candidates: list[NormalizedSiteListing] = Field(default_factory=list)
    quality_stats: ResultQualityStats = Field(default_factory=ResultQualityStats)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class SiteReviewRequest(BaseModel):
    status: SiteReviewStatus
    note: str | None = None
