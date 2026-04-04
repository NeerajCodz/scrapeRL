"""Embeddings service for semantic search and similarity matching."""

import hashlib
import json
import logging
from typing import Any

import numpy as np
import httpx

logger = logging.getLogger(__name__)

# Default embedding dimension for fallback
DEFAULT_EMBEDDING_DIM = 768


class EmbeddingsService:
    """Service for generating embeddings using multiple providers."""

    def __init__(
        self,
        provider: str = "openai",
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
    ):
        """
        Initialize embeddings service.

        Args:
            provider: Provider to use ('openai', 'google')
            model: Model name for embeddings
            api_key: API key for the provider
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self._cache: dict[str, np.ndarray] = {}  # In-memory cache

    def _hash_text(self, text: str) -> str:
        """Create a hash of text for cache key."""
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    def _fallback_embedding(self, text: str, dimension: int = DEFAULT_EMBEDDING_DIM) -> np.ndarray:
        """Generate a deterministic fallback embedding when providers fail."""
        # Simple character-based embedding for fallback
        values = [((ord(ch) % 97) / 97.0) for ch in text[:dimension]]
        if not values:
            values = [0.0]
        
        # Repeat to fill dimension
        repeats = (dimension + len(values) - 1) // len(values)
        vector = (values * repeats)[:dimension]
        
        return np.array(vector, dtype=np.float32)

    async def embed_text(
        self,
        text: str,
        task_type: str = "document",
    ) -> np.ndarray:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            task_type: Type of task ('document' or 'query')

        Returns:
            Embedding vector as numpy array
        """
        # Check cache
        cache_key = self._hash_text(f"{self.provider}:{self.model}:{task_type}:{text}")
        if cache_key in self._cache:
            logger.debug(f"Embedding cache hit for text length {len(text)}")
            return self._cache[cache_key]

        try:
            if self.provider == "openai":
                embedding = await self._embed_openai(text)
            elif self.provider == "google":
                embedding = await self._embed_google(text, task_type)
            else:
                logger.warning(f"Unknown provider {self.provider}, using fallback")
                embedding = self._fallback_embedding(text)

            # Cache the result
            self._cache[cache_key] = embedding
            return embedding

        except Exception as e:
            logger.warning(f"Embedding failed: {e}, using fallback")
            embedding = self._fallback_embedding(text)
            self._cache[cache_key] = embedding
            return embedding

    async def _embed_openai(self, text: str) -> np.ndarray:
        """Generate embedding using OpenAI API."""
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")

        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": text,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            embedding = data["data"][0]["embedding"]
            return np.array(embedding, dtype=np.float32)

    async def _embed_google(self, text: str, task_type: str = "document") -> np.ndarray:
        """Generate embedding using Google Gemini API."""
        if not self.api_key:
            raise ValueError("Google API key not provided")

        # Map task types to Google's task types
        google_task_type = "RETRIEVAL_DOCUMENT" if task_type == "document" else "RETRIEVAL_QUERY"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:embedContent"
        params = {"key": self.api_key}
        payload = {
            "content": {"parts": [{"text": text}]},
            "taskType": google_task_type,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, params=params, json=payload)
            response.raise_for_status()
            data = response.json()
            embedding = data["embedding"]["values"]
            return np.array(embedding, dtype=np.float32)

    async def embed_batch(self, texts: list[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            2D numpy array of embeddings
        """
        if not texts:
            return np.array([])

        embeddings = []
        for text in texts:
            embedding = await self.embed_text(text)
            embeddings.append(embedding)

        return np.vstack(embeddings)

    async def embed_query(self, query: str) -> np.ndarray:
        """
        Generate embedding for a search query.

        Args:
            query: Search query text

        Returns:
            Embedding vector as numpy array
        """
        return await self.embed_text(query, task_type="query")

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Cosine similarity score (0-1)
        """
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def find_most_similar(
        self,
        query_embedding: np.ndarray,
        embeddings: list[np.ndarray],
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """
        Find most similar embeddings to a query.

        Args:
            query_embedding: Query embedding vector
            embeddings: List of embedding vectors to search
            top_k: Number of top results to return

        Returns:
            List of (index, similarity_score) tuples, sorted by similarity
        """
        similarities = []
        for idx, emb in enumerate(embeddings):
            sim = self.cosine_similarity(query_embedding, emb)
            similarities.append((idx, sim))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()
        logger.info("Embedding cache cleared")


# Factory function to create embeddings service
def create_embeddings_service(
    provider: str = "openai",
    model: str | None = None,
    api_key: str | None = None,
) -> EmbeddingsService:
    """
    Create an embeddings service instance.

    Args:
        provider: Provider name ('openai', 'google')
        model: Model name (uses provider default if None)
        api_key: API key for the provider

    Returns:
        EmbeddingsService instance
    """
    if model is None:
        if provider == "openai":
            model = "text-embedding-3-small"
        elif provider == "google":
            model = "text-embedding-004"
        else:
            raise ValueError(f"Unknown provider: {provider}")

    return EmbeddingsService(provider=provider, model=model, api_key=api_key)
