"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { SiteHunterJob } from "@novaion/shared/types";
import { getSiteHunterJob } from "@/lib/api";

const doneStatuses = new Set(["completed", "partially_completed", "failed"]);

export default function SiteHunterProgressPage() {
  const params = useParams<{ jobId: string }>();
  const [job, setJob] = useState<SiteHunterJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const next = await getSiteHunterJob(params.jobId);
        if (!cancelled) {
          setJob(next);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load job");
      }
    }
    load();
    const timer = window.setInterval(() => {
      if (!job || !doneStatuses.has(job.status)) load();
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [params.jobId, job?.status]);

  return (
    <div className="grid">
      <div className="panel">
        <div className="section-label">Search Progress</div>
        <h1 className="page-title">Site Hunter Job</h1>
        {error ? <p className="danger-text">{error}</p> : null}
        <div className="metric-grid">
          <div className="metric">
            <span>Status</span>
            <strong>{job?.status ?? "loading"}</strong>
          </div>
          <div className="metric">
            <span>Queries</span>
            <strong>{job?.generated_queries.length ?? 0}</strong>
          </div>
          <div className="metric">
            <span>Sources</span>
            <strong>{job?.discovered_sources.length ?? 0}</strong>
          </div>
          <div className="metric">
            <span>Results</span>
            <strong>{job?.results.length ?? 0}</strong>
          </div>
        </div>
        <div className="actions">
          <Link className="button secondary" href={`/site-hunter/results/${params.jobId}`}>
            查看结果
          </Link>
        </div>
      </div>

      <div className="panel">
        <div className="section-label">解析后的中文条件</div>
        <p>{job?.parsed_criteria?.parsed_summary_zh ?? "等待解析..."}</p>
      </div>

      <div className="panel">
        <div className="section-label">实际执行的英文搜索词</div>
        <p className="muted">
          当前本地默认使用公开 DuckDuckGo HTML 搜索发现。Crexi 是 search-backed discovery，不是官方 API。
        </p>
        <div className="stack-list">
          {(job?.generated_queries ?? []).slice(0, 14).map((query) => (
            <div className="compact-row" key={query.id}>
              <span>{query.generated_query_en}</span>
              <span className="pill">{query.source_group}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="section-label">数据源执行状态</div>
        <div className="stack-list">
          {(job?.source_runs ?? []).map((run) => (
            <div className="compact-row" key={run.id}>
              <span>
                {run.source_name}
                {run.error_message ? <small className="danger-text"> · {run.error_message}</small> : null}
              </span>
              <span className="pill">{run.status} · {run.result_count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
