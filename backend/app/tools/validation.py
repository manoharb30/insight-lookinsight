"""Validation tools for signal verification."""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from openai import OpenAI

from app.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limiter import openai_limiter
from app.prompts.validation import (
    VALIDATION_RULES,
    FALSE_POSITIVE_PATTERNS,
    SIGNAL_VALIDATION_PROMPT,
    EVIDENCE_VERIFICATION_PROMPT,
)

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class ValidationResult:
    """Result of signal validation."""
    is_valid: bool
    adjusted_severity: int
    adjusted_confidence: float
    rejection_reason: Optional[str]
    validation_notes: str
    evidence_verified: bool


class EvidenceVerifier:
    """Verifies that evidence exists in source text."""

    def verify_evidence(
        self,
        evidence: str,
        source_text: str,
        signal_type: str,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Verify evidence exists in source text.

        Args:
            evidence: The claimed evidence quote
            source_text: The original filing text
            signal_type: Type of signal

        Returns:
            Tuple of (found, match_quality, corrected_evidence)
        """
        if not evidence or not source_text:
            return False, "not_found", None

        evidence_lower = evidence.lower().strip()
        source_lower = source_text.lower()

        # Try exact match first
        if evidence_lower in source_lower:
            return True, "exact", None

        # Try fuzzy match - check if key phrases exist
        # Split evidence into phrases and check each
        key_words = [w for w in evidence_lower.split() if len(w) > 4]
        if len(key_words) > 0:
            matches = sum(1 for w in key_words if w in source_lower)
            match_ratio = matches / len(key_words)

            if match_ratio >= 0.8:
                return True, "partial", None
            elif match_ratio >= 0.5:
                # Try to find the actual matching text
                corrected = self._find_closest_match(evidence, source_text)
                if corrected:
                    return True, "partial", corrected

        return False, "not_found", None

    def _find_closest_match(self, evidence: str, source_text: str) -> Optional[str]:
        """Find the closest matching text in source."""
        # Simple sliding window approach
        evidence_words = evidence.lower().split()
        if len(evidence_words) < 3:
            return None

        # Look for sequences that contain the key words
        source_words = source_text.split()
        window_size = min(len(evidence_words) * 2, 50)

        for i in range(len(source_words) - window_size):
            window = " ".join(source_words[i : i + window_size])
            window_lower = window.lower()

            # Count matching words
            matches = sum(1 for w in evidence_words if w in window_lower)
            if matches >= len(evidence_words) * 0.7:
                return window

        return None


class FalsePositiveDetector:
    """Detects false positive patterns in signals."""

    def check_false_positive(
        self,
        signal_type: str,
        evidence: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a signal is a false positive.

        Args:
            signal_type: Type of signal
            evidence: Evidence text

        Returns:
            Tuple of (is_false_positive, reason)
        """
        if not evidence:
            return True, "No evidence provided"

        evidence_lower = evidence.lower()

        # Check signal-specific false positive patterns
        patterns = FALSE_POSITIVE_PATTERNS.get(signal_type, [])
        for pattern in patterns:
            if re.search(pattern.lower(), evidence_lower):
                return True, f"Matches false positive pattern: {pattern}"

        return False, None


class RuleBasedValidator:
    """Validates signals using predefined rules."""

    def validate(
        self,
        signal_type: str,
        evidence: str,
        severity: int,
        confidence: float,
        person: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validate a signal against rules.

        Args:
            signal_type: Type of signal
            evidence: Evidence text
            severity: Signal severity
            confidence: Signal confidence
            person: Person name if applicable

        Returns:
            Tuple of (is_valid, rejection_reason, adjustments)
        """
        rules = VALIDATION_RULES.get(signal_type, {})
        if not rules:
            # No specific rules, accept with defaults
            return True, None, {}

        evidence_lower = evidence.lower() if evidence else ""
        adjustments = {}

        # Check must_contain_any
        if "must_contain_any" in rules:
            found = any(
                phrase.lower() in evidence_lower
                for phrase in rules["must_contain_any"]
            )
            if not found:
                return False, f"Evidence missing required phrases for {signal_type}", {}

        # Check must_not_contain
        if "must_not_contain" in rules:
            for phrase in rules["must_not_contain"]:
                if phrase.lower() in evidence_lower:
                    return False, f"Evidence contains disqualifying phrase: {phrase}", {}

        # Check require_person
        if rules.get("require_person") and not person:
            return False, f"{signal_type} requires a person name", {}

        # Check min_confidence
        min_conf = rules.get("min_confidence", 0.5)
        if confidence < min_conf:
            adjustments["adjusted_confidence"] = min_conf
            logger.debug(f"Adjusting confidence from {confidence} to {min_conf}")

        # Check min_severity
        min_sev = rules.get("min_severity", 1)
        if severity < min_sev:
            adjustments["adjusted_severity"] = min_sev
            logger.debug(f"Adjusting severity from {severity} to {min_sev}")

        return True, None, adjustments


class GPTValidator:
    """Uses GPT-4o for complex validation."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"

    def validate(
        self,
        signal_type: str,
        evidence: str,
        severity: int,
        confidence: float,
        date: Optional[str] = None,
        person: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate a signal using GPT-4o.

        Args:
            signal_type: Type of signal
            evidence: Evidence text
            severity: Signal severity
            confidence: Signal confidence
            date: Signal date
            person: Person name

        Returns:
            ValidationResult
        """
        rules = VALIDATION_RULES.get(signal_type, {})
        rules_text = json.dumps(rules, indent=2) if rules else "No specific rules"

        prompt = SIGNAL_VALIDATION_PROMPT.format(
            signal_type=signal_type,
            evidence=evidence,
            date=date or "Not specified",
            person=person or "Not specified",
            severity=severity,
            confidence=confidence,
            validation_rules=rules_text,
        )

        try:
            openai_limiter.acquire()

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You validate financial signals. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)

            return ValidationResult(
                is_valid=result.get("is_valid", False),
                adjusted_severity=result.get("adjusted_severity", severity),
                adjusted_confidence=result.get("adjusted_confidence", confidence),
                rejection_reason=result.get("rejection_reason"),
                validation_notes=result.get("validation_notes", ""),
                evidence_verified=True,
            )

        except Exception as e:
            logger.error(f"GPT validation error: {e}")
            # Fall back to accepting the signal as-is
            return ValidationResult(
                is_valid=True,
                adjusted_severity=severity,
                adjusted_confidence=confidence,
                rejection_reason=None,
                validation_notes=f"GPT validation failed: {e}",
                evidence_verified=False,
            )


class SignalValidator:
    """
    Main signal validator combining all validation methods.

    Validation pipeline:
    1. Evidence verification (exists in source)
    2. False positive detection
    3. Rule-based validation
    4. Optional GPT validation for edge cases
    """

    def __init__(self, use_gpt_fallback: bool = True):
        self.evidence_verifier = EvidenceVerifier()
        self.false_positive_detector = FalsePositiveDetector()
        self.rule_validator = RuleBasedValidator()
        self.gpt_validator = GPTValidator() if use_gpt_fallback else None
        self.use_gpt_fallback = use_gpt_fallback

    def validate_signal(
        self,
        signal: Dict[str, Any],
        source_text: Optional[str] = None,
        use_gpt: bool = False,
    ) -> ValidationResult:
        """
        Validate a single signal.

        Args:
            signal: Signal dict with type, evidence, severity, confidence, etc.
            source_text: Original filing text for evidence verification
            use_gpt: Whether to use GPT for validation

        Returns:
            ValidationResult
        """
        signal_type = signal.get("type", "")
        evidence = signal.get("evidence", "")
        severity = signal.get("severity", 5)
        confidence = signal.get("confidence", 0.8)
        person = signal.get("person")
        date = signal.get("date")

        # Step 1: Evidence verification (if source text provided)
        evidence_verified = True
        if source_text:
            found, match_quality, corrected = self.evidence_verifier.verify_evidence(
                evidence, source_text, signal_type
            )
            if not found:
                logger.info(f"Evidence not found for {signal_type}: {evidence[:50]}...")
                return ValidationResult(
                    is_valid=False,
                    adjusted_severity=severity,
                    adjusted_confidence=confidence,
                    rejection_reason="Evidence not found in source text",
                    validation_notes="Evidence verification failed",
                    evidence_verified=False,
                )
            evidence_verified = True
            if corrected:
                evidence = corrected

        # Step 2: False positive detection
        is_fp, fp_reason = self.false_positive_detector.check_false_positive(
            signal_type, evidence
        )
        if is_fp:
            logger.info(f"False positive detected for {signal_type}: {fp_reason}")
            return ValidationResult(
                is_valid=False,
                adjusted_severity=severity,
                adjusted_confidence=confidence,
                rejection_reason=fp_reason,
                validation_notes="Failed false positive check",
                evidence_verified=evidence_verified,
            )

        # Step 3: Rule-based validation
        is_valid, rejection_reason, adjustments = self.rule_validator.validate(
            signal_type, evidence, severity, confidence, person
        )
        if not is_valid:
            logger.info(f"Rule validation failed for {signal_type}: {rejection_reason}")
            return ValidationResult(
                is_valid=False,
                adjusted_severity=severity,
                adjusted_confidence=confidence,
                rejection_reason=rejection_reason,
                validation_notes="Failed rule-based validation",
                evidence_verified=evidence_verified,
            )

        # Apply adjustments from rule validation
        adjusted_severity = adjustments.get("adjusted_severity", severity)
        adjusted_confidence = adjustments.get("adjusted_confidence", confidence)

        # Step 4: GPT validation for edge cases (optional)
        if use_gpt and self.gpt_validator and confidence < 0.7:
            logger.debug(f"Using GPT validation for low-confidence signal: {signal_type}")
            gpt_result = self.gpt_validator.validate(
                signal_type, evidence, adjusted_severity, adjusted_confidence, date, person
            )
            return gpt_result

        return ValidationResult(
            is_valid=True,
            adjusted_severity=adjusted_severity,
            adjusted_confidence=adjusted_confidence,
            rejection_reason=None,
            validation_notes="Passed all validation checks",
            evidence_verified=evidence_verified,
        )

    def validate_signals(
        self,
        signals: List[Dict[str, Any]],
        source_texts: Optional[Dict[str, str]] = None,
        use_gpt: bool = False,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate multiple signals.

        Args:
            signals: List of signal dicts
            source_texts: Optional dict mapping filing accession to text
            use_gpt: Whether to use GPT for validation

        Returns:
            Tuple of (validated_signals, rejected_signals)
        """
        validated = []
        rejected = []

        for signal in signals:
            source_text = None
            if source_texts:
                accession = signal.get("filing_accession", "")
                source_text = source_texts.get(accession)

            result = self.validate_signal(signal, source_text, use_gpt)

            if result.is_valid:
                # Update signal with adjusted values
                validated_signal = signal.copy()
                validated_signal["severity"] = result.adjusted_severity
                validated_signal["confidence"] = result.adjusted_confidence
                validated_signal["validated"] = True
                validated_signal["validation_notes"] = result.validation_notes
                validated.append(validated_signal)
            else:
                # Add rejection info
                rejected_signal = signal.copy()
                rejected_signal["rejection_reason"] = result.rejection_reason
                rejected_signal["validation_notes"] = result.validation_notes
                rejected.append(rejected_signal)

        logger.info(
            f"Validation complete: {len(validated)} valid, {len(rejected)} rejected"
        )
        return validated, rejected


# Singleton instance
signal_validator = SignalValidator()
