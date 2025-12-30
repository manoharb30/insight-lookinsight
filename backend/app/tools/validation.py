"""Signal validation using LLM."""

import asyncio
import json
import random
from typing import List, Dict, Any, Tuple, Optional
from openai import AsyncOpenAI, RateLimitError

from app.config import get_settings
from app.prompts.validation import LLM_VALIDATION_PROMPT, VALID_SIGNAL_TYPES
from app.core.logging import get_logger
from app.core.constants import MIN_CONFIDENCE, MIN_EVIDENCE_LENGTH

logger = get_logger(__name__)
settings = get_settings()


class SignalValidator:
    """
    Validate extracted signals using LLM.

    Two-stage validation:
    1. Basic checks (fast, no API cost)
    2. LLM validation (accurate, catches semantic issues)
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        max_concurrent: int = 3,
    ):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model
        self.max_concurrent = max_concurrent

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Create a new semaphore for the current event loop."""
        return asyncio.Semaphore(self.max_concurrent)

    async def _call_with_retry(self, messages: List[Dict], max_retries: int = 5) -> Optional[str]:
        """Call OpenAI API with exponential backoff retry on rate limit."""
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=200,
                )
                return response.choices[0].message.content
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Rate limited, waiting {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Rate limit exceeded after {max_retries} retries")
                    raise
        return None

    def _basic_validation(self, signal: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Fast validation checks (no LLM call).

        Returns:
            Tuple of (passed, rejection_reason)
        """
        # Check signal type
        signal_type = signal.get("type", "")
        if signal_type not in VALID_SIGNAL_TYPES:
            return False, f"Invalid signal type: {signal_type}"

        # Check evidence exists and has minimum length
        evidence = signal.get("evidence", "")
        if not evidence or len(evidence.strip()) < MIN_EVIDENCE_LENGTH:
            return False, f"Evidence too short ({len(evidence)} chars)"

        # Check confidence threshold
        confidence = signal.get("confidence", 0)
        if confidence < MIN_CONFIDENCE:
            return False, f"Confidence too low ({confidence} < {MIN_CONFIDENCE})"

        # Check severity is valid
        severity = signal.get("severity", 0)
        if not (1 <= severity <= 10):
            return False, f"Invalid severity: {severity}"

        return True, ""

    async def _llm_validate_signal(
        self,
        signal: Dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate a single signal using LLM.

        Returns:
            Tuple of (is_valid, updated_signal_or_rejection_info)
        """
        async with semaphore:
            try:
                prompt = LLM_VALIDATION_PROMPT.format(
                    signal_type=signal.get("type", ""),
                    evidence=signal.get("evidence", ""),
                    severity=signal.get("severity", 5),
                    filing_type=signal.get("filing_type", "8-K"),
                    filing_date=signal.get("date", ""),
                    person=signal.get("person") or "N/A",
                )

                messages = [
                    {
                        "role": "system",
                        "content": "You are an expert SEC filing analyst. Validate signals accurately. Return valid JSON only."
                    },
                    {"role": "user", "content": prompt},
                ]
                content = await self._call_with_retry(messages)
                if not content:
                    # If retry fails, reject the signal
                    return (signal, False, "Rate limit exceeded")
                result = json.loads(content)

                is_valid = result.get("is_valid", False)

                # Only reject if classification is wrong
                if not is_valid:
                    reason = result.get("rejection_reason", "Failed LLM validation")
                    signal["rejection_reason"] = f"LLM: {reason}"
                    logger.info(f"LLM rejected {signal.get('type')}: {reason}")
                    return False, signal

                # Apply corrections if any
                if result.get("corrected_type"):
                    logger.info(
                        f"Correcting signal type: {signal['type']} -> {result['corrected_type']}"
                    )
                    signal["type"] = result["corrected_type"]

                if result.get("corrected_severity"):
                    logger.info(
                        f"Correcting severity: {signal['severity']} -> {result['corrected_severity']}"
                    )
                    signal["severity"] = result["corrected_severity"]

                # Update confidence from validation
                if result.get("confidence"):
                    signal["validation_confidence"] = result["confidence"]

                signal["validated"] = True
                signal["validation_notes"] = "Passed LLM validation"
                return True, signal

            except Exception as e:
                logger.error(f"LLM validation error: {e}")
                # On error, let the signal pass (fail open)
                signal["validated"] = True
                signal["validation_notes"] = f"LLM validation error: {e}"
                return True, signal

    async def validate_signals_async(
        self,
        signals: List[Dict[str, Any]],
        use_llm: bool = True,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate signals with basic checks and optional LLM validation.

        Args:
            signals: List of signal dicts
            use_llm: Whether to use LLM validation (default True)

        Returns:
            Tuple of (validated_signals, rejected_signals)
        """
        validated = []
        rejected = []

        # Stage 1: Basic validation (fast)
        basic_passed = []
        for signal in signals:
            passed, reason = self._basic_validation(signal)
            if passed:
                basic_passed.append(signal)
            else:
                signal["rejection_reason"] = f"Basic: {reason}"
                rejected.append(signal)
                logger.debug(f"Basic validation rejected: {reason}")

        logger.info(f"Basic validation: {len(signals)} -> {len(basic_passed)} signals")

        if not use_llm:
            # Mark as validated without LLM
            for signal in basic_passed:
                signal["validated"] = True
                signal["validation_notes"] = "Passed basic validation (LLM skipped)"
            return basic_passed, rejected

        # Stage 2: LLM validation (accurate)
        if not basic_passed:
            return [], rejected

        # Create semaphore for this event loop
        semaphore = self._get_semaphore()

        tasks = [
            self._llm_validate_signal(signal, semaphore)
            for signal in basic_passed
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Validation task failed: {result}")
                continue

            is_valid, signal = result
            if is_valid:
                validated.append(signal)
            else:
                rejected.append(signal)

        logger.info(
            f"LLM validation: {len(basic_passed)} -> {len(validated)} signals "
            f"({len(basic_passed) - len(validated)} rejected)"
        )

        return validated, rejected

    def validate_signals(
        self,
        signals: List[Dict[str, Any]],
        source_texts: Optional[Dict[str, str]] = None,
        use_gpt: bool = True,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Sync wrapper for validate_signals_async.

        Args:
            signals: List of signal dicts
            source_texts: Not used (kept for backward compatibility)
            use_gpt: Whether to use LLM validation

        Returns:
            Tuple of (validated_signals, rejected_signals)
        """
        # Create new event loop if needed (for Celery workers)
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an async context, we can't use asyncio.run
            # This shouldn't happen in normal flow
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.run(self.validate_signals_async(signals, use_llm=use_gpt))
        except RuntimeError:
            # No running loop, safe to use asyncio.run
            return asyncio.run(self.validate_signals_async(signals, use_llm=use_gpt))


# Singleton instance
signal_validator = SignalValidator(max_concurrent=5)
