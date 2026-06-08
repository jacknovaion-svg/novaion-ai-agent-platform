"use client";

import { Bell, Mail, Send, TrendingDown } from "lucide-react";
import { useI18n } from "@/lib/i18n";

const alertItems = [
  { key: "emailAlert", icon: Mail },
  { key: "telegramAlert", icon: Send },
  { key: "priceDropAlert", icon: TrendingDown },
  { key: "backInStockAlert", icon: Bell },
];

export default function AlertsPage() {
  const { t } = useI18n();

  return (
    <div className="grid">
      <h1 className="page-title">{t("alerts")}</h1>
      <div className="agent-list">
        {alertItems.map((item) => {
          const Icon = item.icon;
          return (
            <div className="agent-row" key={item.key}>
              <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Icon size={18} />
                {t(item.key)}
              </span>
              <span className="pill">{t("reserved")}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
