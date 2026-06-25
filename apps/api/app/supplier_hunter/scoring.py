from __future__ import annotations

from app.supplier_hunter.models import SupplierCategory, SupplierResult, VerificationStatus


class SupplierScoringService:
    def score(self, suppliers: list[SupplierResult]) -> list[SupplierResult]:
        for supplier in suppliers:
            score = 0.0
            reasons: list[str] = []
            if supplier.supplier_category == SupplierCategory.A:
                score += 25
                reasons.append("Likely direct enterprise/data-center asset source")
            elif supplier.supplier_category == SupplierCategory.B:
                score += 18
                reasons.append("ITAD/asset disposition capability")
            elif supplier.supplier_category == SupplierCategory.C:
                score += 10
                reasons.append("Used enterprise hardware wholesale/refurbishing signal")

            if supplier.asset_remarketing or supplier.direct_asset_purchasing:
                score += 20
                reasons.append("Asset remarketing or direct purchasing signal")
            if supplier.server_recycling or "servers" in supplier.equipment_types:
                score += 15
                reasons.append("Server/data-center equipment signal")
            cert_points = self._cert_points(supplier)
            if cert_points:
                score += cert_points
                reasons.append("Certification signal requires verification")
            if supplier.bulk_sales or supplier.wholesale:
                score += 10
                reasons.append("Bulk sales / wholesale signal")
            if supplier.data_center_decommissioning:
                score += 5
                reasons.append("Onsite decommissioning signal")
            if supplier.phone:
                score += 3
            if supplier.email:
                score += 2
            if supplier.state or supplier.city:
                score += 5
            supplier.supplier_score = round(min(score, 100), 2)
            supplier.score_reasons = reasons
        return sorted(suppliers, key=lambda item: item.supplier_score, reverse=True)

    def _cert_points(self, supplier: SupplierResult) -> float:
        points = 0.0
        for status in [supplier.r2_certified, supplier.e_stewards_certified, supplier.naid_aaa_certified]:
            if status == VerificationStatus.VERIFIED:
                points += 5
            elif status in {VerificationStatus.DIRECTORY_DISCOVERED, VerificationStatus.CLAIMED_ON_WEBSITE}:
                points += 3
        return min(points, 15)

