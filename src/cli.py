"""CLI argument parsing and configuration building."""

import argparse
from dataclasses import dataclass

from src.core.settings import (
    DEFAULT_COMPANY_TICKERS,
    DEFAULT_MAX_PER_SECOND,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RETRIES,
)


@dataclass
class CliConfig:
    """Configuration from CLI arguments."""

    companies: list[str]
    output_dir: str
    max_per_second: float
    retries: int
    debug: bool


def parse_args(args: list[str] | None = None) -> CliConfig:
    """Parse command-line arguments.

    Args:
        args: Arguments to parse (defaults to sys.argv).

    Returns:
        CliConfig with parsed values.
    """
    parser = argparse.ArgumentParser(
        prog="sec-filings",
        description="Fetch SEC 10-K filings and convert to PDF.",
    )

    parser.add_argument(
        "--companies",
        type=str,
        default=None,
        help=(
            "Comma-separated list of company names or tickers. "
            f"Default: {', '.join(DEFAULT_COMPANY_TICKERS.keys())}"
        ),
    )

    parser.add_argument(
        "--out",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )

    parser.add_argument(
        "--max-per-second",
        type=float,
        default=DEFAULT_MAX_PER_SECOND,
        help=f"Max requests per second (default: {DEFAULT_MAX_PER_SECOND})",
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Number of retries for failed requests (default: {DEFAULT_RETRIES})",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    parsed = parser.parse_args(args)

    # Parse companies list
    if parsed.companies:
        companies = [c.strip() for c in parsed.companies.split(",") if c.strip()]
    else:
        companies = list(DEFAULT_COMPANY_TICKERS.keys())

    return CliConfig(
        companies=companies,
        output_dir=parsed.out,
        max_per_second=parsed.max_per_second,
        retries=parsed.retries,
        debug=parsed.debug,
    )
