# SEC EDGAR 10-K Fetch + PDF Conversion

A Python CLI tool that fetches the latest SEC EDGAR **10-K** filing for each company, downloads the primary filing document, and converts it to **PDF**.

## What it does

1. Resolves company tickers to **CIK** using SEC’s ticker mapping.
2. Fetches **submissions** metadata from `data.sec.gov`.
3. Selects the **latest 10-K** filing for each company.
4. Downloads the primary filing document (HTML/HTM/TXT).
5. (Optional but enabled) Improves PDF fidelity by embedding external assets as data URLs when needed.
6. Converts the document to PDF using **Playwright (Chromium)**
7. Provides a summary of results for all processed companies

## Default companies

- Apple (AAPL)
- Meta (META)
- Alphabet (GOOGL)
- Amazon (AMZN)
- Netflix (NFLX)
- Goldman Sachs (GS)

## Prerequisites

- Python 3.12+
- `uv` (recommended) or `pip`
- Playwright Chromium (installed via `playwright install chromium`)

## Quick Start

```bash
# Clone and enter directory
git clone <repo-url>
cd sec-filings-service

# Create virtual environment
uv venv --python 3.12

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Install Playwright Chromium browser
playwright install chromium

# Run the tool
python -m src.main
```

## Usage

`--companies` accepts either **company names** or **tickers** (comma-separated).

```bash
# Run with default companies (Apple, Meta, Alphabet, Amazon, Netflix, Goldman Sachs)
python -m src.main

# Run with specific companies
python -m src.main --companies "Apple,Meta,Amazon"

# Run with tickers directly
python -m src.main --companies "AAPL,TSLA,MSFT"

# Specify output directory
python -m src.main --out my_output

# Adjust rate limiting (requests per second)
python -m src.main --max-per-second 2

# Set retry count for failed requests
python -m src.main --retries 3

# Enable debug logging
python -m src.main --debug
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SEC_USER_AGENT` | User-Agent header for SEC requests | `Amirul Islam (amirulislamalmamun@gmail.com)` |

## Output

```
output/
├── pdf/    # Final PDF files: {ticker}_{filingDate}_10-K.pdf
├── html/   # Downloaded HTML files: {ticker}_{filingDate}_{accession}.html
└── json/   # Submissions JSON for debugging: {ticker}_submissions.json
```

## Development

### Install Development Dependencies

```bash
# Install all dependencies (core + dev)
uv pip install -r requirements-dev.txt

# Or install only runtime dependencies
uv pip install -r requirements.txt
```

### Linting & Formatting

```bash
# Check for linting issues
ruff check .

# Format code
ruff format .
```

### Running Tests

```bash
# Run all tests
pytest
```

## Project Structure

```
src/
├── main.py              # Entry point
├── cli.py               # CLI argument parsing
├── core/
│   ├── models.py        # Data models (Company, FilingMeta, etc.)
│   ├── settings.py      # Configuration constants
│   ├── logging.py       # Logging setup
│   └── utils.py         # Helper functions
├── clients/
│   └── sec_http.py      # SEC HTTP client with retry/rate limiting
└── services/
    ├── cik.py           # Ticker to CIK resolution
    ├── filings.py       # Fetch and parse 10-K metadata
    ├── download.py      # Download filing documents
    ├── pdf.py           # HTML to PDF conversion
    └── pipeline.py      # Orchestration
```

## Design Decisions

- **Playwright for PDF conversion**: Chosen for robust HTML rendering of complex SEC filings
- **Base64 image embedding**: SEC blocks headless browsers from loading images directly; we embed images as base64 data URLs during HTML download
- **Sequential processing**: Respects SEC rate limits (default: 2 req/s)
- **Tenacity for retries**: Handles transient failures with exponential backoff
- **Fallback strategy**: If primary document fails, parses the filing index page to locate the main document
- **Atomic writes**: Prevents partial/corrupt files on interruption

## Documentation

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## SEC Compliance

This tool follows [SEC EDGAR access policies](https://www.sec.gov/os/accessing-edgar-data):

- Descriptive **User-Agent** header with contact email
- Rate limiting (**configurable**, default: 2 requests/second)
- Timeouts on all HTTP requests (5s connect, 30s read)
- Retry with exponential backoff for 429/5xx errors
- Respects Retry-After headers

## License

See [LICENSE](LICENSE) file.
