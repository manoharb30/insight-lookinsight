"""Evidence quality filtering."""

import re
from typing import Dict, Any, List, Tuple

from app.core.logging import get_logger
from app.core.constants import MIN_EVIDENCE_LENGTH, MIN_WORD_COUNT, MAX_EVIDENCE_LENGTH

logger = get_logger(__name__)


# Patterns that indicate junk evidence
JUNK_PATTERNS = [
    r'^[a-z]+:[A-Za-z0-9]+Member$',  # XBRL member tags
    r'^[a-z]+:[A-Za-z0-9]+$',         # XBRL tags
    r'^<[^>]+>$',                      # XML tags
    r'^[A-Z][a-z]+[A-Z][a-z]+\d{4}$', # CamelCase with year (e.g., RestructuringPlan2025)
    r'^\s*$',                          # Empty or whitespace only
    r'^[A-Z_]+$',                      # ALL_CAPS_CONSTANTS
]


def is_valid_evidence(evidence: str) -> Tuple[bool, str]:
    """
    Check if evidence meets quality standards.

    Args:
        evidence: The evidence string to validate

    Returns:
        Tuple of (is_valid, rejection_reason)
    """
    if not evidence:
        return False, "Empty evidence"

    evidence = evidence.strip()

    # Length check
    if len(evidence) < MIN_EVIDENCE_LENGTH:
        return False, f"Evidence too short ({len(evidence)} < {MIN_EVIDENCE_LENGTH} chars)"

    # Word count check
    words = evidence.split()
    if len(words) < MIN_WORD_COUNT:
        return False, f"Too few words ({len(words)} < {MIN_WORD_COUNT})"

    # Junk pattern check
    for pattern in JUNK_PATTERNS:
        if re.match(pattern, evidence):
            return False, f"Matches junk pattern: {pattern}"

    # Check for excessive special characters (likely XML/code)
    special_char_ratio = len(re.findall(r'[<>{}[\]|\\]', evidence)) / len(evidence)
    if special_char_ratio > 0.1:
        return False, "Too many special characters (likely XML/code)"

    # Check it contains actual sentences (has periods and capital letters)
    if not re.search(r'[A-Z].*[a-z]', evidence):
        return False, "Doesn't appear to be natural language"

    return True, ""


def filter_signals_by_evidence_quality(
    signals: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Filter signals based on evidence quality.

    Args:
        signals: List of signal dicts

    Returns:
        Tuple of (valid_signals, rejected_signals)
    """
    valid = []
    rejected = []

    for signal in signals:
        evidence = signal.get("evidence", "")
        is_valid, reason = is_valid_evidence(evidence)

        if is_valid:
            valid.append(signal)
        else:
            signal["rejection_reason"] = f"Evidence quality: {reason}"
            rejected.append(signal)
            logger.debug(f"Rejected signal: {reason} - {evidence[:50]}...")

    logger.info(
        f"Evidence filter: {len(signals)} -> {len(valid)} signals "
        f"({len(rejected)} rejected for quality)"
    )

    return valid, rejected


def truncate_evidence(evidence: str) -> str:
    """
    Truncate evidence to reasonable length while keeping complete sentences.
    """
    if len(evidence) <= MAX_EVIDENCE_LENGTH:
        return evidence

    # Try to cut at sentence boundary
    truncated = evidence[:MAX_EVIDENCE_LENGTH]

    # Find last period
    last_period = truncated.rfind('.')
    if last_period > MAX_EVIDENCE_LENGTH * 0.7:  # At least 70% of max
        return truncated[:last_period + 1]

    # Otherwise just truncate with ellipsis
    return truncated.rstrip() + "..."
