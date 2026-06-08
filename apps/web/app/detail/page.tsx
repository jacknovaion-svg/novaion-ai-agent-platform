"use client";

import { ExternalLink, MapPinned } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { SearchResult } from "@novaion/shared/types";
import { loadDetail } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function DetailPage() {
  const { t } = useI18n();
  const [result, setResult] = useState<SearchResult | null>(null);

  useEffect(() => {
    setResult(loadDetail());
  }, []);

  const mapsUrl = useMemo(() => {
    if (!result?.address) return "https://maps.google.com";
    return `https://maps.google.com/?q=${encodeURIComponent(result.address)}`;
  }, [result]);

  if (!result) {
    return <div className="panel muted">{t("detailMissing")}</div>;
  }

  return (
    <div className="grid">
      <h1 className="page-title">{result.product_name}</h1>
      <div className="grid detail-grid">
        <section className="panel kv">
          <div>
            <span>{t("source")}</span>
            <strong>{result.source}</strong>
          </div>
          <div>
            <span>{t("price")}</span>
            <strong>{result.price == null ? "-" : `$${result.price.toLocaleString()}`}</strong>
          </div>
          <div>
            <span>{t("inventoryStatus")}</span>
            <strong>{result.inventory_status ?? "-"}</strong>
          </div>
          <div>
            <span>{t("address")}</span>
            <strong>{result.address ?? "-"}</strong>
          </div>
          <div>
            <span>{t("recommendationScore")}</span>
            <strong className="score">{result.recommendation_score}</strong>
          </div>
        </section>
        <section className="panel">
          <div className="section-label">{t("aiReason")}</div>
          <p>
            {result.inventory_status ?? "Inventory status is available"} gives this listing a strong availability
            signal. The score also reflects price competitiveness, pickup or shipping availability, distance, and
            current promotion data.
          </p>
          <div className="actions">
            <a className="button primary" href={result.product_url ?? "#"} target="_blank" rel="noreferrer">
              <ExternalLink size={17} />
              {t("openProduct")}
            </a>
            <a className="button gold" href={mapsUrl} target="_blank" rel="noreferrer">
              <MapPinned size={17} />
              {t("maps")}
            </a>
          </div>
        </section>
      </div>
    </div>
  );
}
