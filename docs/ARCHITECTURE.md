# SEC EDGAR 10-K Filings — Service Architecture

## Overview

This service fetches the latest SEC EDGAR **10-K** filing for each target company and converts the filing's primary document to **PDF**. It is designed to be small, reliable, and compliant with SEC fair-access guidance (User-Agent, rate limiting, retries).

## High-Level Flow

```
Input (tickers/names) → CIK Lookup → Submissions Fetch → Latest 10-K Selection
    → Document Download (+ image embedding) → PDF Conversion → Summary Output
```

If the primary document download fails, a **fallback** fetches the filing index page to locate the correct document.

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

## Module Reference

### Entry Point

| File | Responsibility |
|------|----------------|
| `main.py` | Application entry point; calls CLI and runs pipeline |
| `cli.py` | Argument parsing with argparse; returns config and client |

### Core Layer (`src/core/`)

| File | Responsibility |
|------|----------------|
| `settings.py` | Configuration constants: URLs, default tickers, User-Agent, timeouts |
| `models.py` | Dataclasses: `Company`, `FilingMeta`, `DownloadResult`, `ConversionResult`, `CompanyResult`, `Status` |
| `utils.py` | Pure helpers: `ensure_output_dirs()`, `atomic_write_bytes()`, `safe_filename()`, `accession_no_dashes()`, `simple_rate_limiter()` |
| `logging.py` | Logging setup: `setup_logging()`, `get_logger()` |

### Client Layer (`src/clients/`)

| File | Responsibility |
|------|----------------|
| `sec_http.py` | `SecHttpClient` — single HTTP gateway with User-Agent, rate limiting, timeouts, and Tenacity retries |

### Services Layer (`src/services/`)

| File | Responsibility |
|------|----------------|
| `cik.py` | Ticker → CIK resolution with file-based caching |
| `filings.py` | Fetch and parse submissions JSON to find latest 10-K |
| `download.py` | Download filing document with fallback index parsing and base64 image embedding |
| `pdf.py` | HTML → PDF conversion using Playwright Chromium |
| `pipeline.py` | Orchestration: `run_pipeline()`, `process_company()`, `print_summary()` |

## Configuration

Key settings in `src/core/settings.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_COMPANY_TICKERS` | 6 companies | Apple, Meta, Alphabet, Amazon, Netflix, Goldman Sachs |
| `USER_AGENT` | Email-based | Required by SEC; overridable via `SEC_USER_AGENT` env var |
| `DEFAULT_MAX_PER_SECOND` | 2 req/s | Rate limit for SEC requests |
| `DEFAULT_RETRIES` | 3 | Retry attempts for transient failures |
| `DEFAULT_TIMEOUT` | (5, 30) | Connect and read timeouts in seconds |

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| HTTP library | `requests` | Simple, well-known, sufficient for sequential use |
| Retry/backoff | `tenacity` | Flexible decorators, respects `Retry-After` |
| PDF conversion | Playwright Chromium | Most accurate rendering of complex SEC HTML/CSS |
| Image strategy | Base64 embedding | SEC blocks headless browsers; self-contained HTML avoids 403s |
| CLI parser | `argparse` | Built-in, no extra dependency |
| Data models | `dataclasses` | Built-in, lightweight, sufficient for this scope |
| Parallelism | Sequential | SEC rate limits cap benefit; simplicity wins |
| PDF writes | Atomic (temp → rename) | Prevents corrupt partial files on crash |
| Failure model | Per-company isolation | One failure does not stop the pipeline |
