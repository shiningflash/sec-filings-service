"""Business logic services module."""

from src.services.cik import (
    DEFAULT_COMPANY_TICKERS,
    download_ticker_map,
    get_default_companies,
    get_ticker_for_company,
    resolve_ticker_to_cik,
)
from src.services.download import DownloadError, download_filing_document
from src.services.filings import No10KFoundError, fetch_latest_10k_meta
from src.services.pdf import PdfConversionError, html_to_pdf
from src.services.pipeline import print_summary, process_company, run_pipeline

__all__ = [
    # CIK resolution
    "DEFAULT_COMPANY_TICKERS",
    "download_ticker_map",
    "get_default_companies",
    "get_ticker_for_company",
    "resolve_ticker_to_cik",
    # Filings
    "No10KFoundError",
    "fetch_latest_10k_meta",
    # Download
    "DownloadError",
    "download_filing_document",
    # PDF
    "PdfConversionError",
    "html_to_pdf",
    # Pipeline
    "print_summary",
    "process_company",
    "run_pipeline",
]
