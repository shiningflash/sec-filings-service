"""Ticker to CIK resolver with caching.

Downloads and caches the SEC ticker->CIK mapping file,
and provides functions to resolve tickers to CIK numbers.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from src.core.logging import get_logger
from src.core.settings import (
    DEFAULT_CACHE_DIR,
    DEFAULT_COMPANY_TICKERS,
    SEC_TICKER_MAP_URL,
    TICKER_CACHE_FILENAME,
)
from src.core.utils import format_cik

if TYPE_CHECKING:
    from src.clients.sec_http import SecHttpClient

logger = get_logger(__name__)


def download_ticker_map(
    client: "SecHttpClient",
    cache_path: Path | None = None,
) -> dict[str, int]:
    """Download and cache the SEC ticker->CIK mapping.

    Fetches the SEC company_tickers.json file which maps tickers to CIKs.
    Caches the result to disk to avoid repeated downloads in the same run.

    Args:
        client: SEC HTTP client for making requests.
        cache_path: Path to cache the mapping file (default: .cache/company_tickers.json).

    Returns:
        Dictionary mapping uppercase ticker symbols to CIK integers.
        Example: {"AAPL": 320193, "META": 1326801, ...}

    Raises:
        Exception: If download fails and no cache exists.
    """
    if cache_path is None:
        cache_path = DEFAULT_CACHE_DIR / TICKER_CACHE_FILENAME

    # Try to load from cache first
    if cache_path.exists():
        logger.debug("Loading ticker map from cache: %s", cache_path)
        try:
            with open(cache_path, encoding="utf-8") as f:
                cached_data = json.load(f)
            logger.info("Loaded %d tickers from cache", len(cached_data))
            return cached_data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load cache, will re-download: %s", e)

    # Download from SEC
    logger.info("Downloading ticker map from SEC...")
    raw_data = client.get_json(SEC_TICKER_MAP_URL)

    # Parse the SEC format: {"0": {"cik_str": "...", "ticker": "...", "title": "..."}, ...}
    ticker_map: dict[str, int] = {}
    for entry in raw_data.values():
        ticker = entry.get("ticker", "").upper()
        cik = entry.get("cik_str")
        if ticker and cik:
            ticker_map[ticker] = int(cik)

    logger.info("Downloaded %d tickers from SEC", len(ticker_map))

    # Cache to disk
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(ticker_map, f)
        logger.debug("Cached ticker map to: %s", cache_path)
    except OSError as e:
        logger.warning("Failed to cache ticker map: %s", e)

    return ticker_map


def resolve_ticker_to_cik(
    ticker: str,
    mapping: dict[str, int],
) -> tuple[int, str]:
    """Resolve a ticker symbol to CIK numbers.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL").
        mapping: Dictionary mapping tickers to CIK integers.

    Returns:
        Tuple of (cik_int, cik10):
        - cik_int: CIK as integer (for Archives path).
        - cik10: CIK as 10-digit zero-padded string (for submissions endpoint).

    Raises:
        ValueError: If ticker is not found in the mapping.

    Example:
        cik_int, cik10 = resolve_ticker_to_cik("AAPL", mapping)
        # cik_int = 320193
        # cik10 = "0000320193"
    """
    ticker_upper = ticker.upper()

    if ticker_upper not in mapping:
        raise ValueError(
            f"Ticker '{ticker}' not found in SEC mapping. "
            "Check spelling or try a different ticker symbol."
        )

    cik_int = mapping[ticker_upper]
    cik_int, cik10 = format_cik(cik_int)

    logger.debug("Resolved %s -> CIK %d (padded: %s)", ticker, cik_int, cik10)

    return cik_int, cik10


def get_ticker_for_company(company_name: str) -> str:
    """Get the ticker symbol for a company name.

    Uses the default company->ticker mapping for the 6 target companies.
    If not found, assumes the input is already a ticker symbol.

    Args:
        company_name: Company name (e.g., "Apple") or ticker (e.g., "AAPL").

    Returns:
        Ticker symbol (uppercase).
    """
    # Check if it's a known company name
    if company_name in DEFAULT_COMPANY_TICKERS:
        return DEFAULT_COMPANY_TICKERS[company_name]

    # Check case-insensitive match
    for name, ticker in DEFAULT_COMPANY_TICKERS.items():
        if name.lower() == company_name.lower():
            return ticker

    # Assume it's already a ticker
    logger.debug("'%s' not in default mapping, treating as ticker", company_name)
    return company_name.upper()


def get_default_companies() -> list[str]:
    """Get the list of default company names.

    Returns:
        List of the 6 target company names.
    """
    return list(DEFAULT_COMPANY_TICKERS.keys())
