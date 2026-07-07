from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.hardware_daily.models import ListingStatus, RawHardwareListing


STATE_NAMES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "DC": "Washington, D.C.",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}

STATE_ALIASES = {code.lower(): code for code in STATE_NAMES}
STATE_ALIASES.update({name.lower(): code for code, name in STATE_NAMES.items()})
STATE_CODE_PATTERN = "|".join(sorted(STATE_NAMES, key=len, reverse=True))


@dataclass(frozen=True)
class HardwareStateMatch:
    requested_states: list[str]
    detected_state: str | None
    matched_requested_state: str | None
    state_match_status: str
    filter_reason: str | None = None


class HardwareStateMatcher:
    def normalize_state(self, value: str | None) -> str | None:
        if not value:
            return None
        cleaned = re.sub(r"\s+", " ", str(value).strip().replace(".", ""))
        if not cleaned:
            return None
        alias = STATE_ALIASES.get(cleaned.lower())
        if alias:
            return alias
        upper = cleaned.upper()
        return upper if upper in STATE_NAMES else None

    def match(self, raw: RawHardwareListing, fallback_requested_states: list[str] | None = None) -> HardwareStateMatch:
        requested_states = self._requested_states(raw, fallback_requested_states or [])
        detected_state = self.detect(raw)
        if not requested_states:
            return HardwareStateMatch([], detected_state, detected_state, "matched")
        if detected_state and detected_state in requested_states:
            return HardwareStateMatch(requested_states, detected_state, detected_state, "matched")
        if detected_state:
            return HardwareStateMatch(requested_states, detected_state, None, "mismatched", "state_mismatch")
        return HardwareStateMatch(requested_states, None, None, "unknown", "location_unknown")

    def apply(self, raw: RawHardwareListing, fallback_requested_states: list[str] | None = None) -> HardwareStateMatch:
        match = self.match(raw, fallback_requested_states=fallback_requested_states)
        payload = {
            "requested_states": match.requested_states,
            "requested_state": match.requested_states[0] if len(match.requested_states) == 1 else None,
            "detected_state": match.detected_state,
            "matched_requested_state": match.matched_requested_state,
            "state_match_status": match.state_match_status,
            "filter_reason": match.filter_reason,
        }
        raw.raw_data.update(payload)
        raw.raw_data["state_match"] = payload
        if match.state_match_status == "unknown" and match.requested_states:
            detail = dict(raw.raw_data.get("detail") or {})
            detail["needs_manual_review"] = True
            detail["listing_status"] = ListingStatus.NEEDS_MANUAL_REVIEW.value
            detail["status_check_result"] = "Location needs verification"
            raw.raw_data["detail"] = detail
        return match

    def detect(self, raw: RawHardwareListing) -> str | None:
        detail = dict(raw.raw_data.get("detail") or {})
        structured_values = [
            detail.get("location_state"),
            detail.get("state"),
            raw.raw_data.get("location_state"),
            raw.raw_data.get("state"),
        ]
        for value in structured_values:
            normalized = self.normalize_state(str(value) if value is not None else None)
            if normalized:
                return normalized

        text_values = [
            detail.get("location"),
            detail.get("address"),
            detail.get("title"),
            detail.get("description"),
            raw.original_title,
            raw.original_description,
            raw.raw_data.get("location"),
            raw.raw_data.get("source_page_text"),
        ]
        text = " ".join(str(value or "") for value in text_values)
        return self._detect_from_text(text)

    def _requested_states(self, raw: RawHardwareListing, fallback_requested_states: list[str]) -> list[str]:
        values: list[Any] = []
        raw_requested_states = raw.raw_data.get("requested_states")
        if isinstance(raw_requested_states, list):
            values.extend(raw_requested_states)
        values.append(raw.raw_data.get("requested_state"))
        values.extend(fallback_requested_states)
        output: list[str] = []
        for value in values:
            normalized = self.normalize_state(str(value) if value is not None else None)
            if normalized and normalized not in output:
                output.append(normalized)
        return output

    def _detect_from_text(self, text: str) -> str | None:
        if not text:
            return None
        state_of = re.search(r"\bState\s+of\s+([A-Za-z .]+?)\b(?:\s|$|\[|,|;|:)", text, flags=re.I)
        if state_of:
            normalized = self.normalize_state(state_of.group(1))
            if normalized:
                return normalized
        city_code = re.search(rf"\b[A-Z][A-Za-z .'-]+,\s*({STATE_CODE_PATTERN})\b", text)
        if city_code:
            normalized = self.normalize_state(city_code.group(1))
            if normalized:
                return normalized
        for code, name in STATE_NAMES.items():
            if re.search(rf"\b{re.escape(name)}\b", text, flags=re.I):
                return code
        return None


hardware_state_matcher = HardwareStateMatcher()
