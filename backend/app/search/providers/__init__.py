"""Search providers for ScrapeRL backend."""

from app.search.providers.base import BaseSearchProvider
from app.search.providers.google import GoogleSearchProvider
from app.search.providers.bing import BingSearchProvider
from app.search.providers.duckduckgo import DuckDuckGoProvider

__all__ = [
    "BaseSearchProvider",
    "GoogleSearchProvider",
    "BingSearchProvider",
    "DuckDuckGoProvider",
]
