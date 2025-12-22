"""GPT-4o signal extraction tools."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from openai import OpenAI
import json

from app.config import get_settings
from app.prompts.extraction import SIGNAL_EXTRACTION_PROMPT, SIGNAL_TYPES

settings = get_settings()


@dataclass
class ExtractedSignal:
    signal_type: str
    severity: int
    confidence: float
    evidence: str
    date: Optional[str]
    person: Optional[str]
    item_number: str
    raw_response: Dict[str, Any]


class SignalExtractor:
    """Extract bankruptcy signals from filing text using GPT-4o."""

    def __init__(self, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = model

    def extract_signals(
        self,
        text: str,
        item_number: str,
        filing_date: str,
        company_name: str = "",
    ) -> List[ExtractedSignal]:
        """Extract signals from a chunk of filing text."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": SIGNAL_EXTRACTION_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": f"""Analyze this SEC filing excerpt and extract any bankruptcy distress signals.

Company: {company_name}
Filing Date: {filing_date}
Item Number: {item_number}

--- FILING TEXT ---
{text}
--- END TEXT ---

Return a JSON array of signals found. If no signals, return an empty array [].
""",
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            signals = []
            for sig in result.get("signals", []):
                if sig.get("type") not in SIGNAL_TYPES:
                    continue

                signals.append(
                    ExtractedSignal(
                        signal_type=sig["type"],
                        severity=min(7, max(1, sig.get("severity", 5))),
                        confidence=min(1.0, max(0.0, sig.get("confidence", 0.8))),
                        evidence=sig.get("evidence", ""),
                        date=sig.get("date") or filing_date,
                        person=sig.get("person"),
                        item_number=item_number,
                        raw_response=sig,
                    )
                )

            return signals

        except Exception as e:
            print(f"Error extracting signals: {e}")
            return []

    def batch_extract(
        self,
        chunks: List[Dict[str, Any]],
        company_name: str = "",
    ) -> List[ExtractedSignal]:
        """Extract signals from multiple chunks."""
        all_signals = []

        for chunk in chunks:
            signals = self.extract_signals(
                text=chunk["content"],
                item_number=chunk.get("item_number", ""),
                filing_date=chunk.get("filed_at", ""),
                company_name=company_name,
            )
            all_signals.extend(signals)

        return all_signals


# Singleton instance
signal_extractor = SignalExtractor()
