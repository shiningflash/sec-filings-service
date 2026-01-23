# SEC EDGAR 10-K Fetch + PDF Conversion

A Python tool that fetches the latest SEC 10-K filings for specified companies via EDGAR APIs, downloads the primary filing documents, and converts them to PDF.

## What it does

- Resolves company tickers to CIK numbers using SEC's ticker mapping
- Fetches the latest 10-K filing metadata from SEC EDGAR
- Downloads the primary filing document (HTML/HTM)
- Converts the filing to PDF using Playwright (Chromium)
- Provides a summary of results for all processed companies

## Target Companies (Default)

- Apple (AAPL)
- Meta (META)
- Alphabet (GOOGL)
- Amazon (AMZN)
- Netflix (NFLX)
- Goldman Sachs (GS)

## Prerequisites

- Python 3.12
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Installation & Setup

```bash
# Create virtual environment with Python 3.12
uv venv --python 3.12

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Install Playwright Chromium browser
playwright install chromium
```

## Usage

```bash
# Run with default companies
python -m src.main

# Run with specific companies
python -m src.main --companies "Apple,Meta,Amazon"

# Specify output directory
python -m src.main --out output

# Adjust rate limiting (requests per second)
python -m src.main --max-per-second 2

# Set retry count
python -m src.main --retries 3
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SEC_USER_AGENT` | User-Agent header for SEC requests | `Amirul Islam (amirulislamalmamun@gmail.com)` |

## Output

PDFs are saved to:
- `output/pdf/{ticker}_{filingDate}_10-K.pdf`

Downloaded HTML files are saved to:
- `output/html/{ticker}_{filingDate}_{accession}.html`

Submissions JSON (for debugging) saved to:
- `output/json/{ticker}_submissions.json`

## Development

### Linting & Formatting

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Running Tests

```bash
pytest -q
```

## Design Decisions

- **Playwright for PDF conversion**: Chosen for robust HTML rendering and reliable PDF output
- **Sequential processing**: Respects SEC rate limits and avoids overwhelming the API
- **Tenacity for retries**: Handles transient failures with exponential backoff
- **Fallback strategy**: If primary document download fails, parses the filing index page to locate the main document

## SEC Compliance

This tool follows SEC EDGAR access policies:
- Descriptive User-Agent header with contact email
- Rate limiting (default: 2 requests/second)
- Timeouts on all HTTP requests
- Retry with exponential backoff for 429/5xx errors
- Respects Retry-After headers

## License

See [LICENSE](LICENSE) file.
