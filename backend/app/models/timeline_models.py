"""Timeline models for Neo4j - Facts-only, no scoring."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


# ==================== NODE MODELS ====================

class CompanyNode(BaseModel):
    """Company node for Neo4j storage."""
    ticker: str
    name: str
    cik: str
    status: str = "ACTIVE"  # "ACTIVE" | "BANKRUPT"
    bankruptcy_date: Optional[str] = None
    going_concern_status: str = "NEVER"  # "ACTIVE" | "REMOVED" | "NEVER"
    going_concern_first_seen: Optional[str] = None
    going_concern_last_seen: Optional[str] = None


class SignalNode(BaseModel):
    """Signal node for Neo4j storage."""
    id: str
    type: str
    date: str
    evidence: str
    fiscal_year: int


class FilingNode(BaseModel):
    """Filing node for Neo4j storage."""
    accession: str
    type: str  # "8-K" | "10-K" | "10-Q"
    item: Optional[str] = None
    date: str
    url: str
    fiscal_year: int
    category: str = "ROUTINE"  # "DISTRESS" | "ROUTINE" | "CORPORATE_ACTION"
    summary: Optional[str] = None
    has_going_concern: Optional[bool] = None
    has_material_weakness: Optional[bool] = None


# ==================== RESPONSE MODELS ====================

class FilingInfo(BaseModel):
    """Filing info attached to a signal."""
    type: str
    item: Optional[str] = None
    date: str
    url: Optional[str] = None
    accession: str


class SignalDetail(BaseModel):
    """Detailed signal with filing context."""
    id: str
    type: str
    date: str
    evidence: str
    fiscal_year: Optional[int] = None
    days_to_next: Optional[int] = None
    filing: Optional[FilingInfo] = None


class FilingDetail(BaseModel):
    """Detailed filing information."""
    accession: str
    type: str
    item: Optional[str] = None
    date: str
    url: Optional[str] = None
    category: str = "ROUTINE"
    summary: Optional[str] = None


class CompanyInfo(BaseModel):
    """Company info for timeline response - NO SCORES."""
    ticker: str
    name: str
    cik: Optional[str] = None
    status: str = "ACTIVE"
    bankruptcy_date: Optional[str] = None

    # Signal timeline context
    first_signal_date: Optional[str] = None
    last_signal_date: Optional[str] = None
    days_since_last_signal: Optional[int] = None
    total_signals: int = 0

    # Going concern tracking
    going_concern_status: str = "NEVER"  # "ACTIVE" | "REMOVED" | "NEVER"
    going_concern_first_seen: Optional[str] = None
    going_concern_last_seen: Optional[str] = None


class CompanyTimeline(BaseModel):
    """Complete company timeline - facts only, no scores."""
    company: CompanyInfo
    signals: List[SignalDetail] = []
    recent_filings: List[FilingDetail] = []


class GoingConcernYear(BaseModel):
    """Going concern status for a single fiscal year."""
    fiscal_year: int
    has_going_concern: bool
    filing_date: str
    url: Optional[str] = None


class GoingConcernHistory(BaseModel):
    """Track going concern status across 10-K filings."""
    ticker: str
    years: List[GoingConcernYear] = []

    @property
    def status_changed(self) -> bool:
        """Did going concern status change between years?"""
        if len(self.years) < 2:
            return False
        return self.years[0].has_going_concern != self.years[1].has_going_concern

    @property
    def was_removed(self) -> bool:
        """Was going concern removed in most recent filing?"""
        if len(self.years) < 2:
            return False
        return (not self.years[0].has_going_concern and
                self.years[1].has_going_concern)


class SimilarCase(BaseModel):
    """Historical case with similar signal pattern."""
    ticker: str
    name: str
    outcome: str  # "BANKRUPT" | "ACTIVE"
    bankruptcy_date: Optional[str] = None
    going_concern_status: Optional[str] = None
    overlap_count: int = 0
    matching_signals: List[str] = []
    timeline: List[dict] = []


# ==================== SIGNAL TYPE CONSTANTS ====================

DISTRESS_SIGNAL_TYPES = [
    "GOING_CONCERN",
    "MATERIAL_WEAKNESS",
    "RESTRUCTURING",
    "MASS_LAYOFFS",
    "CFO_DEPARTURE",
    "CEO_DEPARTURE",
    "AUDITOR_CHANGE",
    "CREDIT_DOWNGRADE",
    "DEBT_DEFAULT",
    "COVENANT_VIOLATION",
    "DELISTING_WARNING",
    "SEC_INVESTIGATION",
    "BANKRUPTCY_FILING"
]

FILING_CATEGORIES = {
    "DISTRESS": "Contains distress signals",
    "ROUTINE": "Normal business filings",
    "CORPORATE_ACTION": "Stock splits, M&A, financing"
}
