"""Analysis models."""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class TimelineEvent(BaseModel):
    date: str
    type: str
    severity: int
    evidence: str


class SimilarCompany(BaseModel):
    ticker: str
    name: str
    status: str
    risk_score: int
    common_signals: int
    similarity_score: float


class PatternMatch(BaseModel):
    company: str
    name: str
    bankruptcy_date: Optional[str]
    matching_signals: int
    similarity_score: float
    common_signal_types: List[str]


class AnalysisMetadata(BaseModel):
    analyzed_at: str
    filings_analyzed: int
    chunks_processed: int
    model_version: str = "gpt-4o"


class AnalysisResult(BaseModel):
    ticker: str
    company_name: str
    cik: str
    status: str  # "ACTIVE" or "BANKRUPT"

    risk_score: int  # 0-100
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"

    signal_summary: Dict[str, int]
    signal_count: int
    signals: List[Dict[str, Any]]
    timeline: List[TimelineEvent]

    similar_companies: List[SimilarCompany]
    bankruptcy_pattern_match: Optional[PatternMatch]

    executive_summary: str
    key_risks: List[str]

    filings_analyzed: int
    analyzed_at: str
