"""Download primary filing document with fallback support.

Downloads 10-K filing documents from SEC EDGAR Archives.
Implements fallback to index page parsing if primary document fails.
"""

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING

from src.core.logging import get_logger
from src.core.models import FilingMeta
from src.core.settings import SEC_ARCHIVES_URL
from src.core.utils import accession_no_dashes, atomic_write_bytes, safe_filename

if TYPE_CHECKING:
    from src.clients.sec_http import SecHttpClient

logger = get_logger(__name__)


class DownloadError(Exception):
    """Raised when document download fails."""

    pass


def download_filing_document(
    client: "SecHttpClient",
    cik_int: int,
    meta: FilingMeta,
    ticker: str,
    out_html_dir: Path,
) -> Path:
    """Download the filing document and save to output directory.

    Attempts to download the primary document first. If that fails or
    the primary document is missing, falls back to parsing the index
    page to find an alternative document.

    Args:
        client: SEC HTTP client for making requests.
        cik_int: CIK as integer (for Archives URL).
        meta: Filing metadata with accession number and primary document.
        ticker: Company ticker (for filename and logging).
        out_html_dir: Directory to save the downloaded file.

    Returns:
        Path to the saved document file.

    Raises:
        DownloadError: If download fails even after fallback attempt.
    """
    accession_nd = accession_no_dashes(meta.accession_number)

    # Try primary document first
    if meta.primary_document:
        try:
            return _download_document(
                client=client,
                cik_int=cik_int,
                accession_no_dashes=accession_nd,
                document=meta.primary_document,
                ticker=ticker,
                filing_date=meta.filing_date,
                out_html_dir=out_html_dir,
            )
        except Exception as e:
            logger.warning(
                "[%s] Primary document download failed: %s. Trying fallback...",
                ticker,
                e,
            )

    # Fallback: parse index page to find the main document
    logger.info("[%s] Using fallback: parsing index page", ticker)
    fallback_doc = _find_document_from_index(
        client=client,
        cik_int=cik_int,
        accession_no_dashes=accession_nd,
        accession_number=meta.accession_number,
        ticker=ticker,
    )

    if not fallback_doc:
        raise DownloadError(
            f"Could not find 10-K document for {ticker} (accession={meta.accession_number})"
        )

    return _download_document(
        client=client,
        cik_int=cik_int,
        accession_no_dashes=accession_nd,
        document=fallback_doc,
        ticker=ticker,
        filing_date=meta.filing_date,
        out_html_dir=out_html_dir,
    )


def _download_document(
    client: "SecHttpClient",
    cik_int: int,
    accession_no_dashes: str,
    document: str,
    ticker: str,
    filing_date: str,
    out_html_dir: Path,
) -> Path:
    """Download a specific document from SEC Archives.

    Args:
        client: SEC HTTP client.
        cik_int: CIK as integer.
        accession_no_dashes: Accession number without dashes.
        document: Document filename to download.
        ticker: Company ticker.
        filing_date: Filing date for filename.
        out_html_dir: Output directory.

    Returns:
        Path to saved file.
    """
    url = SEC_ARCHIVES_URL.format(
        cik_int=cik_int,
        accession_no_dashes=accession_no_dashes,
        document=document,
    )

    logger.info("[%s] Downloading document: %s", ticker, document)
    logger.debug("URL: %s", url)

    content = client.get_bytes(url)

    # Determine extension from document name
    ext = Path(document).suffix or ".html"

    # Build output filename: {ticker}_{filingDate}_{accession}{ext}
    filename = safe_filename(ticker, filing_date, accession_no_dashes, extension=ext)
    out_path = out_html_dir / filename

    atomic_write_bytes(out_path, content)
    logger.info("[%s] Saved document to %s (%.1f KB)", ticker, out_path, len(content) / 1024)

    return out_path


def _find_document_from_index(
    client: "SecHttpClient",
    cik_int: int,
    accession_no_dashes: str,
    accession_number: str,
    ticker: str,
) -> str | None:
    """Parse the filing index page to find the main 10-K document.

    The index page lists all documents in the filing. We look for
    the most likely 10-K HTML document.

    Args:
        client: SEC HTTP client.
        cik_int: CIK as integer.
        accession_no_dashes: Accession number without dashes.
        accession_number: Original accession number (for index filename).
        ticker: Company ticker (for logging).

    Returns:
        Document filename if found, None otherwise.
    """
    # Index page URL: {accessionNumber}-index.html
    index_doc = f"{accession_number}-index.html"
    url = SEC_ARCHIVES_URL.format(
        cik_int=cik_int,
        accession_no_dashes=accession_no_dashes,
        document=index_doc,
    )

    logger.debug("[%s] Fetching index page: %s", ticker, url)

    try:
        html = client.get_text(url)
    except Exception as e:
        logger.error("[%s] Failed to fetch index page: %s", ticker, e)
        return None

    # Parse HTML to find document links
    return _parse_index_for_10k_document(html, ticker)


def _parse_index_for_10k_document(html: str, ticker: str) -> str | None:
    """Parse index HTML to find the main 10-K document link.

    Looks for table rows with document links. Prioritizes:
    1. Documents with "10-K" in description and .htm/.html extension
    2. Documents with common 10-K filename patterns

    Args:
        html: Raw HTML content of index page.
        ticker: Company ticker (for logging).

    Returns:
        Document filename if found, None otherwise.
    """
    parser = _IndexPageParser()
    try:
        parser.feed(html)
    except Exception as e:
        logger.warning("[%s] HTML parsing error: %s", ticker, e)

    # Filter for HTML documents
    html_docs = [
        (href, desc)
        for href, desc in parser.links
        if href.endswith((".htm", ".html")) and not href.endswith("-index.html")
    ]

    if not html_docs:
        logger.warning("[%s] No HTML documents found in index", ticker)
        return None

    # Priority 1: Look for document with "10-K" in description
    for href, desc in html_docs:
        if "10-K" in desc.upper() or "10K" in desc.upper():
            logger.debug("[%s] Found 10-K document by description: %s", ticker, href)
            return href

    # Priority 2: Look for common 10-K filename patterns
    patterns = [
        r".*10-?k.*\.htm",  # Contains "10k" or "10-k"
        r".*_10k.*\.htm",
        r".*-10k.*\.htm",
    ]
    for href, _ in html_docs:
        href_lower = href.lower()
        for pattern in patterns:
            if re.match(pattern, href_lower):
                logger.debug("[%s] Found 10-K document by filename pattern: %s", ticker, href)
                return href

    # Priority 3: Take the first/largest HTML document (often the main filing)
    # Index pages typically list the main document first
    if html_docs:
        href = html_docs[0][0]
        logger.debug("[%s] Using first HTML document as fallback: %s", ticker, href)
        return href

    return None


class _IndexPageParser(HTMLParser):
    """Simple HTML parser to extract document links from index page.

    Extracts href and text from <a> tags within the document table.
    """

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self._in_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href and not href.startswith(("http://", "https://", "#", "javascript:")):
                self._current_href = href
                self._current_text = []
                self._in_link = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_link:
            if self._current_href:
                text = " ".join(self._current_text).strip()
                self.links.append((self._current_href, text))
            self._current_href = None
            self._current_text = []
            self._in_link = False

    def handle_data(self, data: str) -> None:
        if self._in_link:
            self._current_text.append(data)
