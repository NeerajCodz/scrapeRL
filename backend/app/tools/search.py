"""Search tool wrapper for search engine providers."""

from typing import Any, Optional
from dataclasses import dataclass

from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Individual search result."""

    title: str
    url: str
    snippet: str
    position: int
    source: str  # Provider name
    metadata: dict[str, Any] | None = None


@dataclass
class SearchResponse:
    """Response from a search query."""

    query: str
    results: list[SearchResult]
    total_results: int
    provider: str
    success: bool
    error: Optional[str] = None


class SearchTool:
    """
    Search tool that wraps search engine providers.

    Provides a unified interface for searching across different
    search engine providers.
    """

    def __init__(self, default_provider: str = "duckduckgo") -> None:
        self.default_provider = default_provider
        self._engine: Any = None
        self._initialized: bool = False

    async def initialize(self, engine: Any = None) -> None:
        """
        Initialize the search tool with a search engine.

        Args:
            engine: SearchEngineRouter instance to use
        """
        logger.info("Initializing SearchTool")
        self._engine = engine
        self._initialized = True
        logger.info("SearchTool initialized")

    async def shutdown(self) -> None:
        """Shutdown the search tool."""
        logger.info("Shutting down SearchTool")
        self._engine = None
        self._initialized = False

    async def search(
        self,
        query: str,
        max_results: int = 10,
        provider: Optional[str] = None,
    ) -> SearchResponse:
        """
        Perform a search query.

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            provider: Specific provider to use (optional)

        Returns:
            SearchResponse with results
        """
        logger.info(f"Searching for: {query}")

        provider_name = provider or self.default_provider

        if not self._initialized or self._engine is None:
            logger.warning("SearchTool not properly initialized, using stub response")
            return SearchResponse(
                query=query,
                results=[],
                total_results=0,
                provider=provider_name,
                success=False,
                error="Search engine not initialized",
            )

        try:
            # Delegate to search engine router
            results = await self._engine.search(
                query=query,
                max_results=max_results,
                provider=provider_name,
            )

            return SearchResponse(
                query=query,
                results=results,
                total_results=len(results),
                provider=provider_name,
                success=True,
            )

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return SearchResponse(
                query=query,
                results=[],
                total_results=0,
                provider=provider_name,
                success=False,
                error=str(e),
            )

    async def get_results(
        self,
        query: str,
        max_results: int = 10,
        provider: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Get search results as a list.

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            provider: Specific provider to use (optional)

        Returns:
            List of SearchResult objects
        """
        response = await self.search(query, max_results, provider)
        return response.results

    def health_check(self) -> bool:
        """Check if the search tool is healthy."""
        return self._initialized and self._engine is not None

    @property
    def is_initialized(self) -> bool:
        """Check if the search tool has been initialized."""
        return self._initialized
