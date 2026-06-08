"use client";

import { Bookmark, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { SearchMode, SearchSource } from "@novaion/shared/types";
import { runSearch, saveSearch, storeResults } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const sourceOptions: { value: SearchSource; label: string }[] = [
  { value: "best_buy", label: "Best Buy" },
  { value: "micro_center", label: "Micro Center" },
  { value: "newegg", label: "Newegg" },
  { value: "cdw", label: "CDW" },
  { value: "provantage", label: "Provantage" },
];

export function SearchForm() {
  const router = useRouter();
  const { t } = useI18n();
  const [query, setQuery] = useState("RTX 5090");
  const [quantity, setQuantity] = useState(1);
  const [zipCode, setZipCode] = useState("94085");
  const [radius, setRadius] = useState(25);
  const [mode, setMode] = useState<SearchMode>("all");
  const [sources, setSources] = useState<SearchSource[]>(["best_buy", "newegg"]);
  const [loading, setLoading] = useState(false);

  const payload = {
    query,
    quantity,
    zip_code: zipCode,
    radius,
    mode,
    sources,
  };

  async function submit() {
    setLoading(true);
    try {
      const job = await runSearch(payload);
      storeResults(job);
      router.push("/results");
    } finally {
      setLoading(false);
    }
  }

  async function save() {
    await saveSearch(payload);
    router.push("/saved-searches");
  }

  function toggleSource(source: SearchSource) {
    setSources((current) =>
      current.includes(source) ? current.filter((item) => item !== source) : [...current, source],
    );
  }

  return (
    <div className="panel">
      <div className="form-grid">
        <label className="field">
          <span>{t("product")}</span>
          <input className="input" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <label className="field">
          <span>{t("quantity")}</span>
          <input
            className="input"
            type="number"
            min={1}
            value={quantity}
            onChange={(event) => setQuantity(Number(event.target.value))}
          />
        </label>
        <label className="field">
          <span>{t("zipCode")}</span>
          <input className="input" value={zipCode} onChange={(event) => setZipCode(event.target.value)} />
        </label>
        <label className="field">
          <span>{t("radius")}</span>
          <input
            className="input"
            type="number"
            min={1}
            value={radius}
            onChange={(event) => setRadius(Number(event.target.value))}
          />
        </label>
        <label className="field">
          <span>{t("mode")}</span>
          <select className="select" value={mode} onChange={(event) => setMode(event.target.value as SearchMode)}>
            <option value="local">{t("local")}</option>
            <option value="online">{t("online")}</option>
            <option value="all">{t("all")}</option>
          </select>
        </label>
      </div>
      <div style={{ marginTop: 18 }}>
        <div className="section-label">{t("sources")}</div>
        <div className="source-grid">
          {sourceOptions.map((source) => (
            <label className="check" key={source.value}>
              <input
                type="checkbox"
                checked={sources.includes(source.value)}
                onChange={() => toggleSource(source.value)}
              />
              {source.label}
            </label>
          ))}
        </div>
      </div>
      <div className="actions">
        <button className="button primary" type="button" onClick={submit} disabled={loading || !query || !sources.length}>
          <Search size={17} />
          {loading ? "..." : t("startSearch")}
        </button>
        <button className="button secondary" type="button" onClick={save}>
          <Bookmark size={17} />
          {t("saveSearch")}
        </button>
      </div>
    </div>
  );
}
