"""Signal deduplication - simplified type + date based approach."""

import re
from typing import List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.constants import BASE_SEVERITY, SEVERITY_MODIFIERS

logger = get_logger(__name__)


# Ongoing signals - keep only earliest occurrence
ONGOING_SIGNAL_TYPES = {
    "MATERIAL_WEAKNESS",    # Reported until remediated
    "RESTRUCTURING",        # Reported during restructuring period
    "COVENANT_VIOLATION",   # Reported until waived/cured
    "DELISTING_WARNING",    # Reported until compliance restored
    "GOING_CONCERN",        # Reported until resolved
}

# Discrete signals - can have multiple distinct occurrences
DISCRETE_SIGNAL_TYPES = {
    "CEO_DEPARTURE",
    "CFO_DEPARTURE",
    "BOARD_RESIGNATION",
    "MASS_LAYOFFS",
    "DEBT_DEFAULT",
    "AUDITOR_CHANGE",
    "SEC_INVESTIGATION",
    "CREDIT_DOWNGRADE",
    "ASSET_SALE",
    "EQUITY_DILUTION",
}


@dataclass
class DeduplicationResult:
    unique_signals: List[Dict[str, Any]]
    duplicates_removed: int
    by_type: Dict[str, int]


def normalize_severity(signal: Dict[str, Any]) -> int:
    """Normalize severity based on signal type."""
    signal_type = signal.get("type", "")
    evidence = signal.get("evidence", "").lower()
    llm_severity = signal.get("severity", 5)

    # Get base severity
    base = BASE_SEVERITY.get(signal_type, 5)

    # Apply modifiers
    modifier = 0
    if signal_type in SEVERITY_MODIFIERS:
        for pattern, adjust_func in SEVERITY_MODIFIERS[signal_type].get("patterns", []):
            match = re.search(pattern, evidence, re.IGNORECASE)
            if match:
                try:
                    modifier += adjust_func(match)
                except:
                    pass

    normalized = min(10, max(1, base + modifier))

    # Consider LLM input if much higher
    if llm_severity > normalized + 2:
        normalized = min(10, normalized + 1)

    return normalized


def deduplicate_signals(signals: List[Dict[str, Any]]) -> DeduplicationResult:
    """
    Deduplicate signals using type + date based approach.

    - Ongoing signals: Keep only the earliest occurrence
    - Discrete signals: Keep all that are >90 days apart (different events)
    """
    if not signals:
        return DeduplicationResult(
            unique_signals=[],
            duplicates_removed=0,
            by_type={},
        )

    # Normalize severities first
    for signal in signals:
        signal["severity"] = normalize_severity(signal)

    # Sort by date (earliest first)
    sorted_signals = sorted(
        signals,
        key=lambda s: s.get("date", "9999-99-99")
    )

    # Group by type
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for signal in sorted_signals:
        signal_type = signal.get("type", "UNKNOWN")
        if signal_type not in by_type:
            by_type[signal_type] = []
        by_type[signal_type].append(signal)

    # Deduplicate each type
    unique_signals = []
    type_counts = {}

    for signal_type, type_signals in by_type.items():
        if signal_type in ONGOING_SIGNAL_TYPES:
            # Keep only earliest occurrence
            if type_signals:
                unique_signals.append(type_signals[0])
                type_counts[signal_type] = 1
        else:
            # Discrete: keep signals >90 days apart
            kept = []
            for signal in type_signals:
                date_str = signal.get("date", "")

                if not date_str:
                    kept.append(signal)
                    continue

                try:
                    signal_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    kept.append(signal)
                    continue

                # Check if this is a new event (>90 days from any kept signal)
                is_new_event = True
                for existing in kept:
                    existing_date_str = existing.get("date", "")
                    if not existing_date_str:
                        continue

                    try:
                        existing_date = datetime.strptime(existing_date_str, "%Y-%m-%d")
                        days_apart = abs((signal_date - existing_date).days)

                        if days_apart <= 90:
                            # Same event - keep the one with higher severity
                            is_new_event = False
                            if signal.get("severity", 0) > existing.get("severity", 0):
                                kept.remove(existing)
                                kept.append(signal)
                            break
                    except ValueError:
                        continue

                if is_new_event:
                    kept.append(signal)

            unique_signals.extend(kept)
            type_counts[signal_type] = len(kept)

    duplicates_removed = len(signals) - len(unique_signals)

    logger.info(
        f"Deduplication: {len(signals)} -> {len(unique_signals)} signals "
        f"({duplicates_removed} removed)"
    )

    for signal_type, count in sorted(type_counts.items()):
        logger.debug(f"  {signal_type}: {count}")

    return DeduplicationResult(
        unique_signals=unique_signals,
        duplicates_removed=duplicates_removed,
        by_type=type_counts,
    )


# Keep for backward compatibility but simplified
def deduplicate_cross_filing(signals: List[Dict[str, Any]], date_window_days: int = 90) -> List[Dict[str, Any]]:
    """Cross-filing dedup is now handled in main deduplicate_signals."""
    # Already done in deduplicate_signals
    return signals
