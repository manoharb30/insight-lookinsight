"""OpenAI embeddings tools."""

from typing import List
from openai import OpenAI

from app.config import get_settings

settings = get_settings()


class EmbeddingsClient:
    """Client for generating OpenAI embeddings."""

    def __init__(self, model: str = "text-embedding-3-small"):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = model
        self.dimensions = 1536  # Default for text-embedding-3-small

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
        )
        return response.data[0].embedding

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        # Batch API call
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )

        # Sort by index to maintain order
        embeddings = sorted(response.data, key=lambda x: x.index)
        return [e.embedding for e in embeddings]


# Singleton instance
embeddings_client = EmbeddingsClient()
