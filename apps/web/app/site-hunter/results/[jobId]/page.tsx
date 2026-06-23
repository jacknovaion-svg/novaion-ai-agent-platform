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
  const discoveryCandidates = useMemo(() => job?.discovery_candidates ?? [], [job?.discovery_candidates]);
  const stats = job?.quality_stats;
  const anchor = job?.parsed_criteria?.search_anchor;

  return (
    <div className="grid">
      <div className="panel">
        <div className="section-label">Site Hunter Results</div>
        <h1 className="page-title">具体工业地产挂牌</h1>
        <p className="muted">Job {params.jobId} · {job?.status ?? "loading"} · {results.length} specific listings</p>
        {anchor ? (
          <div className="site-facts" style={{ marginTop: 10 }}>
            <span>Search center: {anchor.label ?? anchor.raw_input ?? "unknown"}</span>
            <span>Status: {anchor.status}</span>
            <span>Radius: {anchor.radius_miles ? `${anchor.radius_miles} mi` : "unknown"}</span>
            <span>Coordinates: {anchor.latitude && anchor.longitude ? `${anchor.latitude.toFixed(6)}, ${anchor.longitude.toFixed(6)}` : "unknown"}</span>
            <span>Resolved by: {anchor.source_name ?? "unknown"}</span>
          </div>
        ) : null}
        {error ? <p className="danger-text">{error}</p> : null}
        {stats ? (
          <div className="metric-grid quality-metrics">
            <Metric label="Raw" value={stats.raw_results} />
            <Metric label="Specific" value={stats.specific_listings} />
            <Metric label="Collections" value={stats.listing_collections} />
            <Metric label="Sources" value={stats.source_pages} />
            <Metric label="Irrelevant" value={stats.irrelevant_results} />
            <Metric label="Duplicates" value={stats.duplicates_removed} />
            <Metric label="State removed" value={stats.state_mismatch_removed} />
            <Metric label="Size removed" value={stats.size_mismatch_removed} />
            <Metric label="Budget removed" value={stats.budget_mismatch_removed} />
            <Metric label="Radius removed" value={stats.radius_mismatch_removed} />
            <Metric label="Final" value={stats.final_candidates} />
          </div>
        ) : null}
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
      {!results.length ? <div className="panel muted">本轮没有找到合格具体挂牌。分类页和来源页已放入“待继续发现来源”，不会伪装成具体地产项目。</div> : null}

      <div className="panel">
        <div className="section-label">待继续发现来源</div>
        <h2>Listing Collections / Source Pages</h2>
        <p className="muted">这些页面是真实来源或挂牌列表页，但不是独立地产挂牌，默认不进入正式候选列表。</p>
        <div className="stack-list">
          {discoveryCandidates.slice(0, 30).map((site) => (
            <DiscoveryRow site={site} key={site.id} />
          ))}
        </div>
        {!discoveryCandidates.length ? <p className="muted">暂无待继续发现来源。</p> : null}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SiteCard({ site }: { site: SiteListing }) {
  return (
    <article className="panel site-card">
      <div className="site-card-head">
        <div>
          <div className="section-label">{site.source_name} · {site.result_category}</div>
          <h2>{site.translated_title_zh ?? site.site_name}</h2>
        </div>
        <span className="score-badge">{site.preliminary_grade} · {site.preliminary_score}</span>
      </div>
      <p className="muted">{site.original_title}</p>
      <div className="site-facts">
        <span>State: {site.state ?? "unknown"}</span>
        <span>City: {site.city ?? "unknown"}</span>
        <span>Address: {site.address_status}</span>
        <span>Acres: {site.land_acres ?? "unknown"}</span>
        <span>Price: {site.asking_price_usd ? `$${site.asking_price_usd.toLocaleString()}` : "unknown"}</span>
        <span>Anchor distance: {site.distance_to_search_anchor_miles != null ? `${site.distance_to_search_anchor_miles} mi` : "unknown"}</span>
        <span>Type: {site.property_type ?? "unknown"}</span>
        <span>Completeness: {Math.round(site.data_completeness_score * 100)}%</span>
      </div>
      <p>{site.translated_summary_zh}</p>
      {site.quality_flags.length ? <p className="muted">{site.quality_flags.join(" · ")}</p> : null}
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

function DiscoveryRow({ site }: { site: SiteListing }) {
  return (
    <div className="compact-row source-row">
      <span>
        <strong>{site.result_category}</strong> · {site.original_title}
        <small className="muted"> · {site.source_name} · {site.state ?? "unknown"}</small>
      </span>
      <a className="button secondary" href={site.source_url} target="_blank" rel="noreferrer">
        打开来源
      </a>
    </div>
  );
}
