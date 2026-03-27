"""Base search provider interface."""

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """Standard search result format."""

    title: str
    url: str
    snippet: str
    position: int = 0
    source: str = ""
    score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseSearchProvider(ABC):
    """
    Abstract base class for search providers.

    All search providers must implement this interface.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the provider (optional override)."""
        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown the provider (optional override)."""
        self._initialized = False

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[SearchResult]:
        """
        Perform a search query.

        Args:
            query: Search query string
            max_results: Maximum number of results

        Returns:
            List of SearchResult objects
        """
        pass

    @property
    def name(self) -> str:
        """Provider name for identification."""
        return self.__class__.__name__.replace("Provider", "").replace("Search", "")

    @property
    def is_initialized(self) -> bool:
        """Check if provider is initialized."""
        return self._initialized

    def health_check(self) -> bool:
        """Check provider health."""
        return self._initialized
