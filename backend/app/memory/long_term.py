"""Long-term memory with persistent vector storage using ChromaDB."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Document(BaseModel):
    """A document stored in long-term memory."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"arbitrary_types_allowed": True}


class SearchResult(BaseModel):
    """A search result from long-term memory."""

    document: Document
    score: float
    distance: float | None = None

    model_config = {"arbitrary_types_allowed": True}


class LongTermMemory:
    """
    Long-term persistent memory using ChromaDB for vector storage.

    This memory layer provides semantic search capabilities using embeddings.
    It persists across episodes and sessions, storing knowledge that should
    be retained long-term.

    Attributes:
        collection_name: Name of the ChromaDB collection.
        persist_directory: Directory for persistent storage.
        top_k: Default number of results to return from search.
    """

    def __init__(
        self,
        collection_name: str = "scraperl_memory",
        persist_directory: str = "./data/chroma",
        top_k: int = 10,
        embedding_function: Any | None = None,
    ) -> None:
        """
        Initialize long-term memory.

        Args:
            collection_name: Name of the ChromaDB collection.
            persist_directory: Directory for persistent storage.
            top_k: Default number of results to return from search.
            embedding_function: Optional custom embedding function.
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.top_k = top_k
        self._embedding_function = embedding_function
        self._client: Any = None
        self._collection: Any = None
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """
        Initialize ChromaDB client and collection.

        This should be called before using other methods.
        """
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            try:
                import chromadb
                from chromadb.config import Settings

                # Create persistent client
                self._client = chromadb.Client(
                    Settings(
                        chroma_db_impl="duckdb+parquet",
                        persist_directory=self.persist_directory,
                        anonymized_telemetry=False,
                    )
                )

                # Get or create collection
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    embedding_function=self._embedding_function,
                    metadata={"hnsw:space": "cosine"},
                )

                self._initialized = True
                logger.info(
                    f"Initialized long-term memory: collection={self.collection_name}"
                )

            except ImportError:
                logger.warning(
                    "ChromaDB not available. Long-term memory will use in-memory fallback."
                )
                self._use_fallback()
            except Exception as e:
                logger.warning(
                    f"Failed to initialize ChromaDB: {e}. Using in-memory fallback."
                )
                self._use_fallback()

    def _use_fallback(self) -> None:
        """Use in-memory fallback when ChromaDB is unavailable."""
        self._client = None
        self._collection = None
        self._fallback_store: dict[str, Document] = {}
        self._initialized = True

    @property
    def is_initialized(self) -> bool:
        """Check if memory is initialized."""
        return self._initialized

    @property
    def _using_fallback(self) -> bool:
        """Check if using in-memory fallback."""
        return self._collection is None

    def _generate_id(self, content: str) -> str:
        """Generate a deterministic ID from content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def store(
        self,
        content: str,
        document_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> Document:
        """
        Store a document in long-term memory.

        Args:
            content: Text content to store.
            document_id: Optional custom ID. Generated from content if not provided.
            metadata: Optional metadata dictionary.
            embedding: Optional pre-computed embedding vector.

        Returns:
            The stored document.
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            doc_id = document_id or self._generate_id(content)
            now = datetime.now(timezone.utc)

            document = Document(
                id=doc_id,
                content=content,
                embedding=embedding,
                metadata=metadata or {},
                created_at=now,
                updated_at=now,
            )

            if self._using_fallback:
                self._fallback_store[doc_id] = document
            else:
                # Store in ChromaDB
                try:
                    self._collection.upsert(
                        ids=[doc_id],
                        documents=[content],
                        metadatas=[
                            {
                                **document.metadata,
                                "created_at": now.isoformat(),
                                "updated_at": now.isoformat(),
                            }
                        ],
                        embeddings=[embedding] if embedding else None,
                    )
                except Exception as e:
                    logger.error(f"Failed to store document: {e}")
                    raise

            return document

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        where: dict[str, Any] | None = None,
        query_embedding: list[float] | None = None,
    ) -> list[SearchResult]:
        """
        Search for similar documents using semantic search.

        Args:
            query: Search query text.
            top_k: Number of results to return. Uses default if not specified.
            where: Optional metadata filter.
            query_embedding: Optional pre-computed query embedding.

        Returns:
            List of search results with scores.
        """
        if not self._initialized:
            await self.initialize()

        k = top_k or self.top_k

        async with self._lock:
            if self._using_fallback:
                # Simple substring matching for fallback
                results = []
                query_lower = query.lower()
                for doc in self._fallback_store.values():
                    if query_lower in doc.content.lower():
                        results.append(
                            SearchResult(document=doc, score=1.0, distance=0.0)
                        )
                return results[:k]

            try:
                # Query ChromaDB
                query_params: dict[str, Any] = {
                    "n_results": k,
                }

                if query_embedding:
                    query_params["query_embeddings"] = [query_embedding]
                else:
                    query_params["query_texts"] = [query]

                if where:
                    query_params["where"] = where

                results = self._collection.query(**query_params)

                # Parse results
                search_results = []
                if results and results.get("ids"):
                    for i, doc_id in enumerate(results["ids"][0]):
                        content = (
                            results["documents"][0][i]
                            if results.get("documents")
                            else ""
                        )
                        metadata = (
                            results["metadatas"][0][i]
                            if results.get("metadatas")
                            else {}
                        )
                        distance = (
                            results["distances"][0][i]
                            if results.get("distances")
                            else None
                        )

                        doc = Document(
                            id=doc_id,
                            content=content,
                            metadata=metadata,
                        )

                        # Convert distance to score (cosine similarity)
                        score = 1 - distance if distance is not None else 1.0

                        search_results.append(
                            SearchResult(
                                document=doc,
                                score=score,
                                distance=distance,
                            )
                        )

                return search_results

            except Exception as e:
                logger.error(f"Search failed: {e}")
                return []

    async def get(self, document_id: str) -> Document | None:
        """
        Retrieve a document by ID.

        Args:
            document_id: The document ID to retrieve.

        Returns:
            The document or None if not found.
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            if self._using_fallback:
                return self._fallback_store.get(document_id)

            try:
                result = self._collection.get(ids=[document_id])
                if result and result["ids"]:
                    return Document(
                        id=result["ids"][0],
                        content=result["documents"][0] if result.get("documents") else "",
                        metadata=result["metadatas"][0] if result.get("metadatas") else {},
                    )
                return None
            except Exception as e:
                logger.error(f"Failed to get document: {e}")
                return None

    async def delete(self, document_id: str) -> bool:
        """
        Delete a document from long-term memory.

        Args:
            document_id: The document ID to delete.

        Returns:
            True if document was deleted, False otherwise.
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            if self._using_fallback:
                if document_id in self._fallback_store:
                    del self._fallback_store[document_id]
                    return True
                return False

            try:
                self._collection.delete(ids=[document_id])
                return True
            except Exception as e:
                logger.error(f"Failed to delete document: {e}")
                return False

    async def delete_where(self, where: dict[str, Any]) -> int:
        """
        Delete documents matching a metadata filter.

        Args:
            where: Metadata filter for documents to delete.

        Returns:
            Number of documents deleted.
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            if self._using_fallback:
                to_delete = []
                for doc_id, doc in self._fallback_store.items():
                    if all(doc.metadata.get(k) == v for k, v in where.items()):
                        to_delete.append(doc_id)
                for doc_id in to_delete:
                    del self._fallback_store[doc_id]
                return len(to_delete)

            try:
                # Get matching IDs first
                result = self._collection.get(where=where)
                if result and result["ids"]:
                    self._collection.delete(ids=result["ids"])
                    return len(result["ids"])
                return 0
            except Exception as e:
                logger.error(f"Failed to delete documents: {e}")
                return 0

    async def count(self) -> int:
        """
        Get the total number of documents stored.

        Returns:
            Document count.
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            if self._using_fallback:
                return len(self._fallback_store)

            try:
                return self._collection.count()
            except Exception as e:
                logger.error(f"Failed to count documents: {e}")
                return 0

    async def clear(self) -> int:
        """
        Clear all documents from memory.

        Returns:
            Number of documents that were cleared.
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            if self._using_fallback:
                count = len(self._fallback_store)
                self._fallback_store.clear()
                return count

            try:
                count = self._collection.count()
                # Delete and recreate collection
                self._client.delete_collection(self.collection_name)
                self._collection = self._client.create_collection(
                    name=self.collection_name,
                    embedding_function=self._embedding_function,
                    metadata={"hnsw:space": "cosine"},
                )
                return count
            except Exception as e:
                logger.error(f"Failed to clear memory: {e}")
                return 0

    async def persist(self) -> None:
        """Persist changes to disk."""
        if self._client and hasattr(self._client, "persist"):
            try:
                self._client.persist()
            except Exception as e:
                logger.error(f"Failed to persist memory: {e}")

    async def shutdown(self) -> None:
        """Shutdown long-term memory and persist data."""
        if self._initialized and not self._using_fallback:
            await self.persist()
            self._initialized = False
            logger.info("Long-term memory shutdown complete")

    async def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about long-term memory.

        Returns:
            Dictionary with memory statistics.
        """
        count = await self.count()
        return {
            "initialized": self._initialized,
            "using_fallback": self._using_fallback,
            "collection_name": self.collection_name,
            "persist_directory": self.persist_directory,
            "document_count": count,
            "top_k": self.top_k,
        }
