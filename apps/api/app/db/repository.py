from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.db.memory import memory_store
from app.models.schemas import NormalizedResult, SavedSearch, SavedSearchCreate, SearchRequest, UserPreference, UserPreferenceUpdate


class Repository:
    def __init__(self) -> None:
        self.engine: Engine | None = None
        settings = get_settings()
        if settings.database_url:
            self.engine = create_engine(settings.database_url, pool_pre_ping=True)

    def create_search_job(self, payload: SearchRequest, results: list[NormalizedResult]) -> UUID:
        if not self.engine:
            return uuid4()

        try:
            with self.engine.begin() as connection:
                job_id = connection.execute(
                    text(
                        """
                        insert into search_jobs
                          (user_id, agent_type, query, quantity, zip_code, radius, mode, status)
                        values
                          (:user_id, :agent_type, :query, :quantity, :zip_code, :radius, :mode, 'completed')
                        returning id
                        """
                    ),
                    {
                        "user_id": str(payload.user_id) if payload.user_id else None,
                        "agent_type": payload.agent_type.value,
                        "query": payload.query,
                        "quantity": payload.quantity,
                        "zip_code": payload.zip_code,
                        "radius": payload.radius,
                        "mode": payload.mode.value,
                    },
                ).scalar_one()

                for item in results:
                    connection.execute(
                        text(
                            """
                            insert into search_results
                              (
                                search_job_id, source, product_name, brand, model, store_name,
                                address, distance, price, promotion, inventory_status,
                                pickup_available, shipping_available, product_url,
                                recommendation_score, updated_at
                              )
                            values
                              (
                                :search_job_id, :source, :product_name, :brand, :model, :store_name,
                                :address, :distance, :price, :promotion, :inventory_status,
                                :pickup_available, :shipping_available, :product_url,
                                :recommendation_score, :updated_at
                              )
                            """
                        ),
                        {
                            "search_job_id": job_id,
                            "source": item.source,
                            "product_name": item.product_name,
                            "brand": item.brand,
                            "model": item.model,
                            "store_name": item.store_name,
                            "address": item.address,
                            "distance": item.distance,
                            "price": item.price,
                            "promotion": item.promotion,
                            "inventory_status": item.inventory_status,
                            "pickup_available": item.pickup_available,
                            "shipping_available": item.shipping_available,
                            "product_url": item.product_url,
                            "recommendation_score": item.recommendation_score,
                            "updated_at": item.updated_at,
                        },
                    )
                return UUID(str(job_id))
        except Exception:
            return uuid4()

    def create_saved_search(self, payload: SavedSearchCreate) -> SavedSearch:
        if not self.engine:
            return memory_store.create_saved_search(payload)

        try:
            with self.engine.begin() as connection:
                row = connection.execute(
                    text(
                        """
                        insert into saved_searches
                          (user_id, query, quantity, zip_code, radius, sources)
                        values
                          (:user_id, :query, :quantity, :zip_code, :radius, :sources)
                        returning id, user_id, query, quantity, zip_code, radius, sources, created_at
                        """
                    ),
                    {
                        "user_id": str(payload.user_id) if payload.user_id else None,
                        "query": payload.query,
                        "quantity": payload.quantity,
                        "zip_code": payload.zip_code,
                        "radius": payload.radius,
                        "sources": [source.value for source in payload.sources],
                    },
                ).mappings().one()
                return SavedSearch(**row)
        except Exception:
            return memory_store.create_saved_search(payload)

    def list_saved_searches(self) -> list[SavedSearch]:
        if not self.engine:
            return memory_store.list_saved_searches()

        try:
            with self.engine.begin() as connection:
                rows = connection.execute(
                    text(
                        """
                        select id, user_id, query, quantity, zip_code, radius, sources, created_at
                        from saved_searches
                        order by created_at desc
                        limit 50
                        """
                    )
                ).mappings().all()
                return [SavedSearch(**row) for row in rows]
        except Exception:
            return memory_store.list_saved_searches()

    def upsert_user_preference(self, payload: UserPreferenceUpdate) -> UserPreference:
        if not self.engine:
            return memory_store.upsert_user_preference(payload)

        try:
            with self.engine.begin() as connection:
                email = payload.email or get_settings().default_user_email
                row = connection.execute(
                    text(
                        """
                        insert into users (email, language)
                        values (:email, :language)
                        on conflict (email) do update set language = excluded.language
                        returning id, email, language, created_at
                        """
                    ),
                    {"email": email, "language": payload.language.value},
                ).mappings().one()
                return UserPreference(**row)
        except Exception:
            return memory_store.upsert_user_preference(payload)


repository = Repository()
