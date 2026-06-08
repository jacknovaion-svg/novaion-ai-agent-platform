from __future__ import annotations

from fastapi import APIRouter

from app.db.repository import repository
from app.models.schemas import SavedSearch, SavedSearchCreate

router = APIRouter(prefix="/saved-searches", tags=["saved-searches"])


@router.get("", response_model=list[SavedSearch])
def list_saved_searches() -> list[SavedSearch]:
    return repository.list_saved_searches()


@router.post("", response_model=SavedSearch)
def create_saved_search(payload: SavedSearchCreate) -> SavedSearch:
    return repository.create_saved_search(payload)
