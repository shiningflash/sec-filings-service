"""Data models and result types for SEC EDGAR 10-K fetcher."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Status(Enum):
    """Processing status for a company."""

    OK = "OK"
    FAILED = "FAILED"


@dataclass
class Company:
    """Represents a company to process.

    Attributes:
        name: Human-readable company name (e.g., "Apple").
        ticker: Stock ticker symbol (e.g., "AAPL").
        cik_int: CIK as integer without leading zeros (for Archives path).
        cik10: CIK as 10-digit zero-padded string (for submissions endpoint).
    """

    name: str
    ticker: str
    cik_int: Optional[int] = None
    cik10: Optional[str] = None


@dataclass
class FilingMeta:
    """Metadata for a 10-K filing.

    Attributes:
        accession_number: SEC accession number (e.g., "0000320193-23-000106").
        primary_document: Filename of the primary document (e.g., "aapl-20230930.htm").
        filing_date: Date the filing was submitted (ISO format, e.g., "2023-11-03").
        report_date: Fiscal period end date if available (e.g., "2023-09-30").
        form_type: Form type (should be "10-K").
    """

    accession_number: str
    primary_document: str
    filing_date: str
    report_date: Optional[str] = None
    form_type: str = "10-K"


@dataclass
class DownloadResult:
    """Result of downloading a filing document.

    Attributes:
        success: Whether the download succeeded.
        html_path: Path to the downloaded HTML file (if successful).
        error: Error message (if failed).
        used_fallback: Whether the fallback index page method was used.
    """

    success: bool
    html_path: Optional[str] = None
    error: Optional[str] = None
    used_fallback: bool = False


@dataclass
class ConversionResult:
    """Result of converting HTML to PDF.

    Attributes:
        success: Whether the conversion succeeded.
        pdf_path: Path to the generated PDF file (if successful).
        error: Error message (if failed).
    """

    success: bool
    pdf_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class CompanyResult:
    """Complete processing result for a single company.

    Used for the final summary output.

    Attributes:
        company: The company that was processed.
        status: Overall status (OK or FAILED).
        filing_meta: Metadata about the 10-K filing (if found).
        download_result: Result of the download step.
        conversion_result: Result of the PDF conversion step.
        error: High-level error message if processing failed early.
    """

    company: Company
    status: Status = Status.FAILED
    filing_meta: Optional[FilingMeta] = None
    download_result: Optional[DownloadResult] = None
    conversion_result: Optional[ConversionResult] = None
    error: Optional[str] = None

    @property
    def pdf_path(self) -> Optional[str]:
        """Get the PDF path if conversion was successful."""
        if self.conversion_result and self.conversion_result.success:
            return self.conversion_result.pdf_path
        return None

    @property
    def error_message(self) -> Optional[str]:
        """Get the most relevant error message."""
        if self.error:
            return self.error
        if self.conversion_result and self.conversion_result.error:
            return self.conversion_result.error
        if self.download_result and self.download_result.error:
            return self.download_result.error
        return None
