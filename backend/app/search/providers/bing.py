"""Bing Search provider (stub implementation)."""

from typing import Optional

from app.search.providers.base import BaseSearchProvider, SearchResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BingSearchProvider(BaseSearchProvider):
    """
    Bing Search provider using Bing Web Search API.

    This is a stub implementation. To use Bing Search API:
    1. Get API key from Azure Portal (Bing Search resource)
    2. Set the BING_API_KEY environment variable

    Environment variables:
        BING_API_KEY: Bing Search API key
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        super().__init__(api_key)
        self._base_url = "https://api.bing.microsoft.com/v7.0/search"

    async def initialize(self) -> None:
        """Initialize the Bing Search provider."""
        logger.info("Initializing BingSearchProvider")

        if not self.api_key:
            logger.warning("Bing API key not configured - stub mode enabled")

        self._initialized = True
        logger.info("BingSearchProvider initialized")

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[SearchResult]:
        """
        Search using Bing Web Search API.

        Args:
            query: Search query string
            max_results: Maximum number of results

        Returns:
            List of SearchResult objects
        """
        logger.info(f"Bing search: {query}")

        if not self.api_key:
            logger.warning("Bing Search not configured, returning stub results")
            return self._get_stub_results(query, max_results)

        # Real implementation would look like:
        # import httpx
        # async with httpx.AsyncClient() as client:
        #     headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        #     params = {
        #         "q": query,
        #         "count": max_results,
        #         "responseFilter": "Webpages",
        #     }
        #     response = await client.get(
        #         self._base_url,
        #         headers=headers,
        #         params=params,
        #     )
        #     data = response.json()
        #
        #     results = []
        #     web_pages = data.get("webPages", {}).get("value", [])
        #     for i, item in enumerate(web_pages):
        #         results.append(SearchResult(
        #             title=item.get("name", ""),
        #             url=item.get("url", ""),
        #             snippet=item.get("snippet", ""),
        #             position=i + 1,
        #             source="bing",
        #         ))
        #     return results

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
                    title=f"Bing Result {i + 1}: {query}",
                    url=f"https://example.com/bing/{i + 1}",
                    snippet=f"This is a stub Bing search result for '{query}'. "
                    f"Configure BING_API_KEY for real results.",
                    position=i + 1,
                    source="bing",
                    metadata={"stub": True},
                )
            )
        return results
