"use client";

import { ExternalLink, Phone, Search } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { SupplierResult, SupplierSearchJob } from "@novaion/shared/types";
import { getSupplierHunterJob, reviewSupplier } from "@/lib/api";

export default function SupplierHunterResultsPage() {
  const params = useParams<{ jobId: string }>();
  const [job, setJob] = useState<SupplierSearchJob | null>(null);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [cityFilter, setCityFilter] = useState("");
  const [capabilityFilter, setCapabilityFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const next = await getSupplierHunterJob(params.jobId);
        if (!active) return;
        setJob(next);
        setError(null);
        if (!["completed", "partially_completed", "failed"].includes(next.status)) {
          window.setTimeout(load, 2500);
        }
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load Supplier Hunter job");
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [params.jobId]);

  const suppliers = useMemo(() => {
    return (job?.results ?? []).filter((supplier) => {
      if (categoryFilter && supplier.supplier_category !== categoryFilter) return false;
      if (cityFilter) {
        const haystack = `${supplier.city ?? ""} ${supplier.state ?? ""}`.toLowerCase();
        if (!haystack.includes(cityFilter.toLowerCase())) return false;
      }
      if (capabilityFilter) {
        const haystack = [
          supplier.company_type,
          supplier.equipment_types.join(" "),
          supplier.score_reasons.join(" "),
          supplier.quality_flags.join(" "),
        ].join(" ").toLowerCase();
        if (!haystack.includes(capabilityFilter.toLowerCase())) return false;
      }
      return true;
    });
  }, [job?.results, categoryFilter, cityFilter, capabilityFilter]);

  async function markSupplier(supplierId: string, status: string) {
    const updated = await reviewSupplier(supplierId, status);
    setJob((current) => {
      if (!current) return current;
      return {
        ...current,
        results: current.results.map((supplier) => (supplier.supplier_id === supplierId ? { ...supplier, ...updated } : supplier)),
      };
    });
  }

  return (
    <div className="grid">
      <section className="panel">
        <div className="section-label">Hardware Hunter / Supplier Discovery</div>
        <h1 className="page-title">供应商发现结果</h1>
        <p className="muted">Job {params.jobId} · {job?.status ?? "loading"} · {suppliers.length} suppliers</p>
        {error ? <p className="danger-text">{error}</p> : null}
        {job?.parsed_criteria?.parsed_summary_zh ? <p>{job.parsed_criteria.parsed_summary_zh}</p> : null}
        {job?.quality_stats ? (
          <div className="metric-grid quality-metrics">
            <Metric label="Raw" value={job.quality_stats.raw_results} />
            <Metric label="Normalized" value={job.quality_stats.normalized_suppliers} />
            <Metric label="Duplicates" value={job.quality_stats.duplicates_removed} />
            <Metric label="Low value filtered" value={job.quality_stats.low_value_filtered} />
            <Metric label="Final" value={job.quality_stats.final_suppliers} />
            <Metric label="High value" value={job.quality_stats.high_value_suppliers} />
          </div>
        ) : null}
        <div className="form-grid" style={{ marginTop: 14 }}>
          <label className="field">
            <span>Category</span>
            <select className="select" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
              <option value="">All</option>
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="C">C</option>
            </select>
          </label>
          <label className="field">
            <span>City / State</span>
            <input className="input" value={cityFilter} onChange={(event) => setCityFilter(event.target.value)} />
          </label>
          <label className="field">
            <span>Capability</span>
            <input className="input" value={capabilityFilter} onChange={(event) => setCapabilityFilter(event.target.value)} placeholder="server, wholesale, remarketing" />
          </label>
        </div>
      </section>

      {job?.region_subjobs?.length ? (
        <section className="panel">
          <div className="section-label">Texas Region Subjobs</div>
          <div className="stack-list">
            {job.region_subjobs.map((region) => (
              <div className="compact-row" key={region.id}>
                <span>
                  <strong>{region.region_name}</strong>
                  <small className="muted"> · queries {region.executed_query_count}/{region.generated_query_count} · raw {region.raw_result_count} · suppliers {region.supplier_count} · high value {region.high_value_count}</small>
                </span>
                <span className="pill">{region.status}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="site-card-grid">
        {suppliers.map((supplier) => (
          <SupplierCard supplier={supplier} key={supplier.supplier_id} onReview={markSupplier} />
        ))}
      </div>
      {!suppliers.length ? <div className="panel muted">本轮还没有找到合格高价值供应商；低价值或需排除结果不会冒充一手供应商。</div> : null}
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

function SupplierCard({ supplier, onReview }: { supplier: SupplierResult; onReview: (supplierId: string, status: string) => void }) {
  return (
    <article className="panel site-card">
      <div className="site-card-head">
        <div>
          <div className="section-label">Category {supplier.supplier_category} · {supplier.source_name}</div>
          <h2>{supplier.company_name}</h2>
        </div>
        <span className="score-badge">{supplier.supplier_score}</span>
      </div>
      <div className="site-facts">
        <span>{supplier.city ?? "unknown"}, {supplier.state ?? "unknown"}</span>
        <span>{supplier.company_type ?? "unknown"}</span>
        <span>R2: {supplier.r2_certified}</span>
        <span>e-Stewards: {supplier.e_stewards_certified}</span>
        <span>NAID: {supplier.naid_aaa_certified}</span>
        <span>DC decom: {supplier.data_center_decommissioning ? "yes" : "unknown"}</span>
        <span>Remarketing: {supplier.asset_remarketing ? "yes" : "unknown"}</span>
        <span>Bulk: {supplier.bulk_sales || supplier.wholesale ? "yes" : "unknown"}</span>
      </div>
      <p className="muted">Equipment: {supplier.equipment_types.length ? supplier.equipment_types.join(", ") : "unknown"}</p>
      {supplier.score_reasons.length ? <p>{supplier.score_reasons.join(" · ")}</p> : null}
      {supplier.quality_flags.length ? <p className="muted">{supplier.quality_flags.join(" · ")}</p> : null}
      <div className="actions">
        {supplier.website ? (
          <a className="button secondary" href={supplier.website} target="_blank" rel="noreferrer">
            <ExternalLink size={16} />
            Website
          </a>
        ) : null}
        {supplier.phone ? (
          <a className="button secondary" href={`tel:${supplier.phone}`}>
            <Phone size={16} />
            Phone
          </a>
        ) : null}
        <a className="button secondary" href={supplier.source_url} target="_blank" rel="noreferrer">
          Source
        </a>
      </div>
      <div className="actions">
        <button className="button secondary" type="button" onClick={() => onReview(supplier.supplier_id, "kept")}>保留</button>
        <button className="button secondary" type="button" onClick={() => onReview(supplier.supplier_id, "contact")}>联系</button>
        <button className="button primary" type="button" onClick={() => onReview(supplier.supplier_id, "investigate")}>进一步调查</button>
        <button className="button secondary" type="button" onClick={() => onReview(supplier.supplier_id, "rejected")}>拒绝</button>
      </div>
      <p className="muted">Review: {supplier.review_status} · Confidence: {supplier.confidence_level}</p>
    </article>
  );
}

