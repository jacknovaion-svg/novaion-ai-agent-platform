"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { SiteListing } from "@novaion/shared/types";
import { getSiteHunterSite, reviewSiteHunterSite } from "@/lib/api";

export default function SiteHunterSiteDetailPage() {
  const params = useParams<{ siteId: string }>();
  const [site, setSite] = useState<SiteListing | null>(null);

  useEffect(() => {
    getSiteHunterSite(params.siteId).then(setSite).catch(() => setSite(null));
  }, [params.siteId]);

  async function review(status: string) {
    const updated = await reviewSiteHunterSite(params.siteId, status);
    setSite(updated);
  }

  if (!site) return <div className="panel muted">Loading site...</div>;

  return (
    <div className="grid">
      <div className="panel">
        <div className="section-label">Site Detail</div>
        <h1 className="page-title">{site.translated_title_zh ?? site.site_name}</h1>
        <p className="muted">{site.original_title}</p>
        <div className="actions">
          <button className="button primary" type="button" onClick={() => review("investigate")}>加入进一步调查</button>
          <button className="button secondary" type="button" onClick={() => review("kept")}>保留</button>
          <button className="button secondary" type="button" onClick={() => review("rejected")}>拒绝</button>
          <button className="button secondary" type="button" onClick={() => review("duplicate")}>标记重复</button>
        </div>
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
          <span>Zoning: {site.zoning ?? "unknown"}</span>
        </div>
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
          {site.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          {site.missing_fields.map((field) => <li key={field}>{field}: unknown</li>)}
        </ul>
      </section>
    </div>
  );
}
