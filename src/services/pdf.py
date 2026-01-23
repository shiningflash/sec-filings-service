"""HTML to PDF conversion using Playwright.

Converts local HTML files to PDF using Playwright Chromium.
Handles relative URL rewriting for proper image/resource loading.
"""

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.core.logging import get_logger
from src.core.utils import atomic_write_bytes

logger = get_logger(__name__)


class PdfConversionError(Exception):
    """Raised when PDF conversion fails."""

    pass


def html_to_pdf(html_path: Path, pdf_path: Path, base_url: str | None = None) -> None:
    """Convert a local HTML file to PDF using Playwright Chromium.

    Uses Playwright's print-to-PDF functionality for robust rendering
    of complex HTML documents like SEC filings.

    If base_url is provided, relative image/resource URLs in the HTML
    are rewritten to absolute URLs for proper loading.

    Args:
        html_path: Path to the local HTML file to convert.
        pdf_path: Path where the PDF should be saved.
        base_url: Base URL for resolving relative paths (e.g., SEC Archives URL).

    Raises:
        PdfConversionError: If conversion fails.
        FileNotFoundError: If HTML file doesn't exist.
    """
    if not html_path.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    logger.info("Converting to PDF: %s", html_path.name)

    try:
        # Read HTML content
        html_content = html_path.read_text(encoding="utf-8", errors="replace")

        # Rewrite relative URLs if base_url provided
        if base_url:
            html_content = _rewrite_relative_urls(html_content, base_url)
            logger.debug("Rewrote relative URLs with base: %s", base_url)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            # Load HTML content directly (allows URL rewriting to work)
            page.set_content(html_content, wait_until="load")

            # Generate PDF with minimal settings - let the browser handle layout
            # The HTML already has its own styling, so we avoid forcing margins/format
            pdf_bytes = page.pdf(
                print_background=True,
                prefer_css_page_size=True,  # Respect CSS @page rules if present
            )

            browser.close()

        # Write atomically to avoid partial files
        atomic_write_bytes(pdf_path, pdf_bytes)
        logger.info("PDF saved: %s (%.1f KB)", pdf_path.name, len(pdf_bytes) / 1024)

    except Exception as e:
        raise PdfConversionError(f"Failed to convert {html_path.name} to PDF: {e}") from e


def _rewrite_relative_urls(html: str, base_url: str) -> str:
    """Rewrite relative URLs in HTML to absolute URLs.

    Handles src and href attributes that have relative paths.
    Preserves absolute URLs, data URLs, and anchors.

    Args:
        html: HTML content.
        base_url: Base URL to prepend to relative paths.

    Returns:
        HTML with rewritten URLs.
    """
    # Ensure base_url ends with /
    if not base_url.endswith("/"):
        base_url = base_url + "/"

    def replace_url(match: re.Match) -> str:
        """Replace relative URL with absolute URL."""
        attr = match.group(1)  # src or href
        quote = match.group(2)  # ' or "
        url = match.group(3)

        # Skip if already absolute, data URL, anchor, or javascript
        if url.startswith(("http://", "https://", "data:", "#", "javascript:", "//")) or not url:
            return match.group(0)

        # Build absolute URL
        absolute_url = base_url + url
        return f"{attr}={quote}{absolute_url}{quote}"

    # Pattern to match src="..." or href="..." (both single and double quotes)
    pattern = r'(src|href)=(["\'])([^"\'>]+)\2'
    return re.sub(pattern, replace_url, html, flags=re.IGNORECASE)
