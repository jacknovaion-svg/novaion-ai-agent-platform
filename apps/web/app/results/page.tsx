"use client";

import { useEffect, useState } from "react";
import type { SearchJob } from "@novaion/shared/types";
import { ResultsTable } from "@/components/results-table";
import { loadResults } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function ResultsPage() {
  const { t } = useI18n();
  const [job, setJob] = useState<SearchJob | null>(null);

  useEffect(() => {
    setJob(loadResults());
  }, []);

  return (
    <div className="grid">
      <div>
        <h1 className="page-title">{t("results")}</h1>
        {job ? (
          <p className="muted">
            {job.query} · {job.quantity} · {job.zip_code ?? "-"} · {job.mode}
          </p>
        ) : null}
      </div>
      <ResultsTable results={job?.results ?? []} />
    </div>
  );
}
