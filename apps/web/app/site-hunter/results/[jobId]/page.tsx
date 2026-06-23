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
  const [cityCountyFilter, setCityCountyFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [minAcresFilter, setMinAcresFilter] = useState("");
  const [maxPriceFilter, setMaxPriceFilter] = useState("");
  const [minVoltageFilter, setMinVoltageFilter] = useState("");
  const [maxSubstationDistanceFilter, setMaxSubstationDistanceFilter] = useState("");
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
    return all.filter((item) => {
      if (stateFilter && !(item.state ?? "").toLowerCase().includes(stateFilter.toLowerCase())) return false;
      if (cityCountyFilter) {
        const haystack = `${item.city ?? ""} ${item.county ?? ""}`.toLowerCase();
        if (!haystack.includes(cityCountyFilter.toLowerCase())) return false;
      }
      if (typeFilter && !(item.property_type ?? "").toLowerCase().includes(typeFilter.toLowerCase())) return false;
      if (minAcresFilter && item.land_acres != null && item.land_acres < Number(minAcresFilter)) return false;
      if (maxPriceFilter && item.asking_price_usd != null && item.asking_price_usd > Number(maxPriceFilter)) return false;
      const knownVoltage = item.power_assessment?.known_voltage_kv ?? item.power_assessment?.nearest_transmission_line?.voltage_kv;
      if (minVoltageFilter && knownVoltage != null && knownVoltage < Number(minVoltageFilter)) return false;
      const substationDistance = item.power_assessment?.nearest_substation?.distance_miles;
      if (maxSubstationDistanceFilter && substationDistance != null && substationDistance > Number(maxSubstationDistanceFilter)) return false;
      return true;
    });
  }, [job?.results, stateFilter, cityCountyFilter, typeFilter, minAcresFilter, maxPriceFilter, minVoltageFilter, maxSubstationDistanceFilter]);
  const discoveryCandidates = useMemo(() => job?.discovery_candidates ?? [], [job?.discovery_candidates]);
  const stats = job?.quality_stats;
  const anchor = job?.parsed_criteria?.search_anchor;

  return (
    <div className="grid">
      <div className="panel">
        <div className="section-label">Site Hunter Results</div>
        <h1 className="page-title">具体工业地产挂牌</h1>
        <p className="muted">Job {params.jobId} · {job?.status ?? "loading"} · {job?.job_mode ?? "loading"} · {results.length} specific listings</p>
        {job?.state_job ? (
          <div className="site-facts" style={{ marginTop: 10 }}>
            <span>State: {String(job.state_job.state_name ?? "unknown")}</span>
            <span>State code: {String(job.state_job.state_code ?? "unknown")}</span>
            <span>Regions executed: {job.region_subjobs.filter((item) => item.executed_query_count > 0).length}</span>
            <span>Power screened: {stats?.power_screened_candidates ?? 0}</span>
          </div>
        ) : null}
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
            <Metric label="Power screened" value={stats.power_screened_candidates} />
          </div>
        ) : null}
        <div className="form-grid" style={{ marginTop: 14 }}>
          <label className="field">
            <span>按州筛选</span>
            <input className="input" value={stateFilter} onChange={(event) => setStateFilter(event.target.value)} />
          </label>
          <label className="field">
            <span>城市/县筛选</span>
            <input className="input" value={cityCountyFilter} onChange={(event) => setCityCountyFilter(event.target.value)} />
          </label>
          <label className="field">
            <span>地产类型</span>
            <input className="input" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} />
          </label>
          <label className="field">
            <span>Min acres</span>
            <input className="input" type="number" value={minAcresFilter} onChange={(event) => setMinAcresFilter(event.target.value)} />
          </label>
          <label className="field">
            <span>Max price</span>
            <input className="input" type="number" value={maxPriceFilter} onChange={(event) => setMaxPriceFilter(event.target.value)} />
          </label>
          <label className="field">
            <span>Min line voltage kV</span>
            <input className="input" type="number" value={minVoltageFilter} onChange={(event) => setMinVoltageFilter(event.target.value)} />
          </label>
          <label className="field">
            <span>Max substation miles</span>
            <input className="input" type="number" value={maxSubstationDistanceFilter} onChange={(event) => setMaxSubstationDistanceFilter(event.target.value)} />
          </label>
        </div>
      </div>
      {job?.region_subjobs?.length ? (
        <div className="panel">
          <div className="section-label">State Region Subjobs</div>
          <h2>已执行区域</h2>
          <div className="stack-list">
            {job.region_subjobs.map((region) => (
              <div className="compact-row" key={region.id}>
                <span>
                  <strong>{region.region_name}</strong>
                  <small className="muted"> · {region.region_type} · queries {region.executed_query_count}/{region.generated_query_count} · raw {region.raw_result_count} · candidates {region.final_candidate_count} · power {region.power_screened_count}</small>
                </span>
                <span className="pill">{region.status}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
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
        <span>Region: {String(site.raw_data_json.region_name ?? "unknown")}</span>
        <span>Known voltage: {site.power_assessment?.known_voltage_kv ? `${site.power_assessment.known_voltage_kv} kV` : "unknown"}</span>
        <span>Substation: {site.power_assessment?.nearest_substation?.distance_miles != null ? `${site.power_assessment.nearest_substation.distance_miles} mi` : "unknown"}</span>
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
