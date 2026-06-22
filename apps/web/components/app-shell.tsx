"use client";

import { Bell, Bookmark, Building2, Cpu, Database, Factory, LandPlot, Search, Zap } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import type { Language } from "@novaion/shared/types";

const nav = [
  { href: "/", label: "search", icon: Search },
  { href: "/site-hunter", label: "siteHunter", icon: Building2 },
  { href: "/results", label: "results", icon: Database },
  { href: "/saved-searches", label: "savedSearches", icon: Bookmark },
  { href: "/alerts", label: "alerts", icon: Bell },
];

const agents = [
  { label: "hardwareHunter", icon: Cpu, active: true },
  { label: "siteHunter", icon: Building2, active: true },
  { label: "powerHunter", icon: Zap, active: false },
  { label: "landHunter", icon: LandPlot, active: false },
  { label: "supplierHunter", icon: Factory, active: false },
  { label: "dataCenterHunter", icon: Database, active: false },
];

export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { language, setLanguage, t } = useI18n();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <strong>NOVAION</strong>
          <span>{t("appName")}</span>
        </div>
        <nav className="nav">
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} className={path === item.href ? "active" : ""}>
                <Icon size={17} />
                {t(item.label)}
              </Link>
            );
          })}
        </nav>
        <div style={{ marginTop: 28 }} className="section-label">
          {t("agentCenter")}
        </div>
        <div className="agent-list" style={{ marginTop: 10 }}>
          {agents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div className="agent-row" key={agent.label}>
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Icon size={16} />
                  {t(agent.label)}
                </span>
                <span className="pill">{agent.active ? t("enabled") : t("reserved")}</span>
              </div>
            );
          })}
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <strong>{path.startsWith("/site-hunter") ? t("siteHunter") : t("hardwareHunter")}</strong>
            <div className="muted">
              {path.startsWith("/site-hunter") ? "Industrial site discovery agent" : "AI procurement search agent"}
            </div>
          </div>
          <label className="field" style={{ minWidth: 150 }}>
            <span>{t("language")}</span>
            <select className="select" value={language} onChange={(event) => setLanguage(event.target.value as Language)}>
              <option value="en">English</option>
              <option value="zh">中文</option>
              <option value="es">Español</option>
            </select>
          </label>
        </header>
        <section className="content">{children}</section>
      </main>
    </div>
  );
}
