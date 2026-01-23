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
    # Utils
    "accession_no_dashes",
    "atomic_write_bytes",
    "atomic_write_text",
    "ensure_output_dirs",
    "format_cik",
    "safe_filename",
    "simple_rate_limiter",
]
