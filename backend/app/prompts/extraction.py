"""LLM prompts for signal extraction - full filing approach with marker phrases."""

SIGNAL_TYPES = [
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

# Map 8-K items to signal types for context
ITEM_SIGNAL_MAP = {
    "1.01": ["DEBT_DEFAULT", "COVENANT_VIOLATION"],
    "1.02": ["DEBT_DEFAULT"],
    "1.03": ["BANKRUPTCY_FILING"],
    "2.01": ["ASSET_SALE"],
    "2.04": ["DEBT_DEFAULT", "COVENANT_VIOLATION"],
    "2.05": ["MASS_LAYOFFS", "RESTRUCTURING"],
    "2.06": ["ASSET_SALE"],
    "3.01": ["DELISTING_WARNING"],
    "4.01": ["AUDITOR_CHANGE"],
    "4.02": ["MATERIAL_WEAKNESS"],
    "5.02": ["CEO_DEPARTURE", "CFO_DEPARTURE", "BOARD_RESIGNATION"],
    "7.01": ["CREDIT_DOWNGRADE", "SEC_INVESTIGATION"],
    "8.01": ["CREDIT_DOWNGRADE", "SEC_INVESTIGATION", "EQUITY_DILUTION"],
}

# =============================================================================
# 8-K FULL TEXT EXTRACTION PROMPT - WITH MARKER PHRASES
# =============================================================================

EXTRACT_8K_PROMPT = """You are an expert SEC filing analyst. Extract bankruptcy warning signals from this 8-K filing.

## FILING INFORMATION
Company: {company_name}
Filing Date: {filing_date}
Accession Number: {accession_number}

## 8-K ITEM REFERENCE
8-K filings are organized by Item numbers. Key items for distress signals:
- Item 1.01/1.02: Material agreements (defaults, covenant violations)
- Item 1.03: Bankruptcy filing
- Item 2.04: Triggering events (defaults, acceleration)
- Item 2.05: Exit costs (layoffs, restructuring charges)
- Item 3.01: Delisting notices
- Item 4.01: Auditor changes
- Item 4.02: Non-reliance on financials (material weakness)
- Item 5.02: Director/Officer departures
- Item 7.01/8.01: Other material events (credit downgrades, SEC investigations)

## SIGNAL TYPES TO EXTRACT

1. BANKRUPTCY_FILING - Company files for Chapter 7, Chapter 11 bankruptcy, or receivership (Item 1.03)
2. CEO_DEPARTURE - CEO resigns, is terminated, or steps down (NOT appointments)
3. CFO_DEPARTURE - CFO resigns, is terminated, or steps down (NOT appointments)
4. BOARD_RESIGNATION - Director resigns from board (NOT appointments)
5. MASS_LAYOFFS - Workforce reduction >10% or >100 employees
6. DEBT_DEFAULT - Missed payments, acceleration, events of default
7. COVENANT_VIOLATION - Loan covenant breach or waiver
8. AUDITOR_CHANGE - Change in independent auditor
9. DELISTING_WARNING - Exchange compliance notice
10. CREDIT_DOWNGRADE - Rating agency downgrade
11. ASSET_SALE - Sale of significant assets
12. RESTRUCTURING - Formal restructuring plan, debt exchange, supplemental indentures
13. SEC_INVESTIGATION - SEC subpoena or enforcement
14. MATERIAL_WEAKNESS - Internal control deficiency
15. EQUITY_DILUTION - Stock issuance, equity offering, ATM program

## CRITICAL DISTINCTION - BANKRUPTCY_FILING vs GOING_CONCERN

GOING_CONCERN (hypothetical future - DO NOT classify as BANKRUPTCY_FILING):
- "may be forced to file bankruptcy"
- "could result in bankruptcy proceedings"
- "if we fail to raise capital, we may need to file"
- Contains conditional words: "may", "could", "if", "might", "unlikely"

BANKRUPTCY_FILING (actual event that HAS occurred):
- "On December 14, 2025, the Company filed Chapter 11"
- "has commenced bankruptcy proceedings"
- "filed a voluntary petition for relief under the U.S. Bankruptcy Code"
- Contains: specific date + past tense "filed" + "Chapter 11/7"

RULE: If evidence contains conditional language (may/could/if/might),
it is NOT a BANKRUPTCY_FILING. Do not extract it as such.

## CRITICAL INSTRUCTIONS

1. For each signal, provide a MARKER PHRASE - a unique 10-25 word phrase COPIED EXACTLY from the filing
2. The marker phrase must be VERBATIM - copy it exactly as it appears, including punctuation
3. Choose a marker phrase that uniquely identifies this specific signal/event
4. Include the EXACT Item number where the signal appears (e.g., "5.02")
5. Extract the EVENT DATE if mentioned (often different from filing date)
6. If NO signals found, return empty array

## RESPONSE FORMAT (JSON)

{{
  "signals": [
    {{
      "type": "SIGNAL_TYPE",
      "item_number": "5.02",
      "severity": 1-10,
      "confidence": 0.0-1.0,
      "marker_phrase": "EXACT 10-25 word phrase copied verbatim from filing that identifies this signal",
      "event_date": "YYYY-MM-DD or null if not specified",
      "person": "Name and Title if applicable, or null"
    }}
  ]
}}

## MARKER PHRASE EXAMPLES

GOOD markers (verbatim, unique, 10-25 words):
- "John Smith notified the Board of Directors of his resignation as Chief Executive Officer effective January 15"
- "the Company entered into supplemental indentures to the applicable Indentures with respect to each series"
- "announced a workforce reduction affecting approximately 2,500 employees, representing 12% of its global workforce"

BAD markers (paraphrased, too short, or generic):
- "CEO resigned" (too short, not verbatim)
- "The company restructured its debt" (paraphrased)
- "pursuant to the terms of the agreement" (too generic, appears everywhere)

Severity scale:
- 1-3: Minor/routine
- 4-6: Moderate concern
- 7-8: Significant risk
- 9-10: Critical/immediate bankruptcy risk

## 8-K FILING TEXT

{filing_text}

## END OF FILING

Extract all bankruptcy warning signals with VERBATIM marker phrases. Return {{"signals": []}} if none found.
"""

# =============================================================================
# 10-K GOING CONCERN EXTRACTION PROMPT - WITH MARKER PHRASES
# =============================================================================

EXTRACT_10K_GOING_CONCERN_PROMPT = """You are an expert SEC filing analyst. Analyze this excerpt from a 10-K filing to determine if there is a GOING CONCERN warning.

## FILING INFORMATION
Company: {company_name}
Filing Date: {filing_date}
Accession Number: {accession_number}

## WHAT IS A GOING CONCERN WARNING?

A going concern warning is when the auditor or management expresses "substantial doubt about the company's ability to continue as a going concern." This is one of the strongest bankruptcy predictors.

## IMPORTANT DISTINCTIONS

POSITIVE (IS a going concern signal):
- "There is substantial doubt about our ability to continue as a going concern"
- "The auditor's report includes a going concern emphasis paragraph"
- "Conditions exist that raise substantial doubt"

NEGATIVE (NOT a going concern signal):
- "No substantial doubt about ability to continue"
- "Management believes the company will continue as a going concern"
- "The going concern issue has been resolved"

## RESPONSE FORMAT (JSON)

{{
  "has_going_concern": true/false,
  "signal": {{
    "type": "GOING_CONCERN",
    "severity": 9,
    "confidence": 0.0-1.0,
    "marker_phrase": "EXACT 10-25 word phrase copied verbatim containing going concern language",
    "event_date": "{filing_date}",
    "source": "Auditor Report" or "MD&A" or "Notes to Financial Statements"
  }} or null if no going concern
}}

## 10-K EXCERPT

{excerpt_text}

## END OF EXCERPT

Analyze carefully. If going concern warning exists, provide a VERBATIM marker phrase.
"""


# Keep old prompt name for backward compatibility
SIGNAL_EXTRACTION_PROMPT = EXTRACT_8K_PROMPT
