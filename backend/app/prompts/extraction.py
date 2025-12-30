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
2. CEO_DEPARTURE - Current CEO leaving role: resigns, is terminated, steps down, retirement, OR is being replaced/succeeded by new CEO. Key trigger: existing CEO will no longer be CEO.
3. CFO_DEPARTURE - Current CFO leaving role: resigns, is terminated, steps down, retirement, OR is being replaced/succeeded by new CFO.
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
      "summary": "1-2 sentence plain English explanation of what happened and why it matters",
      "key_facts": ["fact 1", "fact 2", "fact 3"],
      "event_date": "YYYY-MM-DD or null if not specified",
      "person": "Name and Title if applicable, or null"
    }}
  ]
}}

## FIELD GUIDELINES

**summary**: Write a clear, informative 1-2 sentence explanation that a non-expert investor could understand.
- Good: "The company disclosed it may be unable to repay $200M in convertible notes due June 2025, and is exploring debt restructuring options."
- Bad: "Debt default risk mentioned."

**key_facts**: Extract 2-4 specific facts with numbers, dates, names, or percentages:
- "$200M convertible notes due June 1, 2025"
- "Workforce reduction of 2,500 employees (12% of workforce)"
- "CEO John Smith resigned effective January 15, 2025"
- "Material weakness in revenue recognition controls"

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

POSITIVE (IS a going concern signal - extract it):
- "There is substantial doubt about our ability to continue as a going concern"
- "The auditor's report includes a going concern emphasis paragraph"
- "Conditions exist that raise substantial doubt"
- "Our ability to continue is contingent upon..."
- "If we fail to raise capital, we may not be able to continue"
- "There can be no assurance that we will be able to continue"
- "We may not have sufficient capital to fund operations"
- Any language expressing uncertainty about company's survival

NEGATIVE (NOT a going concern signal - do not extract):
- "No substantial doubt about ability to continue"
- "Management believes the company will continue as a going concern"
- "The going concern issue has been resolved"
- Simply mentioning "going concern" in accounting policy context without expressing doubt

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


# =============================================================================
# 10-K ITEM-BASED EXTRACTION PROMPT - FOR STRUCTURED ITEMS
# =============================================================================

EXTRACT_10K_ITEMS_PROMPT = """You are an expert SEC filing analyst. Extract bankruptcy warning signals from these 10-K sections.

## FILING INFORMATION
Company: {company_name}
Filing Date: {filing_date}
Accession Number: {accession_number}

## 10-K SECTION CONTEXT
You are analyzing extracted sections from a 10-K annual report:
- Item 7 (MD&A): Discusses financial condition, liquidity, restructuring plans
- Item 8 (Financial Statements): Contains auditor report with going concern opinions
- Item 9A (Controls): Discloses material weaknesses in internal controls

## SIGNAL TYPES TO EXTRACT

1. GOING_CONCERN - Auditor or management expresses "substantial doubt about ability to continue as a going concern"
2. MATERIAL_WEAKNESS - "Material weakness in internal control over financial reporting" disclosed in Item 9A
3. RESTRUCTURING - Formal restructuring plans, workforce reductions, facility closures mentioned in MD&A
4. MASS_LAYOFFS - Workforce reduction >10% or >100 employees
5. DEBT_DEFAULT - Missed payments, acceleration events, events of default
6. COVENANT_VIOLATION - Loan covenant breach or waiver requests
7. AUDITOR_CHANGE - Change in independent auditor
8. CREDIT_DOWNGRADE - Rating agency downgrade mentioned
9. ASSET_SALE - Sale of significant assets or business segments
10. SEC_INVESTIGATION - SEC subpoena, enforcement action, or investigation disclosed

## CRITICAL INSTRUCTIONS

1. For each signal, provide a MARKER PHRASE - a unique 10-25 word phrase COPIED EXACTLY from the text
2. The marker phrase must be VERBATIM - copy it exactly as it appears
3. Include which Item/section the signal came from
4. If NO signals found, return empty array
5. Be thorough - check ALL provided sections

## RESPONSE FORMAT (JSON)

{{
  "signals": [
    {{
      "type": "SIGNAL_TYPE",
      "item_number": "Item 9A" or "Item 7" or "Item 8",
      "severity": 1-10,
      "confidence": 0.0-1.0,
      "marker_phrase": "EXACT 10-25 word phrase copied verbatim from filing",
      "summary": "1-2 sentence plain English explanation of what happened and why it matters",
      "key_facts": ["fact 1", "fact 2", "fact 3"],
      "event_date": "YYYY-MM-DD or null"
    }}
  ]
}}

## FIELD GUIDELINES

**summary**: Write a clear, informative 1-2 sentence explanation that a non-expert investor could understand.
- Good: "The company raised substantial doubt about its ability to continue operations, citing $4.5B accumulated deficit and ongoing cash burn."
- Bad: "Going concern mentioned."

**key_facts**: Extract 2-4 specific facts with numbers, dates, names, or percentages:
- "$4.5 billion accumulated deficit as of December 31, 2023"
- "Cash burn expected to continue through 2025"
- "Material weakness in internal controls over financial reporting"
- "Workforce reduction of 15% announced"

Severity scale:
- 1-3: Minor/routine
- 4-6: Moderate concern
- 7-8: Significant risk
- 9-10: Critical/immediate bankruptcy risk

## 10-K SECTIONS

{items_text}

## END OF SECTIONS

Extract all signals with VERBATIM marker phrases. Return {{"signals": []}} if none found.
"""

# Keep old prompt name for backward compatibility
SIGNAL_EXTRACTION_PROMPT = EXTRACT_8K_PROMPT
