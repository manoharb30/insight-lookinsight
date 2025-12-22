"""Signal models."""

from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class SignalType(str, Enum):
    GOING_CONCERN = "GOING_CONCERN"
    CEO_DEPARTURE = "CEO_DEPARTURE"
    CFO_DEPARTURE = "CFO_DEPARTURE"
    MASS_LAYOFFS = "MASS_LAYOFFS"
    DEBT_DEFAULT = "DEBT_DEFAULT"
    COVENANT_VIOLATION = "COVENANT_VIOLATION"
    AUDITOR_CHANGE = "AUDITOR_CHANGE"
    BOARD_RESIGNATION = "BOARD_RESIGNATION"
    DELISTING_WARNING = "DELISTING_WARNING"
    CREDIT_DOWNGRADE = "CREDIT_DOWNGRADE"
    ASSET_SALE = "ASSET_SALE"
    RESTRUCTURING = "RESTRUCTURING"
    SEC_INVESTIGATION = "SEC_INVESTIGATION"
    MATERIAL_WEAKNESS = "MATERIAL_WEAKNESS"
    EQUITY_DILUTION = "EQUITY_DILUTION"


class Signal(BaseModel):
    id: str
    type: SignalType
    date: str
    severity: int
    confidence: float
    evidence: str
    source_filing: str
    item_number: str
    person: Optional[str] = None


class SignalSummary(BaseModel):
    total: int
    by_type: dict
    highest_severity: int
    avg_confidence: float
