from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class USState:
    code: str
    name: str
    zh_names: tuple[str, ...] = ()


US_STATES: tuple[USState, ...] = (
    USState("AL", "Alabama", ("阿拉巴马",)),
    USState("AK", "Alaska", ("阿拉斯加",)),
    USState("AZ", "Arizona", ("亚利桑那",)),
    USState("AR", "Arkansas", ("阿肯色",)),
    USState("CA", "California", ("加州", "加利福尼亚")),
    USState("CO", "Colorado", ("科罗拉多",)),
    USState("CT", "Connecticut", ("康涅狄格",)),
    USState("DE", "Delaware", ("特拉华",)),
    USState("FL", "Florida", ("佛州", "佛罗里达")),
    USState("GA", "Georgia", ("乔治亚", "佐治亚")),
    USState("HI", "Hawaii", ("夏威夷",)),
    USState("ID", "Idaho", ("爱达荷",)),
    USState("IL", "Illinois", ("伊利诺伊",)),
    USState("IN", "Indiana", ("印第安纳",)),
    USState("IA", "Iowa", ("爱荷华",)),
    USState("KS", "Kansas", ("堪萨斯",)),
    USState("KY", "Kentucky", ("肯塔基",)),
    USState("LA", "Louisiana", ("路易斯安那",)),
    USState("ME", "Maine", ("缅因",)),
    USState("MD", "Maryland", ("马里兰",)),
    USState("MA", "Massachusetts", ("马萨诸塞", "麻省")),
    USState("MI", "Michigan", ("密歇根",)),
    USState("MN", "Minnesota", ("明尼苏达",)),
    USState("MS", "Mississippi", ("密西西比",)),
    USState("MO", "Missouri", ("密苏里",)),
    USState("MT", "Montana", ("蒙大拿",)),
    USState("NE", "Nebraska", ("内布拉斯加",)),
    USState("NV", "Nevada", ("内华达",)),
    USState("NH", "New Hampshire", ("新罕布什尔",)),
    USState("NJ", "New Jersey", ("新泽西",)),
    USState("NM", "New Mexico", ("新墨西哥",)),
    USState("NY", "New York", ("纽约州", "纽约")),
    USState("NC", "North Carolina", ("北卡", "北卡罗来纳")),
    USState("ND", "North Dakota", ("北达科他",)),
    USState("OH", "Ohio", ("俄亥俄",)),
    USState("OK", "Oklahoma", ("俄克拉荷马",)),
    USState("OR", "Oregon", ("俄勒冈",)),
    USState("PA", "Pennsylvania", ("宾州", "宾夕法尼亚")),
    USState("RI", "Rhode Island", ("罗德岛",)),
    USState("SC", "South Carolina", ("南卡", "南卡罗来纳")),
    USState("SD", "South Dakota", ("南达科他",)),
    USState("TN", "Tennessee", ("田纳西",)),
    USState("TX", "Texas", ("德州", "德克萨斯")),
    USState("UT", "Utah", ("犹他",)),
    USState("VT", "Vermont", ("佛蒙特",)),
    USState("VA", "Virginia", ("弗吉尼亚",)),
    USState("WA", "Washington", ("华盛顿州",)),
    USState("WV", "West Virginia", ("西弗吉尼亚",)),
    USState("WI", "Wisconsin", ("威斯康星",)),
    USState("WY", "Wyoming", ("怀俄明",)),
    USState("DC", "Washington, D.C.", ("华盛顿dc", "华盛顿特区")),
)

STATE_BY_CODE = {state.code.lower(): state for state in US_STATES}
STATE_BY_NAME = {state.name.lower(): state for state in US_STATES}
STATE_ALIAS_LOOKUP: dict[str, USState] = {}
for state in US_STATES:
    STATE_ALIAS_LOOKUP[state.code.lower()] = state
    STATE_ALIAS_LOOKUP[state.name.lower()] = state
    for zh_name in state.zh_names:
        STATE_ALIAS_LOOKUP[zh_name.lower()] = state


def normalize_state(value: str) -> USState | None:
    cleaned = value.strip().strip(",.;:，。；：")
    if not cleaned:
        return None
    return STATE_ALIAS_LOOKUP.get(cleaned.lower())


def all_state_aliases() -> dict[str, USState]:
    return STATE_ALIAS_LOOKUP

