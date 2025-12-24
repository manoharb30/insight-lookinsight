"""Centralized constants for signal processing."""

# Base severity by signal type (can be adjusted by context)
BASE_SEVERITY = {
    "BANKRUPTCY_FILING": 10,
    "GOING_CONCERN": 9,
    "DEBT_DEFAULT": 8,
    "DELISTING_WARNING": 8,
    "MASS_LAYOFFS": 7,
    "CEO_DEPARTURE": 6,
    "CFO_DEPARTURE": 6,
    "COVENANT_VIOLATION": 7,
    "RESTRUCTURING": 5,
    "AUDITOR_CHANGE": 6,
    "SEC_INVESTIGATION": 7,
    "CREDIT_DOWNGRADE": 6,
    "ASSET_SALE": 5,
    "MATERIAL_WEAKNESS": 4,
    "BOARD_RESIGNATION": 4,
    "EQUITY_DILUTION": 4,
}

# Severity modifiers based on evidence content
SEVERITY_MODIFIERS = {
    "MASS_LAYOFFS": {
        "patterns": [
            (r'(\d{2,})%', lambda m: 2 if int(m.group(1)) >= 30 else 1 if int(m.group(1)) >= 20 else 0),
            (r'immediately', lambda m: 1),
        ],
    },
    "CEO_DEPARTURE": {
        "patterns": [
            (r'terminated', lambda m: 2),
            (r'immediate', lambda m: 1),
            (r'disagreement', lambda m: 2),
        ],
    },
    "CFO_DEPARTURE": {
        "patterns": [
            (r'terminated', lambda m: 2),
            (r'immediate', lambda m: 1),
            (r'disagreement', lambda m: 2),
        ],
    },
    "DEBT_DEFAULT": {
        "patterns": [
            (r'acceleration', lambda m: 2),
            (r'cross.?default', lambda m: 2),
            (r'event of default', lambda m: 1),
        ],
    },
    "GOING_CONCERN": {
        "patterns": [
            (r'substantial doubt', lambda m: 1),
            (r'ability to continue', lambda m: 1),
        ],
    },
}

# Legacy weights (kept for backward compatibility)
SIGNAL_WEIGHTS = {
    "BANKRUPTCY_FILING": 30,
    "GOING_CONCERN": 25,
    "DEBT_DEFAULT": 20,
    "DELISTING_WARNING": 15,
    "MASS_LAYOFFS": 15,
    "COVENANT_VIOLATION": 12,
    "CEO_DEPARTURE": 10,
    "CFO_DEPARTURE": 10,
    "CREDIT_DOWNGRADE": 10,
    "RESTRUCTURING": 10,
    "AUDITOR_CHANGE": 8,
    "SEC_INVESTIGATION": 8,
    "ASSET_SALE": 8,
    "MATERIAL_WEAKNESS": 5,
    "BOARD_RESIGNATION": 5,
    "EQUITY_DILUTION": 5,
}

# Predictive Weight = How well does this signal predict future bankruptcy (1-10)
# Based on research: CFO departure > CEO departure, early signals > late confirmations
PREDICTIVE_WEIGHTS = {
    # Tier 1: Insider Flight (12-24 months early) - HIGHEST VALUE
    "CFO_DEPARTURE": 9,       # CFOs see the numbers, leave early
    "AUDITOR_CHANGE": 8,      # Auditors don't want liability exposure

    # Tier 2: Financial Stress Signals (12-18 months early)
    "COVENANT_VIOLATION": 8,  # Lenders see problems, force action
    "MATERIAL_WEAKNESS": 7,   # Accounting issues emerging

    # Tier 3: Operational Distress (12-24 months early)
    "MASS_LAYOFFS": 7,        # Company in cost-cutting mode
    "CEO_DEPARTURE": 6,       # Leader exits (less predictive than CFO)
    "RESTRUCTURING": 6,       # Taking desperate measures

    # Tier 4: Confirmed Distress (6-12 months early)
    "GOING_CONCERN": 5,       # Auditor finally notices (late signal)
    "CREDIT_DOWNGRADE": 6,    # Rating agencies catch up
    "SEC_INVESTIGATION": 6,   # Regulatory issues
    "DEBT_DEFAULT": 5,        # Crisis already happening

    # Tier 5: Late Stage (1-6 months early)
    "DELISTING_WARNING": 4,   # Stock already crashed
    "ASSET_SALE": 4,          # Fire sale mode
    "EQUITY_DILUTION": 4,     # Desperate financing
    "BOARD_RESIGNATION": 3,   # Often routine

    # Tier 6: No Predictive Value
    "BANKRUPTCY_FILING": 2,   # Already happened - confirmation only
}

# Dangerous signal combinations - these patterns are highly predictive
# Each combination has a multiplier applied to combined weight
SIGNAL_COMBINATIONS = {
    # Insider Flight Pattern (Critical)
    "INSIDER_FLIGHT": {
        "signals": ["CFO_DEPARTURE", "AUDITOR_CHANGE"],
        "multiplier": 1.5,
        "description": "CFO and Auditor both exiting - insiders fleeing",
        "risk_level": "CRITICAL",
    },

    # Financial Collapse Pattern (Critical)
    "FINANCIAL_COLLAPSE": {
        "signals": ["COVENANT_VIOLATION", "DEBT_DEFAULT"],
        "multiplier": 1.5,
        "description": "Covenant breach followed by default - debt spiral",
        "risk_level": "CRITICAL",
    },

    # Leadership Crisis Pattern (High)
    "LEADERSHIP_CRISIS": {
        "signals": ["CEO_DEPARTURE", "CFO_DEPARTURE"],
        "multiplier": 1.4,
        "description": "Both CEO and CFO leaving - leadership vacuum",
        "risk_level": "HIGH",
    },

    # Confirmed Distress Pattern (Critical)
    "CONFIRMED_DISTRESS": {
        "signals": ["GOING_CONCERN", "RESTRUCTURING"],
        "multiplier": 1.5,
        "description": "Auditor warning plus restructuring - confirmed crisis",
        "risk_level": "CRITICAL",
    },

    # Operational Meltdown Pattern (High)
    "OPERATIONAL_MELTDOWN": {
        "signals": ["MASS_LAYOFFS", "RESTRUCTURING"],
        "multiplier": 1.3,
        "description": "Layoffs plus restructuring - deep operational cuts",
        "risk_level": "HIGH",
    },

    # Cash Crisis Pattern (High)
    "CASH_CRISIS": {
        "signals": ["MASS_LAYOFFS", "EQUITY_DILUTION"],
        "multiplier": 1.3,
        "description": "Cutting staff and raising equity - cash desperation",
        "risk_level": "HIGH",
    },

    # Accounting Red Flag Pattern (High)
    "ACCOUNTING_RED_FLAG": {
        "signals": ["AUDITOR_CHANGE", "MATERIAL_WEAKNESS"],
        "multiplier": 1.4,
        "description": "Auditor change plus material weakness - accounting issues",
        "risk_level": "HIGH",
    },

    # Delisting Spiral Pattern (Critical)
    "DELISTING_SPIRAL": {
        "signals": ["DELISTING_WARNING", "MASS_LAYOFFS", "CFO_DEPARTURE"],
        "multiplier": 1.6,
        "description": "Delisting warning with layoffs and CFO exit - collapse imminent",
        "risk_level": "CRITICAL",
    },

    # Triple Threat Pattern (Critical)
    "TRIPLE_THREAT": {
        "signals": ["CFO_DEPARTURE", "COVENANT_VIOLATION", "MASS_LAYOFFS"],
        "multiplier": 1.8,
        "description": "CFO exits + covenant breach + layoffs - imminent collapse",
        "risk_level": "CRITICAL",
    },
}

# Signal velocity thresholds (signals within time period)
VELOCITY_THRESHOLDS = {
    "HIGH_VELOCITY": {
        "signals_count": 3,
        "days": 90,
        "multiplier": 1.3,
        "description": "3+ signals in 90 days indicates rapid deterioration",
    },
    "EXTREME_VELOCITY": {
        "signals_count": 5,
        "days": 90,
        "multiplier": 1.5,
        "description": "5+ signals in 90 days indicates crisis",
    },
}

# Validation thresholds
MIN_CONFIDENCE = 0.6
MIN_EVIDENCE_LENGTH = 50
MIN_WORD_COUNT = 10
MAX_EVIDENCE_LENGTH = 1000

# Valid signal types
VALID_SIGNAL_TYPES = list(BASE_SEVERITY.keys())
