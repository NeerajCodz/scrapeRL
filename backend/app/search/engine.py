"""Search engine router for aggregating multiple search providers."""

from typing import Any, Optional
from dataclasses import dataclass, field

from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Individual search result."""

    title: str
    url: str
    snippet: str
    position: int
    source: str
    score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class SearchEngineRouter:
    """
    Routes search queries to different providers and aggregates results.

    Supports multiple search providers and can aggregate/rank results
    from multiple sources.
    """

    def __init__(self) -> None:
        self._providers: dict[str, Any] = {}
        self._default_provider: Optional[str] = None
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the search engine router and all providers."""
        logger.info("Initializing SearchEngineRouter")

        # Initialize all registered providers
        for name, provider in self._providers.items():
            try:
                if hasattr(provider, "initialize"):
                    await provider.initialize()
                logger.info(f"Initialized provider: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize provider {name}: {e}")

        self._initialized = True
        logger.info("SearchEngineRouter initialized")

    async def shutdown(self) -> None:
        """Shutdown the router and all providers."""
        logger.info("Shutting down SearchEngineRouter")

        for name, provider in self._providers.items():
            try:
                if hasattr(provider, "shutdown"):
                    await provider.shutdown()
                logger.info(f"Shut down provider: {name}")
            except Exception as e:
                logger.error(f"Error shutting down provider {name}: {e}")

        self._initialized = False

    def register_provider(
        self,
        name: str,
        provider: Any,
        set_default: bool = False,
    ) -> None:
        """
        Register a search provider.

        Args:
            name: Provider identifier
            provider: Provider instance
            set_default: Set as the default provider
        """
        self._providers[name] = provider
        logger.info(f"Registered search provider: {name}")

        if set_default or self._default_provider is None:
            self._default_provider = name
            logger.info(f"Set default provider: {name}")

    def unregister_provider(self, name: str) -> bool:
        """
        Unregister a search provider.

        Args:
            name: Provider identifier

        Returns:
            True if provider was removed
        """
        if name in self._providers:
            del self._providers[name]
            if self._default_provider == name:
                self._default_provider = next(iter(self._providers), None)
            logger.info(f"Unregistered provider: {name}")
            return True
        return False

    def get_providers(self) -> list[str]:
        """
        Get list of registered provider names.

        Returns:
            List of provider identifiers
        """
        return list(self._providers.keys())

    def get_provider(self, name: str) -> Optional[Any]:
        """
        Get a specific provider by name.

        Args:
            name: Provider identifier

        Returns:
            Provider instance or None
        """
        return self._providers.get(name)

    async def search(
        self,
        query: str,
        max_results: int = 10,
        provider: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Perform a search using a specific provider.

        Args:
            query: Search query string
            max_results: Maximum results to return
            provider: Provider to use (defaults to default provider)

        Returns:
            List of search results

        Raises:
            ValueError: If provider not found
        """
        provider_name = provider or self._default_provider

        if provider_name is None:
            raise ValueError("No search provider configured")

        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' not found")

        provider_instance = self._providers[provider_name]
        logger.info(f"Searching with provider '{provider_name}': {query}")

        try:
            results = await provider_instance.search(query, max_results)

            # Ensure results have proper source attribution
            for i, result in enumerate(results):
                if isinstance(result, dict):
                    result["source"] = provider_name
                    result["position"] = i + 1
                elif hasattr(result, "source"):
                    result.source = provider_name
                    result.position = i + 1

            return results

        except Exception as e:
            logger.error(f"Search failed with provider '{provider_name}': {e}")
            raise

    async def search_all(
        self,
        query: str,
        max_results_per_provider: int = 10,
        providers: Optional[list[str]] = None,
    ) -> list[SearchResult]:
        """
        Search across multiple providers and aggregate results.

        Args:
            query: Search query string
            max_results_per_provider: Max results from each provider
            providers: Specific providers to use (defaults to all)

        Returns:
            Aggregated and ranked list of results
        """
        provider_names = providers or list(self._providers.keys())
        all_results: list[SearchResult] = []

        for provider_name in provider_names:
            try:
                results = await self.search(
                    query=query,
                    max_results=max_results_per_provider,
                    provider=provider_name,
                )
                all_results.extend(results)
            except Exception as e:
                logger.warning(f"Provider '{provider_name}' failed: {e}")
                continue

        # Rank and deduplicate results
        ranked_results = self._rank_results(all_results)

        return ranked_results

    def _rank_results(
        self,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """
        Rank and deduplicate search results.

        Args:
            results: Raw results from multiple providers

        Returns:
            Ranked and deduplicated results
        """
        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique_results: list[SearchResult] = []

        for result in results:
            url = result.url if hasattr(result, "url") else result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)

        # Sort by score (higher is better) then by position (lower is better)
        def sort_key(r: Any) -> tuple[float, int]:
            score = r.score if hasattr(r, "score") else r.get("score", 1.0)
            position = r.position if hasattr(r, "position") else r.get("position", 999)
            return (-score, position)

        unique_results.sort(key=sort_key)

        # Update positions
        for i, result in enumerate(unique_results):
            if hasattr(result, "position"):
                result.position = i + 1
            elif isinstance(result, dict):
                result["position"] = i + 1

        return unique_results

    @property
    def is_initialized(self) -> bool:
        """Check if the router is initialized."""
        return self._initialized

    @property
    def default_provider(self) -> Optional[str]:
        """Get the default provider name."""
        return self._default_provider
