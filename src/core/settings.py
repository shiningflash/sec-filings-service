"""Constants, defaults, and configuration settings.

Centralized configuration for SEC EDGAR 10-K fetcher.
Environment variables can override defaults where noted.
"""

import os
from pathlib import Path

# =============================================================================
# User-Agent (required by SEC - include contact email)
# Can be overridden via SEC_USER_AGENT environment variable
# =============================================================================
DEFAULT_USER_AGENT = "Amirul Islam (amirulislamalmamun@gmail.com)"
USER_AGENT = os.getenv("SEC_USER_AGENT", DEFAULT_USER_AGENT)

# =============================================================================
# SEC EDGAR URLs
# =============================================================================
SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
SEC_ARCHIVES_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{document}"
)

# =============================================================================
# Default HTTP settings
# =============================================================================
DEFAULT_MAX_PER_SECOND = 2.0
DEFAULT_RETRIES = 3
DEFAULT_TIMEOUT = (5.0, 30.0)  # (connect_timeout, read_timeout)

# =============================================================================
# Paths
# =============================================================================
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_CACHE_DIR = Path(".cache")
TICKER_CACHE_FILENAME = "company_tickers.json"

# =============================================================================
# Target companies (name -> ticker mapping)
# =============================================================================
DEFAULT_COMPANY_TICKERS: dict[str, str] = {
    "Apple": "AAPL",
    "Meta": "META",
    "Alphabet": "GOOGL",
    "Amazon": "AMZN",
    "Netflix": "NFLX",
    "Goldman Sachs": "GS",
}
