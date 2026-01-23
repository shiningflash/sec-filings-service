# SEC Filings Service Architecture

## Overview

The SEC Filings Service is a Python application that fetches SEC 10-K filings for specified companies and converts them to PDF format. It handles the complexity of the SEC EDGAR API, including rate limiting, retry logic, and image embedding.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLI (main.py)                              │
│                                                                      │
│  - Parse arguments (output dir, companies, request delay)            │
│  - Initialize SecHttpClient                                          │
│  - Process companies sequentially                                    │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Pipeline Service                                │
│                    (services/pipeline.py)                            │
│                                                                      │
│  Orchestrates the full workflow for each company:                    │
│  1. CIK lookup                                                       │
│  2. Filings search                                                   │
│  3. Document download                                                │
│  4. PDF conversion                                                   │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   CIK Lookup    │ │  Filings API    │ │  Download       │
│ (services/cik)  │ │ (services/      │ │ (services/      │
│                 │ │  filings)       │ │  download)      │
│ - Ticker → CIK  │ │                 │ │                 │
│ - Validation    │ │ - Search 10-K   │ │ - Fetch HTML    │
│                 │ │ - Get metadata  │ │ - Embed images  │
└─────────────────┘ └─────────────────┘ │ - Rewrite URLs  │
                                        └────────┬────────┘
                                                 │
                                                 ▼
                                        ┌─────────────────┐
                                        │  PDF Service    │
                                        │ (services/pdf)  │
                                        │                 │
                                        │ - Playwright    │
                                        │ - Chrome render │
                                        │ - PDF output    │
                                        └─────────────────┘
```

## Module Structure

### Core Layer (`src/core/`)

- **config.py**: Configuration constants (target companies, user agent, URLs)
- **models.py**: Data classes for results (`FilingMeta`, `DownloadResult`, `ProcessingResult`)
- **exceptions.py**: Custom exception classes (`SecApiError`, `CikLookupError`, etc.)
- **urls.py**: URL builders for SEC EDGAR API endpoints
- **http.py**: `SecHttpClient` - HTTP client with rate limiting and retry logic

### Services Layer (`src/services/`)

- **cik.py**: Convert ticker symbols to CIK numbers
- **filings.py**: Search for and retrieve filing metadata
- **download.py**: Download filing documents with image embedding
- **pdf.py**: Convert HTML to PDF using Playwright
- **pipeline.py**: Orchestrate the full processing workflow

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
3. Select the largest document (typically the main filing)

### 4. Sequential Processing

Companies are processed sequentially (not in parallel) to:
- Respect SEC rate limits
- Simplify error handling
- Avoid overwhelming system resources

## Data Flow

```
1. INPUT: Ticker symbol (e.g., "AAPL")
           │
           ▼
2. CIK LOOKUP: AAPL → 0000320193
           │
           ▼
3. FILINGS SEARCH: Query SEC API for 10-K filings
           │
           ▼
4. DOWNLOAD: Fetch HTML, embed images as base64
           │
           ▼
5. CONVERT: Playwright renders HTML → PDF
           │
           ▼
6. OUTPUT: /output/pdf/AAPL-2024-10-31-10-K.pdf
```

## Configuration

Key configuration in `src/core/settings.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `TARGET_TICKERS` | 6 companies | Apple, Meta, Alphabet, Amazon, Netflix, Goldman Sachs |
| `USER_AGENT` | Email-based | Required by SEC fair access policy |
| `DEFAULT_REQUEST_DELAY` | 0.5s | Delay between requests |
| `DEFAULT_MAX_RETRIES` | 3 | Retry attempts for failed requests |

## Error Handling

The application uses custom exceptions for different failure modes:

- `SecApiError`: Base class for all SEC API errors
- `CikLookupError`: Failed to resolve ticker to CIK
- `FilingNotFoundError`: No filings match criteria
- `DownloadError`: Document download failed
- `PdfConversionError`: PDF conversion failed

All errors include context (ticker, CIK, URL) for debugging.

## Testing

Tests are organized by module:

```
tests/
├── test_cik.py          # CIK lookup tests
├── test_filings.py      # Filing search tests
├── test_pdf.py          # URL rewriting tests
├── test_urls.py         # URL builder tests
└── test_fallback_parser.py  # Fallback document detection tests
```

Run tests with: `pytest -v`

## Dependencies

### Runtime
- `requests`: HTTP client for SEC API
- `tenacity`: Retry logic with exponential backoff
- `playwright`: Headless Chrome for PDF rendering

### Development
- `pytest`: Test framework
- `pytest-cov`: Coverage reporting
- `ruff`: Linting and formatting
