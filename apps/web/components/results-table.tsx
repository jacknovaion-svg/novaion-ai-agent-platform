"use client";

import { ExternalLink } from "lucide-react";
import { useRouter } from "next/navigation";
import type { SearchResult } from "@novaion/shared/types";
import { storeDetail } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export function ResultsTable({ results }: { results: SearchResult[] }) {
  const { t } = useI18n();
  const router = useRouter();

  if (!results.length) {
    return <div className="panel muted">{t("noResults")}</div>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{t("rank")}</th>
            <th>{t("source")}</th>
            <th>{t("productName")}</th>
            <th>{t("brand")}</th>
            <th>{t("model")}</th>
            <th>{t("storeName")}</th>
            <th>{t("address")}</th>
            <th>{t("distance")}</th>
            <th>{t("price")}</th>
            <th>{t("promotion")}</th>
            <th>{t("inventoryStatus")}</th>
            <th>{t("pickupAvailable")}</th>
            <th>{t("shippingAvailable")}</th>
            <th>{t("updatedAt")}</th>
            <th>{t("recommendationScore")}</th>
            <th>{t("productLink")}</th>
          </tr>
        </thead>
        <tbody>
          {results.map((item, index) => (
            <tr key={`${item.source}-${item.product_name}-${index}`}>
              <td>{index + 1}</td>
              <td>{item.source}</td>
              <td>{item.product_name}</td>
              <td>{item.brand ?? "-"}</td>
              <td>{item.model ?? "-"}</td>
              <td>{item.store_name ?? "-"}</td>
              <td>{item.address ?? "-"}</td>
              <td>{item.distance == null ? "-" : `${item.distance} mi`}</td>
              <td>{item.price == null ? "-" : `$${item.price.toLocaleString()}`}</td>
              <td>{item.promotion ?? "-"}</td>
              <td>{item.inventory_status ?? "-"}</td>
              <td>{item.pickup_available ? "Y" : "N"}</td>
              <td>{item.shipping_available ? "Y" : "N"}</td>
              <td>{new Date(item.updated_at).toLocaleString()}</td>
              <td className="score">{item.recommendation_score}</td>
              <td>
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => {
                    storeDetail(item);
                    router.push("/detail");
                  }}
                >
                  <ExternalLink size={15} />
                  {t("viewDetails")}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
