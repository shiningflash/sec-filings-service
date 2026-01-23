"""Submissions fetch and latest 10-K selection.

Fetches company submissions from SEC EDGAR and extracts
the latest 10-K filing metadata.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.core.logging import get_logger
from src.core.models import FilingMeta
from src.core.settings import SEC_SUBMISSIONS_URL
from src.core.utils import atomic_write_text

if TYPE_CHECKING:
    from src.clients.sec_http import SecHttpClient

logger = get_logger(__name__)


class No10KFoundError(Exception):
    """Raised when no 10-K filing is found for a company."""

    pass


def fetch_latest_10k_meta(
    client: "SecHttpClient",
    cik10: str,
    cik_int: int,
    ticker: str,
    out_json_dir: Path | None = None,
) -> FilingMeta:
    """Fetch the latest 10-K filing metadata for a company.

    Calls the SEC submissions endpoint and parses the filings to find
    the most recent 10-K filing by filing date.

    Args:
        client: SEC HTTP client for making requests.
        cik10: 10-digit zero-padded CIK (for submissions URL).
        cik_int: CIK as integer (for reference, not used in URL).
        ticker: Company ticker symbol (for logging and JSON filename).
        out_json_dir: Directory to save submissions JSON (optional).
                      If provided, saves to {out_json_dir}/{ticker}_submissions.json.

    Returns:
        FilingMeta with the latest 10-K filing details.

    Raises:
        No10KFoundError: If no 10-K filing is found in submissions.
        Exception: If HTTP request fails.
    """
    url = SEC_SUBMISSIONS_URL.format(cik10=cik10)
    logger.info("[%s] Fetching submissions from SEC", ticker)
    logger.debug("URL: %s", url)

    submissions = client.get_json(url)

    # Optionally save submissions JSON for debugging
    if out_json_dir is not None:
        json_path = out_json_dir / f"{ticker}_submissions.json"
        atomic_write_text(json_path, json.dumps(submissions, indent=2))
        logger.debug("Saved submissions JSON to %s", json_path)

    # Parse and find latest 10-K
    filing_meta = _parse_latest_10k(submissions, ticker)

    logger.info(
        "[%s] Found 10-K: accession=%s, date=%s",
        ticker,
        filing_meta.accession_number,
        filing_meta.filing_date,
    )

    return filing_meta


def _parse_latest_10k(submissions: dict[str, Any], ticker: str) -> FilingMeta:
    """Parse submissions JSON and find the latest 10-K filing.

    The submissions JSON has columnar arrays under filings.recent:
    - form[], accessionNumber[], primaryDocument[], filingDate[], reportDate[]
    All arrays are aligned by index.

    Args:
        submissions: Raw submissions JSON from SEC.
        ticker: Company ticker (for error messages).

    Returns:
        FilingMeta for the latest 10-K filing.

    Raises:
        No10KFoundError: If no 10-K filing is found.
    """
    filings = submissions.get("filings", {})
    recent = filings.get("recent", {})

    # Get the columnar arrays
    forms = recent.get("form", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_documents = recent.get("primaryDocument", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])

    if not forms:
        raise No10KFoundError(f"No filings found for {ticker}")

    # Find all 10-K filings and their indices
    ten_k_indices: list[int] = []
    for i, form in enumerate(forms):
        if form == "10-K":
            ten_k_indices.append(i)

    if not ten_k_indices:
        raise No10KFoundError(f"No 10-K filing found for {ticker}")

    # Find the latest 10-K by filing date (ISO format sorts lexicographically)
    latest_idx = max(
        ten_k_indices, key=lambda i: filing_dates[i] if i < len(filing_dates) else ""
    )

    # Extract filing metadata (with defensive checks)
    accession = _safe_get(accession_numbers, latest_idx, "")
    primary_doc = _safe_get(primary_documents, latest_idx, "")
    filing_date = _safe_get(filing_dates, latest_idx, "")
    report_date = _safe_get(report_dates, latest_idx, None)

    if not accession or not filing_date:
        raise No10KFoundError(
            f"10-K found for {ticker} but missing required fields "
            f"(accession={accession}, filingDate={filing_date})"
        )

    # Primary document might be missing in rare cases
    if not primary_doc:
        logger.warning("[%s] 10-K has no primaryDocument field", ticker)

    return FilingMeta(
        accession_number=accession,
        primary_document=primary_doc,
        filing_date=filing_date,
        report_date=report_date if report_date else None,
        form_type="10-K",
    )


def _safe_get(arr: list, idx: int, default: Any) -> Any:
    """Safely get an element from a list by index.

    Args:
        arr: List to get element from.
        idx: Index to retrieve.
        default: Value to return if index is out of bounds.

    Returns:
        Element at index or default value.
    """
    if idx < len(arr):
        return arr[idx]
    return default
