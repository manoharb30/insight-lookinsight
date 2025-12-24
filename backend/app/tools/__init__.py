# Tools module
from app.tools.edgar import edgar_client, SECEdgarClient
from app.tools.embeddings import embedding_service, EmbeddingService, embeddings_client
from app.tools.extraction import signal_extractor, SignalExtractor
from app.tools.validation import signal_validator, SignalValidator
from app.tools.deduplication import deduplicate_signals

__all__ = [
    "edgar_client",
    "SECEdgarClient",
    "embedding_service",
    "EmbeddingService",
    "embeddings_client",  # Backward compatible alias
    "signal_extractor",
    "SignalExtractor",
    "signal_validator",
    "SignalValidator",
    "deduplicate_signals",
]
