"""LLM prompts for signal validation."""

# Signal types for reference
VALID_SIGNAL_TYPES = [
    "GOING_CONCERN",
    "BANKRUPTCY_FILING",
    "CEO_DEPARTURE",
    "CFO_DEPARTURE",
    "MASS_LAYOFFS",
    "DEBT_DEFAULT",
    "COVENANT_VIOLATION",
    "AUDITOR_CHANGE",
    "BOARD_RESIGNATION",
    "DELISTING_WARNING",
    "CREDIT_DOWNGRADE",
    "ASSET_SALE",
    "RESTRUCTURING",
    "SEC_INVESTIGATION",
    "MATERIAL_WEAKNESS",
    "EQUITY_DILUTION",
]

# =============================================================================
# LLM VALIDATION PROMPT
# =============================================================================

LLM_VALIDATION_PROMPT = """You are an SEC filing analyst validating signal classification.

## SIGNAL TO VALIDATE

Type: {signal_type}
Evidence: "{evidence}"
Severity: {severity}/10
Filing Type: {filing_type}
Filing Date: {filing_date}
Person: {person}

## SIGNAL TYPE DEFINITIONS

- GOING_CONCERN: Language about substantial doubt, ability to continue operations, may not survive
- BANKRUPTCY_FILING: ACTUAL Chapter 7/11 filing (past tense "filed", specific date)
- CEO_DEPARTURE: CEO leaves (resignation, termination, retirement, being replaced)
- CFO_DEPARTURE: CFO leaves
- BOARD_RESIGNATION: Director resigns from board
- MASS_LAYOFFS: Workforce reduction, layoffs, headcount reduction
- DEBT_DEFAULT: Missed payment, event of default, acceleration, or RISK of default
- COVENANT_VIOLATION: Breach of covenants, waiver requests, or covenant-related issues
- AUDITOR_CHANGE: Change of independent auditor
- DELISTING_WARNING: Exchange compliance notice
- CREDIT_DOWNGRADE: Rating downgrade
- ASSET_SALE: Sale of assets or subsidiaries
- RESTRUCTURING: Debt restructuring, exchange offers, reorganization, cost-cutting
- SEC_INVESTIGATION: SEC subpoena, enforcement, Wells notice
- MATERIAL_WEAKNESS: Internal control deficiency
- EQUITY_DILUTION: Stock issuance, equity offering, ATM program

## TASK: VERIFY CLASSIFICATION ONLY

Your ONLY job is to check if the signal TYPE matches the evidence.
- Does the evidence describe this type of event?
- If misclassified, suggest the correct type

DO NOT reject signals for:
- Conditional language (may, could, if) - these are still valid disclosures
- Severity disagreements - just correct the severity
- Whether it's "distressing enough" - we record all disclosures

ONLY reject if:
- Evidence describes a completely different event type
- Evidence is about an appointment when type says departure
- BANKRUPTCY_FILING with only conditional language (reclassify to GOING_CONCERN)

## RESPONSE FORMAT (JSON)

{{
  "is_valid": true or false,
  "corrected_type": "SIGNAL_TYPE" if misclassified, otherwise null,
  "corrected_severity": 1-10 if needs adjustment, otherwise null,
  "rejection_reason": "brief reason" if is_valid is false, otherwise null,
  "confidence": 0.0-1.0
}}

## EXAMPLES

Example 1 - Valid (conditional language is OK):
Type: DEBT_DEFAULT
Evidence: "if we fail to raise capital, we may be unable to meet debt obligations"
Response: {{"is_valid": true, "corrected_type": null, "corrected_severity": null, "rejection_reason": null, "confidence": 0.85}}

Example 2 - Misclassified (appointment, not departure):
Type: CEO_DEPARTURE
Evidence: "John Smith was appointed as Chief Executive Officer"
Response: {{"is_valid": false, "corrected_type": null, "corrected_severity": null, "rejection_reason": "Appointment, not departure", "confidence": 0.95}}

Example 3 - Reclassify (not actual bankruptcy):
Type: BANKRUPTCY_FILING
Evidence: "may be forced to file for bankruptcy protection"
Response: {{"is_valid": true, "corrected_type": "GOING_CONCERN", "corrected_severity": null, "rejection_reason": null, "confidence": 0.9}}

Validate the signal above.
"""
