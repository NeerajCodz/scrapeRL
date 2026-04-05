"""Site template registry for domain-aware scraping behavior."""

from app.sites.models import SiteTemplate
from app.sites.registry import (
    get_site_template,
    list_site_templates,
    match_site_template,
    serialize_site_template,
)

__all__ = [
    "SiteTemplate",
    "get_site_template",
    "list_site_templates",
    "match_site_template",
    "serialize_site_template",
]
