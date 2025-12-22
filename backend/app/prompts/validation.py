"""Validation rules and prompts for signal validation."""

from typing import Dict, Any, List

# Signal-specific validation rules
VALIDATION_RULES: Dict[str, Dict[str, Any]] = {
    "CEO_DEPARTURE": {
        "must_contain_any": ["resign", "step down", "stepped down", "terminate", "depart", "left", "leaving"],
        "must_not_contain": ["appointed", "promoted", "continues as", "will remain", "named as", "hired"],
        "require_person": True,
        "min_confidence": 0.7,
        "description": "CEO must be LEAVING the position, not being appointed or staying",
    },
    "CFO_DEPARTURE": {
        "must_contain_any": ["resign", "step down", "stepped down", "terminate", "depart", "left", "leaving"],
        "must_not_contain": ["appointed", "promoted", "continues as", "will remain", "named as", "hired"],
        "require_person": True,
        "min_confidence": 0.7,
        "description": "CFO must be LEAVING the position, not being appointed or staying",
    },
    "GOING_CONCERN": {
        "must_contain_any": ["going concern", "substantial doubt", "ability to continue", "continue as a going concern"],
        "min_confidence": 0.8,
        "min_severity": 5,
        "description": "Must have explicit language about doubt of survival",
    },
    "MASS_LAYOFFS": {
        "must_contain_any": ["layoff", "workforce reduction", "headcount reduction", "job cuts", "employees", "positions"],
        "require_quantity": True,  # Needs percentage or number
        "min_threshold_percent": 0.10,  # 10% of workforce
        "min_threshold_count": 100,  # Or 100+ employees
        "min_confidence": 0.7,
        "description": "Must have significant workforce reduction (>10% or >100 employees)",
    },
    "DEBT_DEFAULT": {
        "must_contain_any": ["default", "acceleration", "failed to pay", "event of default", "missed payment"],
        "min_confidence": 0.8,
        "min_severity": 5,
        "description": "Must have explicit default or payment failure language",
    },
    "COVENANT_VIOLATION": {
        "must_contain_any": ["covenant", "waiver", "breach", "violation", "non-compliance"],
        "min_confidence": 0.7,
        "description": "Must have explicit covenant breach or waiver",
    },
    "AUDITOR_CHANGE": {
        "must_contain_any": ["dismissed", "resigned", "new auditor", "change in auditor", "engaged", "independent registered"],
        "must_not_contain": ["no disagreements"],  # If no disagreements, might be routine
        "min_confidence": 0.7,
        "description": "Change in independent auditor",
    },
    "BOARD_RESIGNATION": {
        "must_contain_any": ["resigned from the board", "director resign", "stepped down from board", "departed from board"],
        "must_not_contain": ["appointed", "elected", "named to board"],
        "require_person": True,
        "min_confidence": 0.6,
        "description": "Director must be leaving the board, not joining",
    },
    "DELISTING_WARNING": {
        "must_contain_any": ["nasdaq", "nyse", "delisting", "compliance", "deficiency", "listing standard"],
        "min_confidence": 0.8,
        "min_severity": 5,
        "description": "Exchange compliance warning or delisting notice",
    },
    "CREDIT_DOWNGRADE": {
        "must_contain_any": ["moody's", "s&p", "fitch", "downgrade", "rating", "lowered"],
        "must_not_contain": ["upgrade", "affirmed", "maintained"],
        "min_confidence": 0.7,
        "description": "Credit rating must be downgraded, not upgraded or affirmed",
    },
    "ASSET_SALE": {
        "must_contain_any": ["sale of assets", "disposition", "divest", "sold", "selling"],
        "min_confidence": 0.6,
        "description": "Significant asset sale or divestiture",
    },
    "RESTRUCTURING": {
        "must_contain_any": ["restructuring", "reorganization", "chapter 11", "bankruptcy", "restructure"],
        "min_confidence": 0.7,
        "min_severity": 4,
        "description": "Formal restructuring or reorganization plan",
    },
    "SEC_INVESTIGATION": {
        "must_contain_any": ["subpoena", "sec", "investigation", "wells notice", "enforcement", "inquiry"],
        "min_confidence": 0.7,
        "description": "SEC investigation or enforcement action",
    },
    "MATERIAL_WEAKNESS": {
        "must_contain_any": ["material weakness", "internal control", "disclosure controls", "significant deficiency"],
        "min_confidence": 0.7,
        "description": "Internal control deficiency or material weakness",
    },
    "EQUITY_DILUTION": {
        "must_contain_any": ["at-the-market", "atm", "equity offering", "stock issuance", "registered direct"],
        "min_confidence": 0.6,
        "description": "Equity issuance that may dilute shareholders",
    },
}

# False positive patterns - signals that look real but aren't
FALSE_POSITIVE_PATTERNS = {
    "CEO_DEPARTURE": [
        "appointed as CEO",
        "named CEO",
        "will continue as",
        "remains as CEO",
        "effective immediately, .* has been appointed",
        "successor .* has been appointed",
    ],
    "CFO_DEPARTURE": [
        "appointed as CFO",
        "named CFO",
        "will continue as",
        "remains as CFO",
        "effective immediately, .* has been appointed",
    ],
    "GOING_CONCERN": [
        "no going concern",
        "absence of .* going concern",
        "do not believe .* going concern",
        "no substantial doubt",
    ],
    "DEBT_DEFAULT": [
        "no default",
        "waived the default",
        "cured the default",
        "no event of default",
    ],
    "MASS_LAYOFFS": [
        "hired .* employees",
        "added .* positions",
        "increased headcount",
    ],
}

# GPT-4o validation prompt
SIGNAL_VALIDATION_PROMPT = """You are an expert at validating financial distress signals extracted from SEC filings.

Your task is to verify that each signal:
1. Has evidence that actually supports the signal type
2. Is not a false positive (e.g., an appointment mistaken for a departure)
3. Has accurate severity and confidence scores

## Signal Being Validated:
Type: {signal_type}
Evidence: {evidence}
Date: {date}
Person: {person}
Original Severity: {severity}
Original Confidence: {confidence}

## Validation Rules for {signal_type}:
{validation_rules}

## Your Task:
1. Verify the evidence supports this signal type
2. Check for false positive patterns
3. Adjust severity (1-10) and confidence (0.0-1.0) if needed
4. Provide reasoning

## Response Format (JSON):
{{
  "is_valid": true/false,
  "adjusted_severity": 1-10,
  "adjusted_confidence": 0.0-1.0,
  "rejection_reason": "reason if rejected or null",
  "validation_notes": "brief explanation of validation decision"
}}

Be strict - reject signals that don't clearly meet the criteria.
"""

# Evidence verification prompt
EVIDENCE_VERIFICATION_PROMPT = """Verify that the following evidence quote exists in the source text and supports the claimed signal.

Signal Type: {signal_type}
Claimed Evidence: "{evidence}"

Source Text:
---
{source_text}
---

Does this evidence:
1. Exist in the source text (exact or near-exact match)?
2. Support the claimed signal type?

Response (JSON):
{{
  "evidence_found": true/false,
  "match_quality": "exact"/"partial"/"not_found",
  "supports_signal": true/false,
  "corrected_evidence": "the actual matching text if different, or null"
}}
"""
