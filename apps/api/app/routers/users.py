from fastapi import APIRouter

from app.db.repository import repository
from app.models.schemas import UserPreference, UserPreferenceUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/preferences", response_model=UserPreference)
def update_preference(payload: UserPreferenceUpdate) -> UserPreference:
    return repository.upsert_user_preference(payload)
