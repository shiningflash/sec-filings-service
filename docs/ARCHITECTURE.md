# SEC Filings Service Architecture

## Overview

This service fetches the latest SEC EDGAR **10-K** filing for each target company and converts the filing's primary document to **PDF**. It is designed to be small, reliable, and compliant with SEC fair-access guidance (User-Agent, rate limiting, retries).

## High-Level Flow

1. **CIK lookup** — Ticker → CIK via SEC's ticker mapping
2. **Submissions fetch** — `data.sec.gov/submissions/CIK##########.json`
3. **Latest 10-K selection** — Choose newest `filingDate` where `form == "10-K"`
4. **Download** — Fetch primary document from `www.sec.gov/Archives/...`
5. **Fallback** — If primary doc fails, fetch `*-index.html` and locate the main document
6. **Image embedding** — Download images and embed as base64 (SEC blocks headless browsers)
7. **PDF conversion** — Playwright renders the local HTML to PDF
8. **Summary** — Print per-company status + output paths

## Architecture Diagram

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ENTRY POINT                                    │
│                                                                             │
│   src/main.py ──► src/cli.py                                                │
│   - Application entry point      - Parse CLI arguments (--companies, etc.)  │
│   - Calls CLI parser             - Configure logging level                  │
│   - Invokes pipeline             - Initialize SecHttpClient                 │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATION LAYER                                 │
│                                                                             │
│   src/services/pipeline.py                                                  │
│   - run_pipeline(): iterate over companies                                  │
│   - process_company(): CIK → filings → download → PDF → result              │
│   - print_summary(): display final status table                             │
└───────────┬─────────────────┬─────────────────┬─────────────────┬───────────┘
            │                 │                 │                 │
            ▼                 ▼                 ▼                 ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│ services/cik.py   │ │ services/         │ │ services/         │ │ services/pdf.py   │
│                   │ │ filings.py        │ │ download.py       │ │                   │
│ - download_ticker │ │                   │ │                   │ │ - html_to_pdf()   │
│   _map()          │ │ - fetch_latest_   │ │ - download_filing │ │ - Playwright      │
│ - resolve_ticker_ │ │   10k_meta()      │ │   _document()     │ │   Chromium        │
│   to_cik()        │ │ - Parse columnar  │ │ - Fallback to     │ │ - scale=0.9 for   │
│ - get_ticker_for_ │ │   submissions     │ │   index page      │ │   better fit      │
│   company()       │ │   JSON arrays     │ │ - Embed images    │ │ - atomic writes   │
│                   │ │ - Save JSON for   │ │   as base64       │ │                   │
│                   │ │   debugging       │ │ - Rewrite URLs    │ │                   │
└───────────────────┘ └───────────────────┘ └───────────────────┘ └───────────────────┘
            │                 │                 │                 │
            └─────────────────┴─────────────────┴─────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            HTTP CLIENT LAYER                                │
│                                                                             │
│   src/clients/sec_http.py                                                   │
│   - SecHttpClient: single gateway for ALL SEC HTTP requests                 │
│   - User-Agent header (required by SEC)                                     │
│   - Rate limiting (configurable, default 2 req/s)                           │
│   - Timeouts (5s connect, 30s read)                                         │
│   - Retries with Tenacity (exponential backoff for 429/5xx/timeouts)        │
│   - Respects Retry-After header                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CORE LAYER                                     │
│                                                                             │
│   src/core/settings.py     src/core/models.py     src/core/utils.py         │
│   - URL templates          - Company              - ensure_output_dirs()    │
│   - Default tickers        - FilingMeta           - atomic_write_bytes()    │
│   - USER_AGENT             - DownloadResult       - safe_filename()         │
│   - Timeouts/delays        - ConversionResult     - accession_no_dashes()   │
│                            - CompanyResult        - simple_rate_limiter()   │
│                            - Status enum                                    │
│                                                                             │
│   src/core/logging.py                                                       │
│   - setup_logging(): configure log level/format                             │
│   - get_logger(): get module-specific logger                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Module Structure

### Entry Point (`src/`)

| File | Description |
|------|-------------|
| `main.py` | Application entry point; calls CLI and runs pipeline |
| `cli.py` | Argument parsing with argparse; returns config and client |

### Core Layer (`src/core/`)

| File | Description |
|------|-------------|
| `settings.py` | Configuration constants: URLs, default tickers, User-Agent, timeouts |
| `models.py` | Dataclasses: `Company`, `FilingMeta`, `DownloadResult`, `ConversionResult`, `CompanyResult`, `Status` |
| `utils.py` | Pure helpers: `ensure_output_dirs()`, `atomic_write_bytes()`, `safe_filename()`, `accession_no_dashes()`, `simple_rate_limiter()` |
| `logging.py` | Logging setup: `setup_logging()`, `get_logger()` |

### Client Layer (`src/clients/`)

| File | Description |
|------|-------------|
| `sec_http.py` | `SecHttpClient` — single HTTP gateway with User-Agent, rate limiting, timeouts, and Tenacity retries |

### Services Layer (`src/services/`)

| File | Description |
|------|-------------|
| `cik.py` | Ticker → CIK resolution: `download_ticker_map()`, `resolve_ticker_to_cik()`, `get_ticker_for_company()` |
| `filings.py` | Fetch and parse submissions JSON: `fetch_latest_10k_meta()` |
| `download.py` | Download filing documents: `download_filing_document()`, fallback index parsing, URL rewriting, base64 image embedding |
| `pdf.py` | HTML → PDF conversion: `html_to_pdf()` using Playwright Chromium |
| `pipeline.py` | Orchestration: `run_pipeline()`, `process_company()`, `print_summary()` |

## Data Flow

```text
┌──────────────────────────────────────────────────────────────────────────┐
│  INPUT: Company name or ticker (e.g., "Apple" or "AAPL")                 │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  1. TICKER RESOLUTION                                                    │
│     "Apple" → "AAPL"  (via DEFAULT_COMPANY_TICKERS mapping)              │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  2. CIK LOOKUP                                                           │
│     "AAPL" → 320193 (cik_int) / "0000320193" (cik10)                     │
│     Source: https://www.sec.gov/files/company_tickers.json               │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  3. SUBMISSIONS FETCH                                                    │
│     GET https://data.sec.gov/submissions/CIK0000320193.json              │
│     → Parse filings.recent arrays to find latest "10-K"                  │
│     → Extract: accessionNumber, primaryDocument, filingDate              │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  4. DOCUMENT DOWNLOAD                                                    │
│     GET https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}  │
│     → Rewrite relative URLs to absolute                                  │
│     → Download images and embed as base64 data URLs                      │
│     → Save to: output/html/AAPL-2024-11-01-000032019324000123.htm        │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  5. PDF CONVERSION                                                       │
│     Playwright Chromium loads file:// URL                                │
│     → Render with scale=0.9, Letter format                               │
│     → Atomic write to: output/pdf/AAPL-2024-11-01-10-K.pdf               │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  OUTPUT: PDF file + summary status (OK/FAILED)                           │
└──────────────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Image Embedding as Base64

**Problem**: SEC servers block headless browsers from loading images directly, returning 403 Forbidden errors.

**Solution**: During HTML download, we:
1. Parse the HTML for all image sources
2. Download images using our HTTP client (with proper User-Agent)
3. Convert images to base64 data URLs
4. Embed the base64 data directly in the HTML

This ensures images appear in the final PDF without requiring the browser to make additional requests.

### 2. Rate Limiting

SEC requires no more than 10 requests per second. We implement:
- Configurable delay between requests (default: 0.5s = 2 req/s)
- Exponential backoff with Tenacity for transient failures

### 3. Fallback Document Detection

If the primary document listed in filing metadata fails:
1. Download the filing index page
2. Parse for alternative documents (htm, html files)
3. Select the best candidate (prioritizes documents with "10-K" in description)

### 4. Sequential Processing

Companies are processed sequentially (not in parallel) to:
- Respect SEC rate limits
- Simplify error handling
- Avoid overwhelming system resources

## Error Handling

The pipeline isolates failures per company:
- One company failing does **not** stop others
- Final summary includes OK/FAILED status and error messages

Custom exceptions for different failure modes:

| Exception | Description |
|-----------|-------------|
| `CikLookupError` | Failed to resolve ticker to CIK |
| `FilingNotFoundError` | No 10-K filings found for company |
| `DownloadError` | Document download failed |
| `PdfConversionError` | PDF conversion failed |

All errors include context (ticker, CIK, URL) for debugging.

## Configuration

Key settings in `src/core/settings.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_COMPANY_TICKERS` | 6 companies | Apple, Meta, Alphabet, Amazon, Netflix, Goldman Sachs |
| `USER_AGENT` | Email-based | Required by SEC fair access policy |
| `DEFAULT_MAX_PER_SECOND` | 2 req/s | Rate limit for SEC requests |
| `DEFAULT_RETRIES` | 3 | Retry attempts for failed requests |
| `DEFAULT_TIMEOUT` | (5, 30) | Connect and read timeouts in seconds |

## Testing

Tests are organized by module (all mock HTTP — no real SEC calls):

```text
tests/
├── test_cik.py              # CIK lookup and ticker resolution
├── test_filings.py          # 10-K selection logic
├── test_pdf.py              # URL rewriting tests
├── test_urls.py             # URL construction + accession normalization
└── test_fallback_parser.py  # Index page parsing for fallback
```

Run tests: `pytest -v`

## Dependencies

### Runtime
| Package | Purpose |
|---------|---------|
| `requests` | HTTP client for SEC API |
| `tenacity` | Retry logic with exponential backoff |
| `playwright` | Headless Chromium for PDF rendering |

### Development
| Package | Purpose |
|---------|---------|
| `pytest` | Test framework |
| `pytest-cov` | Coverage reporting |
| `ruff` | Linting and formatting |
