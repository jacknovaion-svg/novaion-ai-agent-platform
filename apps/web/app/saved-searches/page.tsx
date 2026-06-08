"use client";

import { useEffect, useState } from "react";
import { listSavedSearches } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type SavedSearch = {
  id: string;
  query: string;
  quantity: number;
  zip_code?: string | null;
  radius?: number | null;
  sources: string[];
  created_at: string;
};

export default function SavedSearchesPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<SavedSearch[]>([]);

  useEffect(() => {
    listSavedSearches().then(setItems).catch(() => setItems([]));
  }, []);

  return (
    <div className="grid">
      <h1 className="page-title">{t("savedSearches")}</h1>
      {!items.length ? <div className="panel muted">{t("noSaved")}</div> : null}
      <div className="agent-list">
        {items.map((item) => (
          <div className="agent-row" key={item.id}>
            <div>
              <strong>{item.query}</strong>
              <div className="muted">
                {item.quantity} · {item.zip_code ?? "-"} · {item.radius ?? "-"} mi · {item.sources.join(", ")}
              </div>
            </div>
            <span className="pill">{new Date(item.created_at).toLocaleDateString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
