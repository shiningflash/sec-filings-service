"""Orchestrator - runs the full pipeline for each company.

Processes companies independently: CIK lookup -> fetch metadata ->
download document -> convert to PDF.
"""

from pathlib import Path

from src.clients.sec_http import SecHttpClient
from src.core.logging import get_logger
from src.core.models import (
    Company,
    CompanyResult,
    ConversionResult,
    DownloadResult,
    Status,
)
from src.core.utils import ensure_output_dirs, safe_filename
from src.services.cik import (
    download_ticker_map,
    get_ticker_for_company,
    resolve_ticker_to_cik,
)
from src.services.download import download_filing_document
from src.services.filings import fetch_latest_10k_meta
from src.services.pdf import html_to_pdf

logger = get_logger(__name__)


def process_company(
    company_name: str,
    client: SecHttpClient,
    ticker_map: dict[str, int],
    output_dirs: dict[str, Path],
) -> CompanyResult:
    """Process a single company through the full pipeline.

    Steps:
    1. Resolve company name to ticker
    2. Resolve ticker to CIK
    3. Fetch latest 10-K metadata
    4. Download filing document (with fallback)
    5. Convert to PDF

    Args:
        company_name: Company name or ticker to process.
        client: SEC HTTP client.
        ticker_map: Ticker to CIK mapping.
        output_dirs: Dictionary of output directory paths.

    Returns:
        CompanyResult with status and details.
    """
    ticker = get_ticker_for_company(company_name)
    company = Company(name=company_name, ticker=ticker)

    logger.info("[%s] Starting processing", ticker)

    try:
        # Step 1: Resolve CIK
        cik_int, cik10 = resolve_ticker_to_cik(ticker, ticker_map)
        company.cik_int = cik_int
        company.cik10 = cik10
        logger.debug("[%s] CIK: %d (padded: %s)", ticker, cik_int, cik10)

        # Step 2: Fetch latest 10-K metadata
        meta = fetch_latest_10k_meta(
            client=client,
            cik10=cik10,
            cik_int=cik_int,
            ticker=ticker,
            out_json_dir=output_dirs["json"],
        )

        # Step 3: Download filing document
        html_path = download_filing_document(
            client=client,
            cik_int=cik_int,
            meta=meta,
            ticker=ticker,
            out_html_dir=output_dirs["html"],
        )
        download_result = DownloadResult(success=True, html_path=str(html_path))

        # Step 4: Convert to PDF
        pdf_filename = safe_filename(ticker, meta.filing_date, "10-K", extension=".pdf")
        pdf_path = output_dirs["pdf"] / pdf_filename

        html_to_pdf(html_path, pdf_path)
        conversion_result = ConversionResult(success=True, pdf_path=str(pdf_path))

        logger.info("[%s] Completed successfully", ticker)

        return CompanyResult(
            company=company,
            status=Status.OK,
            filing_meta=meta,
            download_result=download_result,
            conversion_result=conversion_result,
        )

    except Exception as e:
        logger.error("[%s] Failed: %s", ticker, e)
        return CompanyResult(
            company=company,
            status=Status.FAILED,
            error=str(e),
        )


def run_pipeline(
    companies: list[str],
    client: SecHttpClient,
    output_dir: str,
) -> list[CompanyResult]:
    """Run the full pipeline for all companies.

    Args:
        companies: List of company names or tickers.
        client: SEC HTTP client.
        output_dir: Base output directory.

    Returns:
        List of CompanyResult for each company.
    """
    # Ensure output directories exist
    output_dirs = ensure_output_dirs(output_dir)

    # Download ticker map (cached)
    logger.info("Loading ticker map...")
    ticker_map = download_ticker_map(client)

    # Process each company
    results: list[CompanyResult] = []
    total = len(companies)

    for i, company_name in enumerate(companies, 1):
        print(f"\n[{i}/{total}] Processing {company_name}...")
        result = process_company(company_name, client, ticker_map, output_dirs)
        results.append(result)

    return results


def print_summary(results: list[CompanyResult]) -> None:
    """Print a summary table of results to stdout.

    Args:
        results: List of CompanyResult from pipeline run.
    """
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # Header
    print(
        f"{'Company':<15} {'Ticker':<8} {'CIK':<12} {'Filing Date':<12} {'Status':<8} {'PDF/Error'}"
    )
    print("-" * 80)

    for r in results:
        company = r.company
        cik = str(company.cik_int) if company.cik_int else "N/A"
        filing_date = r.filing_meta.filing_date if r.filing_meta else "N/A"
        status = r.status.value

        if r.status == Status.OK:
            detail = r.pdf_path or ""
        else:
            detail = r.error_message or "Unknown error"
            # Truncate long error messages
            if len(detail) > 40:
                detail = detail[:37] + "..."

        print(
            f"{company.name:<15} {company.ticker:<8} {cik:<12} {filing_date:<12} {status:<8} {detail}"
        )

    # Summary counts
    ok_count = sum(1 for r in results if r.status == Status.OK)
    failed_count = len(results) - ok_count
    print("-" * 80)
    print(f"Total: {len(results)} | OK: {ok_count} | FAILED: {failed_count}")
    print("=" * 80)
