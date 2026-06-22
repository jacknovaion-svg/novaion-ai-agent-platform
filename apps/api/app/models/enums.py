from enum import Enum


class AgentType(str, Enum):
    HARDWARE_HUNTER = "hardware_hunter"
    SITE_HUNTER = "site_hunter"
    POWER_HUNTER = "power_hunter"
    LAND_HUNTER = "land_hunter"
    SUPPLIER_HUNTER = "supplier_hunter"
    DATA_CENTER_HUNTER = "data_center_hunter"


class SearchMode(str, Enum):
    LOCAL = "local"
    ONLINE = "online"
    ALL = "all"


class SearchSource(str, Enum):
    BEST_BUY = "best_buy"
    MICRO_CENTER = "micro_center"
    NEWEGG = "newegg"
    CDW = "cdw"
    PROVANTAGE = "provantage"


class Language(str, Enum):
    ENGLISH = "en"
    CHINESE = "zh"
    SPANISH = "es"
