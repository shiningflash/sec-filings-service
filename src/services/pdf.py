"""HTML to PDF conversion using Playwright.

Converts local HTML files to PDF using Playwright Chromium.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

from src.core.logging import get_logger
from src.core.utils import atomic_write_bytes

logger = get_logger(__name__)


class PdfConversionError(Exception):
    """Raised when PDF conversion fails."""

    pass


def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    """Convert a local HTML file to PDF using Playwright Chromium.

    Uses Playwright's print-to-PDF functionality for robust rendering
    of complex HTML documents like SEC filings.

    Args:
        html_path: Path to the local HTML file to convert.
        pdf_path: Path where the PDF should be saved.

    Raises:
        PdfConversionError: If conversion fails.
        FileNotFoundError: If HTML file doesn't exist.
    """
    if not html_path.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    # Convert to file:// URL
    file_url = html_path.resolve().as_uri()
    logger.info("Converting to PDF: %s", html_path.name)
    logger.debug("File URL: %s", file_url)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            # Load the HTML file
            page.goto(file_url, wait_until="load")

            # Generate PDF
            pdf_bytes = page.pdf(
                format="Letter",
                print_background=True,
                margin={
                    "top": "0.5in",
                    "bottom": "0.5in",
                    "left": "0.5in",
                    "right": "0.5in",
                },
            )

            browser.close()

        # Write atomically to avoid partial files
        atomic_write_bytes(pdf_path, pdf_bytes)
        logger.info("PDF saved: %s (%.1f KB)", pdf_path.name, len(pdf_bytes) / 1024)

    except Exception as e:
        raise PdfConversionError(
            f"Failed to convert {html_path.name} to PDF: {e}"
        ) from e
