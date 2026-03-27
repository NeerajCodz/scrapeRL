"""Search module for ScrapeRL backend."""

from app.search.engine import SearchEngineRouter
from app.search.providers import (
    BaseSearchProvider,
    GoogleSearchProvider,
    BingSearchProvider,
    DuckDuckGoProvider,
)

__all__ = [
    "SearchEngineRouter",
    "BaseSearchProvider",
    "GoogleSearchProvider",
    "BingSearchProvider",
    "DuckDuckGoProvider",
]
