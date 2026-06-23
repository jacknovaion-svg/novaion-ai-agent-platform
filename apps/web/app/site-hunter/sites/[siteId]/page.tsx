"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { LandIdReview, NearbyPowerAsset, SiteListing, SitePowerAssessment } from "@novaion/shared/types";
import { getSiteHunterSite, reviewSiteHunterSite, updateLandIdReview } from "@/lib/api";

export default function SiteHunterSiteDetailPage() {
  const params = useParams<{ siteId: string }>();
  const [site, setSite] = useState<SiteListing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [landForm, setLandForm] = useState<Partial<LandIdReview>>({});

  useEffect(() => {
    getSiteHunterSite(params.siteId)
      .then((next) => {
        setSite(next);
        setLandForm(next.land_id_review ?? {});
        setError(null);
      })
      .catch((err) => {
        setSite(null);
        setError(err instanceof Error ? err.message : "Failed to load site");
      });
  }, [params.siteId]);

  async function review(status: string) {
    try {
      const updated = await reviewSiteHunterSite(params.siteId, status);
      setSite(updated);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    }
  }

  async function saveLandIdReview(status?: string) {
    if (!site) return;
    try {
      const updated = await updateLandIdReview(params.siteId, {
        land_id_review_status: status ?? landForm.land_id_review_status ?? "in_review",
        land_id_map_url: landForm.land_id_map_url ?? site.land_id_review.land_id_map_url,
        parcel_id: landForm.parcel_id,
        owner_name: landForm.owner_name,
        owner_mailing_address: landForm.owner_mailing_address,
        parcel_acres: landForm.parcel_acres ?? null,
        nearest_substation_name: landForm.nearest_substation_name,
        nearest_substation_distance: landForm.nearest_substation_distance ?? null,
        nearest_transmission_voltage: landForm.nearest_transmission_voltage ?? null,
        manual_notes: landForm.manual_notes,
      });
      setSite(updated);
      setLandForm(updated.land_id_review);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Land id review failed");
    }
  }

  async function copyPowerContext() {
    if (!site) return;
    const assessment = site.power_assessment;
    const text = [
      site.standardized_address ?? `${site.address_line_1 ?? ""}, ${site.city ?? ""}, ${site.state ?? ""} ${site.zip_code ?? ""}`,
      assessment?.latitude && assessment?.longitude ? `${assessment.latitude}, ${assessment.longitude}` : "coordinates unknown",
    ].join("\n");
    await navigator.clipboard.writeText(text);
  }

  if (!site) {
    return (
      <div className="panel muted">
        Loading site...
        {error ? <p className="danger-text">{error}</p> : null}
      </div>
    );
  }

  return (
    <div className="grid">
      <div className="panel">
        <div className="section-label">Site Detail</div>
        <h1 className="page-title">{site.translated_title_zh ?? site.site_name}</h1>
        <p className="muted">{site.original_title}</p>
        <div className="site-facts" style={{ marginTop: 12 }}>
          <span>Category: {site.result_category}</span>
          <span>Completeness: {Math.round(site.data_completeness_score * 100)}%</span>
          <span>Address status: {site.address_status}</span>
          <span>Price status: {site.price_status}</span>
          <span>Source confidence: {site.source_confidence}</span>
        </div>
        <div className="actions">
          <button className="button primary" type="button" onClick={() => review("investigate")}>加入进一步调查</button>
          <button className="button secondary" type="button" onClick={() => review("kept")}>保留</button>
          <button className="button secondary" type="button" onClick={() => review("rejected")}>拒绝</button>
          <button className="button secondary" type="button" onClick={() => review("duplicate")}>标记重复</button>
        </div>
        {error ? <p className="danger-text">{error}</p> : null}
        {site.review_status ? <p className="muted">Review status: {site.review_status}</p> : null}
      </div>

      <section className="panel">
        <div className="section-label">地产信息</div>
        <div className="fact-grid">
          <span>Address: {site.address_line_1 ?? "unknown"}</span>
          <span>City: {site.city ?? "unknown"}</span>
          <span>County: {site.county ?? "unknown"}</span>
          <span>State: {site.state ?? "unknown"}</span>
          <span>ZIP: {site.zip_code ?? "unknown"}</span>
          <span>Acres: {site.land_acres ?? "unknown"}</span>
          <span>Building sqft: {site.building_sqft ?? "unknown"}</span>
          <span>Price: {site.asking_price_usd ? `$${site.asking_price_usd.toLocaleString()}` : "unknown"}</span>
          <span>Broker/source: {site.broker_company ?? site.source_name}</span>
          <span>Zoning: {site.zoning ?? "unknown"}</span>
        </div>
      </section>

      <PowerAssessmentPanel assessment={site.power_assessment} landIdReview={site.land_id_review} onCopy={copyPowerContext} />

      <section className="panel">
        <div className="section-label">Land id 人工核查</div>
        <div className="actions">
          <a className="button secondary" href={site.land_id_review.land_id_map_url ?? "https://id.land/"} target="_blank" rel="noreferrer">
            打开Land id进行核查
          </a>
          <button className="button secondary" type="button" onClick={copyPowerContext}>复制地址和经纬度</button>
          <button className="button primary" type="button" onClick={() => saveLandIdReview("manually_verified")}>标记与自动分析一致</button>
          <button className="button secondary" type="button" onClick={() => saveLandIdReview("mismatch_found")}>标记发现不一致</button>
        </div>
        <div className="form-grid" style={{ marginTop: 14 }}>
          <label className="field">
            <span>Parcel ID / APN</span>
            <input className="input" value={landForm.parcel_id ?? ""} onChange={(event) => setLandForm({ ...landForm, parcel_id: event.target.value })} />
          </label>
          <label className="field">
            <span>Owner name</span>
            <input className="input" value={landForm.owner_name ?? ""} onChange={(event) => setLandForm({ ...landForm, owner_name: event.target.value })} />
          </label>
          <label className="field">
            <span>Parcel acres</span>
            <input className="input" type="number" value={landForm.parcel_acres ?? ""} onChange={(event) => setLandForm({ ...landForm, parcel_acres: Number(event.target.value) || undefined })} />
          </label>
          <label className="field">
            <span>Nearest substation</span>
            <input className="input" value={landForm.nearest_substation_name ?? ""} onChange={(event) => setLandForm({ ...landForm, nearest_substation_name: event.target.value })} />
          </label>
          <label className="field">
            <span>Substation distance miles</span>
            <input className="input" type="number" value={landForm.nearest_substation_distance ?? ""} onChange={(event) => setLandForm({ ...landForm, nearest_substation_distance: Number(event.target.value) || undefined })} />
          </label>
          <label className="field">
            <span>Transmission voltage kV</span>
            <input className="input" type="number" value={landForm.nearest_transmission_voltage ?? ""} onChange={(event) => setLandForm({ ...landForm, nearest_transmission_voltage: Number(event.target.value) || undefined })} />
          </label>
        </div>
        <label className="field" style={{ marginTop: 14 }}>
          <span>Manual notes</span>
          <textarea className="textarea" value={landForm.manual_notes ?? ""} onChange={(event) => setLandForm({ ...landForm, manual_notes: event.target.value })} />
        </label>
        <div className="actions">
          <button className="button secondary" type="button" onClick={() => saveLandIdReview("in_review")}>录入Land id核查结果</button>
        </div>
        <p className="muted">Land id status: {site.land_id_review.land_id_review_status} · Reviewed at: {site.land_id_review.reviewed_at ?? "not reviewed"}</p>
      </section>

      <section className="panel">
        <div className="section-label">原始资料</div>
        <p><strong>English title:</strong> {site.original_title}</p>
        <p><strong>English description:</strong> {site.original_description ?? "unknown"}</p>
        <p><strong>中文摘要:</strong> {site.translated_summary_zh ?? "unknown"}</p>
        <a className="button secondary" href={site.source_url} target="_blank" rel="noreferrer">打开原始链接</a>
      </section>

      <section className="panel">
        <div className="section-label">初步分析</div>
        <p>Score: {site.preliminary_score} · Grade: {site.preliminary_grade}</p>
        <ul>
          {site.score_reasons.map((reason) => <li key={reason}>{reason}</li>)}
        </ul>
        <div className="section-label">风险和未知信息</div>
        <ul>
          {site.quality_flags.map((flag) => <li key={flag}>{flag}</li>)}
          {site.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          {site.missing_fields.map((field) => <li key={field}>{field}: unknown</li>)}
        </ul>
      </section>
    </div>
  );
}

function PowerAssessmentPanel({ assessment, landIdReview, onCopy }: { assessment?: SitePowerAssessment | null; landIdReview: LandIdReview; onCopy: () => void }) {
  if (!assessment) {
    return <section className="panel muted">周边电力设施：等待本地初筛。</section>;
  }
  return (
    <section className="panel">
      <div className="section-label">周边电力设施</div>
      <h2>Power Screening</h2>
      <p className="danger-text">{assessment.assessment_warning}</p>
      <div className="fact-grid">
        <span>Address status: {assessment.address_status}</span>
        <span>Standardized address: {assessment.standardized_address ?? "unknown"}</span>
        <span>Coordinates: {assessment.latitude && assessment.longitude ? `${assessment.latitude.toFixed(6)}, ${assessment.longitude.toFixed(6)}` : "unknown"}</span>
        <span>Geocoding: {assessment.geocoding_source ?? "unknown"} · {Math.round(assessment.geocoding_confidence * 100)}%</span>
        <span>Capacity: {assessment.capacity_status}</span>
        <span>Known voltage: {assessment.known_voltage_kv ? `${assessment.known_voltage_kv} kV` : "unknown"}</span>
        <span>Likely utility: {assessment.likely_utility.likely_utility ?? "unknown"}</span>
        <span>Utility confidence: {assessment.likely_utility.confidence_level}</span>
        <span>Land id review: {landIdReview.land_id_review_status}</span>
      </div>
      {assessment.error_message ? <p className="muted">{assessment.error_message}</p> : null}
      <div className="actions">
        <button className="button secondary" type="button" onClick={onCopy}>复制地址和经纬度</button>
      </div>
      <div className="power-grid">
        <AssetCard title="最近疑似变电站" asset={assessment.nearest_substation} />
        <AssetCard title="最近输电线路" asset={assessment.nearest_transmission_line} />
      </div>
      <div className="section-label">搜索半径内设施数量</div>
      <div className="site-facts">
        {Object.entries(assessment.search_radius_counts).map(([radius, count]) => <span key={radius}>{radius}: {count}</span>)}
      </div>
      <div className="section-label">数据来源 / GIS发现任务</div>
      <div className="stack-list">
        {assessment.power_source_records.slice(0, 8).map((record) => (
          <div className="compact-row" key={`${record.source_name}-${record.generated_query}`}>
            <span>{record.generated_query ?? record.source_name}</span>
            {record.source_url ? <a className="button secondary" href={record.source_url} target="_blank" rel="noreferrer">打开</a> : <span className="pill">{record.confidence_level}</span>}
          </div>
        ))}
      </div>
    </section>
  );
}

function AssetCard({ title, asset }: { title: string; asset?: NearbyPowerAsset | null }) {
  return (
    <div className="metric power-card">
      <span>{title}</span>
      {asset ? (
        <>
          <strong>{asset.distance_miles != null ? `${asset.distance_miles} mi` : "unknown"}</strong>
          <p>Name: {asset.asset_name ?? "unknown"}</p>
          <p>Voltage: {asset.voltage_kv ? `${asset.voltage_kv} kV` : "unknown"}</p>
          <p>Owner/operator: {asset.owner ?? asset.operator ?? "unknown"}</p>
          <p>Source: {asset.source_name}</p>
          <p>Dataset: {asset.dataset_version ?? "unknown"}</p>
          <p>Confidence: {asset.confidence_level}</p>
          {asset.source_url ? <a href={asset.source_url} target="_blank" rel="noreferrer">Open source</a> : null}
        </>
      ) : (
        <strong>unknown</strong>
      )}
    </div>
  );
}
