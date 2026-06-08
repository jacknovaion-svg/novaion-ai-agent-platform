from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl

from app.models.enums import AgentType, Language, SearchMode, SearchSource


class SearchOptions(BaseModel):
    quantity: int = Field(default=1, ge=1)
    zip_code: str | None = None
    radius: int | None = Field(default=25, ge=1)
    mode: SearchMode = SearchMode.ALL
    sources: list[SearchSource] = Field(default_factory=lambda: list(SearchSource))


class SearchRequest(SearchOptions):
    query: str = Field(min_length=1)
    user_id: UUID | None = None
    agent_type: AgentType = AgentType.HARDWARE_HUNTER


class NormalizedResult(BaseModel):
    source: str
    product_name: str
    brand: str | None = None
    model: str | None = None
    store_name: str | None = None
    address: str | None = None
    distance: float | None = None
    price: float | None = None
    promotion: str | None = None
    inventory_status: str | None = None
    pickup_available: bool = False
    shipping_available: bool = False
    product_url: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recommendation_score: float = 0


class SearchJobResponse(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    agent_type: AgentType
    query: str
    quantity: int
    zip_code: str | None
    radius: int | None
    mode: SearchMode
    status: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    results: list[NormalizedResult]


class AgentInfo(BaseModel):
    id: str
    name: str
    type: AgentType
    enabled: bool
    description: str


class SavedSearchCreate(BaseModel):
    user_id: UUID | None = None
    query: str
    quantity: int = Field(default=1, ge=1)
    zip_code: str | None = None
    radius: int | None = Field(default=25, ge=1)
    sources: list[SearchSource] = Field(default_factory=list)


class SavedSearch(SavedSearchCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserPreferenceUpdate(BaseModel):
    email: str | None = None
    language: Language


class UserPreference(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: str | None = None
    language: Language = Language.ENGLISH
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
