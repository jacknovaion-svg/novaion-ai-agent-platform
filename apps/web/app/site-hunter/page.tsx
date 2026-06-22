"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createSiteHunterJob } from "@/lib/api";

const defaultQuery =
  "帮我搜索德州和乔治亚州20英亩以上的旧制造工厂或工业土地，预算1000万美元以内，用于未来建设50MW AI数据中心。";

function splitList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function SiteHunterSearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState(defaultQuery);
  const [states, setStates] = useState("Texas, Georgia");
  const [counties, setCounties] = useState("");
  const [cities, setCities] = useState("");
  const [zipCodes, setZipCodes] = useState("");
  const [minAcres, setMinAcres] = useState(20);
  const [maxPrice, setMaxPrice] = useState(10000000);
  const [targetMw, setTargetMw] = useState(50);
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    try {
      const job = await createSiteHunterJob({
        natural_language_query_zh: query,
        structured_criteria: {
          regions: {
            states: splitList(states),
            counties: splitList(counties),
            cities: splitList(cities),
            zip_codes: splitList(zipCodes),
          },
          property_types: ["former manufacturing facility", "industrial land"],
          transaction_types: ["for sale"],
          min_land_acres: minAcres || null,
          max_price_usd: maxPrice || null,
          target_load_mw: targetMw || null,
          project_use: "ai_data_center",
        },
        max_results_per_source: 6,
      });
      router.push(`/site-hunter/progress/${job.id}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid site-layout">
      <div className="panel">
        <h1 className="page-title">Site Hunter V1</h1>
        <label className="field">
          <span>中文自然语言需求</span>
          <textarea className="textarea" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <div className="form-grid" style={{ marginTop: 14 }}>
          <label className="field">
            <span>States</span>
            <input className="input" value={states} onChange={(event) => setStates(event.target.value)} />
          </label>
          <label className="field">
            <span>Counties</span>
            <input className="input" value={counties} onChange={(event) => setCounties(event.target.value)} />
          </label>
          <label className="field">
            <span>Cities</span>
            <input className="input" value={cities} onChange={(event) => setCities(event.target.value)} />
          </label>
          <label className="field">
            <span>ZIP Codes</span>
            <input className="input" value={zipCodes} onChange={(event) => setZipCodes(event.target.value)} />
          </label>
          <label className="field">
            <span>Min Land Acres</span>
            <input className="input" type="number" value={minAcres} onChange={(event) => setMinAcres(Number(event.target.value))} />
          </label>
          <label className="field">
            <span>Max Price USD</span>
            <input className="input" type="number" value={maxPrice} onChange={(event) => setMaxPrice(Number(event.target.value))} />
          </label>
          <label className="field">
            <span>Target Load MW</span>
            <input className="input" type="number" value={targetMw} onChange={(event) => setTargetMw(Number(event.target.value))} />
          </label>
        </div>
        <div className="actions">
          <button className="button primary" type="button" onClick={submit} disabled={loading || !query.trim()}>
            <Search size={17} />
            {loading ? "Starting..." : "启动 Site Hunter 搜索"}
          </button>
        </div>
      </div>
      <aside className="panel">
        <div className="section-label">V1 Phase 1</div>
        <h2>中文需求到美国工业地产发现</h2>
        <p className="muted">
          系统会保留原始中文、解析条件、英文搜索词、来源状态、原始英文标题和原始链接。电力容量验证不在本阶段执行。
        </p>
      </aside>
    </div>
  );
}
