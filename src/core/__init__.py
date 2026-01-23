"""Core module - models, settings, utilities, and logging."""

from src.core.logging import get_logger, set_level, setup_logging
from src.core.models import (
    Company,
    CompanyResult,
    ConversionResult,
    DownloadResult,
    FilingMeta,
    Status,
)
from src.core.settings import (
    DEFAULT_COMPANY_TICKERS,
    DEFAULT_MAX_PER_SECOND,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    SEC_ARCHIVES_URL,
    SEC_SUBMISSIONS_URL,
    SEC_TICKER_MAP_URL,
    USER_AGENT,
)
from src.core.utils import (
    accession_no_dashes,
    atomic_write_bytes,
    atomic_write_text,
    ensure_output_dirs,
    format_cik,
    safe_filename,
    simple_rate_limiter,
)

__all__ = [
    # Logging
    "get_logger",
    "set_level",
    "setup_logging",
    # Models
    "Company",
    "CompanyResult",
    "ConversionResult",
    "DownloadResult",
    "FilingMeta",
    "Status",
    # Settings
    "DEFAULT_COMPANY_TICKERS",
    "DEFAULT_MAX_PER_SECOND",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_RETRIES",
    "DEFAULT_TIMEOUT",
    "SEC_ARCHIVES_URL",
    "SEC_SUBMISSIONS_URL",
    "SEC_TICKER_MAP_URL",
    "USER_AGENT",
    # Utils
    "accession_no_dashes",
    "atomic_write_bytes",
    "atomic_write_text",
    "ensure_output_dirs",
    "format_cik",
    "safe_filename",
    "simple_rate_limiter",
]
