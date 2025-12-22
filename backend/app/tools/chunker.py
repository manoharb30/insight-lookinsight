"""Filing content chunking tools."""

from typing import List, Dict, Any
from dataclasses import dataclass
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class Chunk:
    content: str
    item_number: str
    chunk_index: int
    token_count: int
    metadata: Dict[str, Any]


class FilingChunker:
    """Chunk SEC filings for processing."""

    def __init__(
        self,
        max_tokens: int = 2000,
        overlap_tokens: int = 200,
        model: str = "gpt-4o",
    ):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.encoding = tiktoken.encoding_for_model(model)

        # Use characters as approximation (4 chars ≈ 1 token)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_tokens * 4,
            chunk_overlap=overlap_tokens * 4,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))

    def chunk_filing(self, filing_data: Dict[str, Any]) -> List[Chunk]:
        """Chunk a filing into processable segments."""
        chunks = []
        chunk_index = 0

        filing_type = filing_data.get("filing_type", "")
        accession = filing_data.get("accession_number", "")
        filed_at = filing_data.get("filed_at", "")

        if filing_type == "8-K" and filing_data.get("sections"):
            # Chunk by item section for 8-K
            for item_number, content in filing_data["sections"].items():
                if not content or len(content.strip()) < 50:
                    continue

                item_chunks = self._split_text(content)
                for i, chunk_text in enumerate(item_chunks):
                    chunks.append(
                        Chunk(
                            content=chunk_text,
                            item_number=item_number,
                            chunk_index=chunk_index,
                            token_count=self.count_tokens(chunk_text),
                            metadata={
                                "filing_type": filing_type,
                                "accession_number": accession,
                                "filed_at": filed_at,
                                "section_chunk": i,
                            },
                        )
                    )
                    chunk_index += 1
        else:
            # Chunk full text for other filings
            raw_text = filing_data.get("raw_text", "")
            if raw_text:
                text_chunks = self._split_text(raw_text)
                for i, chunk_text in enumerate(text_chunks):
                    chunks.append(
                        Chunk(
                            content=chunk_text,
                            item_number="full",
                            chunk_index=chunk_index,
                            token_count=self.count_tokens(chunk_text),
                            metadata={
                                "filing_type": filing_type,
                                "accession_number": accession,
                                "filed_at": filed_at,
                                "section_chunk": i,
                            },
                        )
                    )
                    chunk_index += 1

        return chunks

    def _split_text(self, text: str) -> List[str]:
        """Split text into chunks."""
        if self.count_tokens(text) <= self.max_tokens:
            return [text]

        return self.splitter.split_text(text)

    def chunk_for_extraction(
        self,
        filing_data: Dict[str, Any],
        focus_items: List[str] = None,
    ) -> List[Chunk]:
        """Chunk filing with focus on signal-relevant items."""
        # High-value 8-K items for distress signals
        distress_items = focus_items or [
            "1.01",  # Entry into Material Agreement
            "1.02",  # Termination of Agreement
            "1.03",  # Bankruptcy
            "2.01",  # Acquisition/Disposition
            "2.04",  # Triggering Events (Defaults)
            "2.05",  # Costs Associated with Exit
            "2.06",  # Material Impairments
            "3.01",  # Delisting
            "4.01",  # Auditor Changes
            "4.02",  # Non-Reliance on Financials
            "5.02",  # Director/Officer Changes
            "5.03",  # Amendments to Articles
            "7.01",  # Regulation FD Disclosure
            "8.01",  # Other Events
        ]

        all_chunks = self.chunk_filing(filing_data)

        if filing_data.get("filing_type") != "8-K":
            return all_chunks

        # Prioritize distress-relevant items
        prioritized = []
        other = []

        for chunk in all_chunks:
            if any(chunk.item_number.startswith(item) for item in distress_items):
                prioritized.append(chunk)
            else:
                other.append(chunk)

        return prioritized + other


# Singleton instance
chunker = FilingChunker()
