"""Embedding generation and search tools."""

from typing import List, Optional
from openai import OpenAI, AsyncOpenAI

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmbeddingService:
    """Generate embeddings using OpenAI - supports both sync and async."""

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self.dimension = 1536  # OpenAI embedding dimension
        self._sync_client: Optional[OpenAI] = None
        self._async_client: Optional[AsyncOpenAI] = None

    @property
    def sync_client(self) -> OpenAI:
        """Lazy init sync client."""
        if self._sync_client is None:
            self._sync_client = OpenAI(api_key=settings.openai_api_key)
        return self._sync_client

    @property
    def async_client(self) -> AsyncOpenAI:
        """Lazy init async client."""
        if self._async_client is None:
            self._async_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._async_client

    def _truncate_text(self, text: str, max_chars: int = 30000) -> str:
        """Truncate text if too long (max ~8000 tokens)."""
        if len(text) > max_chars:
            return text[:max_chars]
        return text

    # ==================== Sync Methods ====================

    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text (sync).

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None on error
        """
        try:
            text = self._truncate_text(text)
            response = self.sync_client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimension,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None

    def embed_texts(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts (sync).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (None for failed items)
        """
        if not texts:
            return []

        try:
            truncated = [self._truncate_text(t) for t in texts]
            response = self.sync_client.embeddings.create(
                model=self.model,
                input=truncated,
                dimensions=self.dimension,
            )
            # Sort by index to maintain order
            embeddings = sorted(response.data, key=lambda x: x.index)
            return [e.embedding for e in embeddings]
        except Exception as e:
            logger.error(f"Batch embedding error: {e}")
            return [None] * len(texts)

    # ==================== Async Methods ====================

    async def embed_text_async(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text (async).

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None on error
        """
        try:
            text = self._truncate_text(text)
            response = await self.async_client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimension,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Async embedding error: {e}")
            return None

    async def embed_batch_async(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts (async).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (None for failed items)
        """
        if not texts:
            return []

        try:
            truncated = [self._truncate_text(t) for t in texts]
            response = await self.async_client.embeddings.create(
                model=self.model,
                input=truncated,
                dimensions=self.dimension,
            )
            # Sort by index to maintain order
            embeddings = sorted(response.data, key=lambda x: x.index)
            return [e.embedding for e in embeddings]
        except Exception as e:
            logger.error(f"Async batch embedding error: {e}")
            return [None] * len(texts)


# Singleton instance
embedding_service = EmbeddingService()

# Backward compatible alias
embeddings_client = embedding_service
