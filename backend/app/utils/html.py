"""HTML processing utilities for ScrapeRL backend."""

import re
from typing import Any, Optional
from bs4 import BeautifulSoup, Tag, NavigableString

from app.utils.logging import get_logger

logger = get_logger(__name__)


def parse_html(html: str, parser: str = "html.parser") -> BeautifulSoup:
    """
    Parse HTML string into a BeautifulSoup object.

    Args:
        html: Raw HTML string
        parser: Parser to use (html.parser, lxml, html5lib)

    Returns:
        Parsed BeautifulSoup object
    """
    return BeautifulSoup(html, parser)


def clean_html(
    html: str,
    remove_scripts: bool = True,
    remove_styles: bool = True,
    remove_comments: bool = True,
    remove_tags: Optional[list[str]] = None,
) -> str:
    """
    Clean HTML by removing unwanted elements.

    Args:
        html: Raw HTML string
        remove_scripts: Remove <script> tags
        remove_styles: Remove <style> tags
        remove_comments: Remove HTML comments
        remove_tags: Additional tags to remove

    Returns:
        Cleaned HTML string
    """
    soup = parse_html(html)

    # Remove script tags
    if remove_scripts:
        for script in soup.find_all("script"):
            script.decompose()

    # Remove style tags
    if remove_styles:
        for style in soup.find_all("style"):
            style.decompose()

    # Remove comments
    if remove_comments:
        from bs4 import Comment

        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

    # Remove additional specified tags
    if remove_tags:
        for tag_name in remove_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()

    return str(soup)


def extract_text(
    html: str,
    separator: str = " ",
    strip: bool = True,
) -> str:
    """
    Extract plain text from HTML.

    Args:
        html: Raw HTML string
        separator: String to join text segments
        strip: Strip whitespace from result

    Returns:
        Extracted plain text
    """
    soup = parse_html(html)

    # Remove script and style elements
    for element in soup(["script", "style", "noscript"]):
        element.decompose()

    text = soup.get_text(separator=separator)

    if strip:
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

    return text


def semantic_chunk(
    html: str,
    max_chunk_size: int = 4000,
    overlap: int = 200,
) -> list[dict[str, Any]]:
    """
    Split HTML content into semantic chunks based on structure.

    Args:
        html: Raw HTML string
        max_chunk_size: Maximum characters per chunk
        overlap: Number of characters to overlap between chunks

    Returns:
        List of chunk dictionaries with text and metadata
    """
    soup = parse_html(html)
    chunks: list[dict[str, Any]] = []

    # Remove non-content elements
    for element in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        element.decompose()

    # Find semantic boundaries
    semantic_tags = ["article", "section", "div", "p", "h1", "h2", "h3", "h4", "h5", "h6"]

    def get_text_content(element: Tag | NavigableString) -> str:
        if isinstance(element, NavigableString):
            return str(element).strip()
        return element.get_text(separator=" ", strip=True)

    current_chunk = ""
    current_metadata: dict[str, Any] = {"tags": [], "headings": []}

    for element in soup.find_all(semantic_tags):
        text = get_text_content(element)
        if not text:
            continue

        tag_name = element.name if isinstance(element, Tag) else "text"

        # Check if adding this would exceed max size
        if len(current_chunk) + len(text) + 1 > max_chunk_size:
            if current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "metadata": current_metadata.copy(),
                    "char_count": len(current_chunk),
                })
            # Start new chunk with overlap
            if overlap > 0 and current_chunk:
                current_chunk = current_chunk[-overlap:] + " " + text
            else:
                current_chunk = text
            current_metadata = {"tags": [tag_name], "headings": []}
        else:
            current_chunk += " " + text if current_chunk else text
            current_metadata["tags"].append(tag_name)

        # Track headings
        if tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            current_metadata["headings"].append(text[:100])

    # Add remaining content
    if current_chunk.strip():
        chunks.append({
            "text": current_chunk.strip(),
            "metadata": current_metadata,
            "char_count": len(current_chunk),
        })

    # If no semantic chunks found, fall back to simple chunking
    if not chunks:
        text = extract_text(html)
        for i in range(0, len(text), max_chunk_size - overlap):
            chunk_text = text[i : i + max_chunk_size]
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text.strip(),
                    "metadata": {"tags": [], "headings": []},
                    "char_count": len(chunk_text),
                })

    return chunks


def extract_links(
    html: str,
    base_url: Optional[str] = None,
    include_text: bool = True,
) -> list[dict[str, str]]:
    """
    Extract all links from HTML.

    Args:
        html: Raw HTML string
        base_url: Base URL for resolving relative links
        include_text: Include link text in results

    Returns:
        List of link dictionaries with href and optionally text
    """
    from urllib.parse import urljoin

    soup = parse_html(html)
    links: list[dict[str, str]] = []

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        # Resolve relative URLs
        if base_url and not href.startswith(("http://", "https://", "//")):
            href = urljoin(base_url, href)

        link_data: dict[str, str] = {"href": href}

        if include_text:
            link_data["text"] = anchor.get_text(strip=True)

        # Include title if present
        title = anchor.get("title")
        if title:
            link_data["title"] = title

        links.append(link_data)

    return links


def extract_tables(
    html: str,
    include_headers: bool = True,
) -> list[dict[str, Any]]:
    """
    Extract tables from HTML as structured data.

    Args:
        html: Raw HTML string
        include_headers: Try to identify and include header rows

    Returns:
        List of table dictionaries with headers and rows
    """
    soup = parse_html(html)
    tables: list[dict[str, Any]] = []

    for table in soup.find_all("table"):
        table_data: dict[str, Any] = {
            "headers": [],
            "rows": [],
        }

        # Extract headers from thead or first row
        if include_headers:
            thead = table.find("thead")
            if thead:
                header_row = thead.find("tr")
                if header_row:
                    table_data["headers"] = [
                        th.get_text(strip=True)
                        for th in header_row.find_all(["th", "td"])
                    ]

        # Extract body rows
        tbody = table.find("tbody") or table
        for row in tbody.find_all("tr"):
            cells = row.find_all(["td", "th"])
            row_data = [cell.get_text(strip=True) for cell in cells]

            # If no headers yet and this looks like a header row
            if include_headers and not table_data["headers"] and row.find("th"):
                table_data["headers"] = row_data
            else:
                if row_data:  # Skip empty rows
                    table_data["rows"].append(row_data)

        if table_data["rows"] or table_data["headers"]:
            tables.append(table_data)

    return tables
