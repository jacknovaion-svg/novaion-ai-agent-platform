"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { SiteHunterJob, SiteListing } from "@novaion/shared/types";
import { getSiteHunterJob } from "@/lib/api";

export default function SiteHunterResultsPage() {
  const params = useParams<{ jobId: string }>();
  const [job, setJob] = useState<SiteHunterJob | null>(null);
  const [stateFilter, setStateFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSiteHunterJob(params.jobId)
      .then((next) => {
        setJob(next);
        setError(null);
      })
      .catch((err) => {
        setJob(null);
        setError(err instanceof Error ? err.message : "Failed to load results");
      });
  }, [params.jobId]);

  const results = useMemo(() => {
    const all = job?.results ?? [];
    return stateFilter ? all.filter((item) => (item.state ?? "").toLowerCase().includes(stateFilter.toLowerCase())) : all;
  }, [job?.results, stateFilter]);

  return (
    <div className="grid">
      <div className="panel">
        <div className="section-label">Site Hunter Results</div>
        <h1 className="page-title">真实工业地产候选</h1>
        <p className="muted">Job {params.jobId} · {job?.status ?? "loading"} · {results.length} results</p>
        {error ? <p className="danger-text">{error}</p> : null}
        <div className="form-grid" style={{ marginTop: 14 }}>
          <label className="field">
            <span>按州筛选</span>
            <input className="input" value={stateFilter} onChange={(event) => setStateFilter(event.target.value)} />
          </label>
        </div>
      </div>
      <div className="site-card-grid">
        {results.map((site) => (
          <SiteCard site={site} key={site.id} />
        ))}
      </div>
      {!results.length ? <div className="panel muted">暂无结果。真实搜索源可能超时、被阻断或未发现匹配项目。</div> : null}
    </div>
  );
}

function SiteCard({ site }: { site: SiteListing }) {
  return (
    <article className="panel site-card">
      <div className="site-card-head">
        <div>
          <div className="section-label">{site.source_name}</div>
          <h2>{site.translated_title_zh ?? site.site_name}</h2>
        </div>
        <span className="score-badge">{site.preliminary_grade} · {site.preliminary_score}</span>
      </div>
      <p className="muted">{site.original_title}</p>
      <div className="site-facts">
        <span>State: {site.state ?? "unknown"}</span>
        <span>Acres: {site.land_acres ?? "unknown"}</span>
        <span>Price: {site.asking_price_usd ? `$${site.asking_price_usd.toLocaleString()}` : "unknown"}</span>
        <span>Type: {site.property_type ?? "unknown"}</span>
      </div>
      <p>{site.translated_summary_zh}</p>
      <div className="actions">
        <Link className="button secondary" href={`/site-hunter/sites/${site.id}`}>
          详情
        </Link>
        <a className="button secondary" href={site.source_url} target="_blank" rel="noreferrer">
          原始链接
        </a>
      </div>
    </article>
  );
}
