"use client";

import { Bookmark, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { HardwareSearchMode, SearchMode, SearchSource } from "@novaion/shared/types";
import { createSupplierHunterJob, runSearch, saveSearch, storeResults } from "@/lib/api";
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
  const [hardwareMode, setHardwareMode] = useState<HardwareSearchMode>("retail_products");
  const [query, setQuery] = useState("RTX 5090");
  const [supplierQuery, setSupplierQuery] = useState("TX，寻找做数据中心退役、企业ITAD、二手服务器、内存、硬盘、笔记本和台式机批量销售的一手供应商。");
  const [supplierState, setSupplierState] = useState("TX");
  const [supplierCity, setSupplierCity] = useState("");
  const [supplierType, setSupplierType] = useState("enterprise ITAD, data center decommissioning, used server wholesaler");
  const [equipmentType, setEquipmentType] = useState("servers, memory, hard drives, laptops, desktops");
  const [certification, setCertification] = useState("R2");
  const [dataCenterDecommissioning, setDataCenterDecommissioning] = useState(true);
  const [bulkSales, setBulkSales] = useState(true);
  const [wholesale, setWholesale] = useState(true);
  const [directAssetPurchasing, setDirectAssetPurchasing] = useState(true);
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
      if (hardwareMode === "supplier_discovery") {
        const job = await createSupplierHunterJob({
          natural_language_query_zh: supplierQuery,
          structured_criteria: {
            regions: {
              states: splitList(supplierState).filter((item) => item.length !== 2),
              state_codes: splitList(supplierState).filter((item) => /^[A-Za-z]{2}$/.test(item)).map((item) => item.toUpperCase()),
              cities: splitList(supplierCity),
              zip_codes: [],
            },
            supplier_types: splitList(supplierType),
            equipment_types: splitList(equipmentType),
            certifications: splitList(certification),
            data_center_decommissioning: dataCenterDecommissioning,
            bulk_sales: bulkSales,
            wholesale,
            direct_asset_purchasing: directAssetPurchasing,
          },
          max_results_per_source: 6,
        });
        router.push(`/supplier-hunter/results/${job.id}`);
        return;
      }
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
      <div className="mode-switch" style={{ marginBottom: 18 }}>
        {[
          ["retail_products", "Retail Products"],
          ["used_enterprise_hardware", "Used Enterprise Hardware"],
          ["supplier_discovery", "Supplier Discovery"],
        ].map(([value, label]) => (
          <button
            className={`button ${hardwareMode === value ? "primary" : "secondary"}`}
            key={value}
            type="button"
            onClick={() => setHardwareMode(value as HardwareSearchMode)}
          >
            {label}
          </button>
        ))}
      </div>
      {hardwareMode === "supplier_discovery" ? (
        <>
          <label className="field">
            <span>Supplier Discovery Requirement</span>
            <textarea className="textarea" value={supplierQuery} onChange={(event) => setSupplierQuery(event.target.value)} />
          </label>
          <div className="form-grid" style={{ marginTop: 14 }}>
            <label className="field">
              <span>State / 州</span>
              <input className="input" value={supplierState} onChange={(event) => setSupplierState(event.target.value)} placeholder="TX, Texas, 德州" />
            </label>
            <label className="field">
              <span>City optional</span>
              <input className="input" value={supplierCity} onChange={(event) => setSupplierCity(event.target.value)} />
            </label>
            <label className="field">
              <span>Supplier Type</span>
              <input className="input" value={supplierType} onChange={(event) => setSupplierType(event.target.value)} />
            </label>
            <label className="field">
              <span>Equipment Type</span>
              <input className="input" value={equipmentType} onChange={(event) => setEquipmentType(event.target.value)} />
            </label>
            <label className="field">
              <span>Certification</span>
              <input className="input" value={certification} onChange={(event) => setCertification(event.target.value)} />
            </label>
          </div>
          <div className="source-grid" style={{ marginTop: 18 }}>
            <label className="check">
              <input type="checkbox" checked={dataCenterDecommissioning} onChange={() => setDataCenterDecommissioning(!dataCenterDecommissioning)} />
              Data Center Decommissioning
            </label>
            <label className="check">
              <input type="checkbox" checked={directAssetPurchasing} onChange={() => setDirectAssetPurchasing(!directAssetPurchasing)} />
              Direct Asset Purchasing
            </label>
            <label className="check">
              <input type="checkbox" checked={bulkSales} onChange={() => setBulkSales(!bulkSales)} />
              Bulk Sales
            </label>
            <label className="check">
              <input type="checkbox" checked={wholesale} onChange={() => setWholesale(!wholesale)} />
              Wholesale
            </label>
          </div>
          <div className="actions">
            <button className="button primary" type="button" onClick={submit} disabled={loading || !supplierQuery.trim()}>
              <Search size={17} />
              {loading ? "Searching..." : "Start Supplier Discovery"}
            </button>
          </div>
        </>
      ) : (
        <>
      <div className="form-grid">
        <label className="field">
          <span>{hardwareMode === "used_enterprise_hardware" ? "Used Enterprise Hardware" : t("product")}</span>
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
        </>
      )}
    </div>
  );
}

function splitList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
