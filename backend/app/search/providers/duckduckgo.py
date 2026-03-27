"""DuckDuckGo Search provider using duckduckgo-search library."""

from typing import Optional

from app.search.providers.base import BaseSearchProvider, SearchResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DuckDuckGoProvider(BaseSearchProvider):
    """
    DuckDuckGo Search provider using the duckduckgo-search library.

    This provider works without an API key.

    Requirements:
        pip install duckduckgo-search
    """

    def __init__(self) -> None:
        super().__init__(api_key=None)
        self._ddgs: Optional[object] = None

    async def initialize(self) -> None:
        """Initialize the DuckDuckGo Search provider."""
        logger.info("Initializing DuckDuckGoProvider")

        try:
            from duckduckgo_search import DDGS

            self._ddgs = DDGS()
            self._initialized = True
            logger.info("DuckDuckGoProvider initialized with duckduckgo-search")
        except ImportError:
            logger.warning(
                "duckduckgo-search not installed. "
                "Install with: pip install duckduckgo-search"
            )
            self._initialized = True  # Still mark as initialized for stub mode
            logger.info("DuckDuckGoProvider initialized in stub mode")

    async def shutdown(self) -> None:
        """Shutdown the DuckDuckGo provider."""
        self._ddgs = None
        self._initialized = False
        logger.info("DuckDuckGoProvider shut down")

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[SearchResult]:
        """
        Search using DuckDuckGo.

        Args:
            query: Search query string
            max_results: Maximum number of results

        Returns:
            List of SearchResult objects
        """
        logger.info(f"DuckDuckGo search: {query}")

        if self._ddgs is None:
            logger.warning("DuckDuckGo not available, returning stub results")
            return self._get_stub_results(query, max_results)

        try:
            # duckduckgo-search is synchronous, run in executor for async
            import asyncio

            loop = asyncio.get_event_loop()
            raw_results = await loop.run_in_executor(
                None,
                lambda: list(self._ddgs.text(query, max_results=max_results)),  # type: ignore
            )

            results = []
            for i, item in enumerate(raw_results):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("href", item.get("link", "")),
                        snippet=item.get("body", item.get("snippet", "")),
                        position=i + 1,
                        source="duckduckgo",
                        metadata={
                            "raw": item,
                        },
                    )
                )

            logger.info(f"DuckDuckGo returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return self._get_stub_results(query, max_results)

    def _get_stub_results(
        self,
        query: str,
        max_results: int,
    ) -> list[SearchResult]:
        """Generate stub results for testing."""
        results = []
        for i in range(min(max_results, 3)):
            results.append(
                SearchResult(
                    title=f"DuckDuckGo Result {i + 1}: {query}",
                    url=f"https://example.com/ddg/{i + 1}",
                    snippet=f"This is a stub DuckDuckGo search result for '{query}'. "
                    f"Install duckduckgo-search for real results.",
                    position=i + 1,
                    source="duckduckgo",
                    metadata={"stub": True},
                )
            )
        return results

    @property
    def is_available(self) -> bool:
        """Check if DuckDuckGo search is available."""
        return self._ddgs is not None
