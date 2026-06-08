from __future__ import annotations

from app.models.schemas import SavedSearch, SavedSearchCreate, UserPreference, UserPreferenceUpdate


class MemoryStore:
    def __init__(self) -> None:
        self.saved_searches: list[SavedSearch] = []
        self.user_preferences: list[UserPreference] = []

    def create_saved_search(self, payload: SavedSearchCreate) -> SavedSearch:
        saved = SavedSearch(**payload.model_dump())
        self.saved_searches.insert(0, saved)
        return saved

    def list_saved_searches(self) -> list[SavedSearch]:
        return self.saved_searches

    def upsert_user_preference(self, payload: UserPreferenceUpdate) -> UserPreference:
        for user in self.user_preferences:
            if payload.email and user.email == payload.email:
                user.language = payload.language
                return user
        user = UserPreference(email=payload.email, language=payload.language)
        self.user_preferences.append(user)
        return user


memory_store = MemoryStore()
