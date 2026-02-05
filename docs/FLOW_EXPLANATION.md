# SEC EDGAR 10-K FILINGS - Step-by-Step Flow Explanation

> "This is a Python CLI tool that fetches the latest 10-K annual filings from the SEC EDGAR database for specified companies and converts them to PDF format. It handles the entire pipeline: resolving company tickers to SEC CIK identifiers, fetching filing metadata, downloading the primary document, embedding images for offline rendering, and converting to PDF using Playwright's Chromium browser."

#### Step 1: Input Parsing (`cli.py`)

```
User Input: "Apple,Meta,AAPL,TSLA"
     ↓
argparse parses --companies flag
     ↓
Output: List of strings ["Apple", "Meta", "AAPL", "TSLA"]
```

**What happens:**
- The CLI accepts company names OR tickers (flexible input)
- Configures logging level, output directory, rate limiting parameters
- Creates the `SecHttpClient` with User-Agent and retry settings

**Why this design:**
- Single entry point keeps the interface simple
- Configuration is centralized before any processing begins
- The HTTP client is created once and reused (connection pooling)

---

#### Step 2: Company Name → Ticker Resolution (`cik.py`)

```
"Apple" → "AAPL"
"Goldman Sachs" → "GS"
"AAPL" → "AAPL" (already a ticker, passthrough)
```

**What happens:**
- A hardcoded mapping (`DEFAULT_COMPANY_TICKERS` in `settings.py`) maps known company names to tickers
- If the input is already a valid ticker (e.g., "AAPL"), it passes through unchanged
- Unknown names are treated as tickers (allows flexibility)

**Why this design:**
- Assignment specified 6 default companies—a simple dict is sufficient
- No need for fuzzy matching or external API for company name resolution
- Keeps the code minimal and predictable

**Alternative considered:**
- Could use a fuzzy matching library (e.g., `fuzzywuzzy`) for company names
- Could call an external API for company lookup
- **Rejected because:** Over-engineering for the requirement; adds complexity and potential failure points

---

#### Step 3: Ticker → CIK Resolution (`cik.py`)

```
"AAPL" → (cik_int=320193, cik10="0000320193")
```

**What happens:**
1. Download SEC's `company_tickers.json` (cached to avoid repeated downloads)
2. Parse JSON to build ticker→CIK mapping
3. Return two CIK formats:
   - `cik_int`: Integer (e.g., `320193`) - used in Archives URL path
   - `cik10`: Zero-padded 10-digit string (e.g., `"0000320193"`) - required for submissions endpoint

**Why two CIK formats:**
- SEC submissions endpoint requires: `CIK0000320193.json` (10-digit padded)
- SEC Archives path uses: `/edgar/data/320193/` (no padding)
- This is a real SEC API quirk that must be handled correctly

**Caching strategy:**
- In-memory cache during the run (ticker_map dict)
- File-based cache (`.cache/company_tickers.json`) to avoid re-downloading
- Cache expiry: Currently no TTL, could add 24-hour expiry

---

#### Step 4: Fetch Submissions & Find Latest 10-K (`filings.py`)

```
GET https://data.sec.gov/submissions/CIK0000320193.json
     ↓
Parse JSON → Find form=="10-K" with latest filingDate
     ↓
Extract: accessionNumber, primaryDocument, filingDate
```

**What happens:**
1. Fetch the submissions JSON for the company
2. The JSON has a columnar structure: `filings.recent.form[]`, `filings.recent.accessionNumber[]`, etc.
3. Find the index where `form[i] == "10-K"` with the newest `filingDate[i]`
4. Extract metadata at that index

**Critical implementation detail - Columnar Array Alignment:**
```python
# The arrays are aligned by index!
forms = data["filings"]["recent"]["form"]           # ["10-K", "8-K", "10-Q", ...]
accessions = data["filings"]["recent"]["accessionNumber"]  # ["0000320193-24-000081", ...]
dates = data["filings"]["recent"]["filingDate"]     # ["2024-11-01", "2024-10-15", ...]

# To find the latest 10-K:
for i, form in enumerate(forms):
    if form == "10-K":
        # forms[i], accessions[i], dates[i] all refer to the SAME filing
```

**Why save submissions JSON (`output/json/`):**
- Debugging: Can inspect what SEC returned without re-fetching
- Traceability: Verify which filing was selected
- Offline analysis: Examine filing history

---

#### Step 5: Download Primary Document (`download.py`)

```
Build URL: https://www.sec.gov/Archives/edgar/data/320193/000032019324000081/aapl-20240928.htm
     ↓
Download HTML content
     ↓
Parse HTML, find <img> tags
     ↓
Download each image, convert to base64, embed inline
     ↓
Save modified HTML to output/html/
```

**Accession Number Transformation:**
```
Original:    "0000320193-24-000081"
No dashes:   "000032019324000081"   ← Used in URL path
```

**Why embed images as base64:**
- SEC blocks image requests from headless browsers (anti-scraping)
- Playwright rendering would show broken images
- Embedding base64 makes the HTML self-contained and renders correctly

**Fallback Strategy (if primary document fails):**
1. Fetch `{accessionNumber}-index.html` (filing index page)
2. Parse HTML to find links to the main 10-K document
3. Download the discovered document instead

---

#### Step 6: Convert to PDF (`pdf.py`)

```
Local HTML file: output/html/AAPL_2024-11-01_000032019324000081.htm
     ↓
Playwright loads file:///path/to/file.htm
     ↓
page.pdf() generates PDF
     ↓
Atomic write: temp file → rename to final path
```

**Why Playwright over alternatives:**

| Approach | Pros | Cons |
|----------|------|------|
| **Playwright (chosen)** | Full browser rendering, handles CSS/JS, most accurate | Requires Chromium install (~300MB) |
| WeasyPrint | Pure Python, no browser needed | Limited CSS support, struggles with complex layouts |
| wkhtmltopdf | Fast, good CSS support | Requires system install, deprecated |
| pdfkit | Wrapper around wkhtmltopdf | Same limitations |

**Why atomic writes:**
```python
# Write to temp file first, then rename
temp_path = pdf_path.with_suffix(".tmp")
page.pdf(path=str(temp_path), ...)
temp_path.rename(pdf_path)  # Atomic on same filesystem
```
- If the process crashes mid-write, we don't have a corrupt partial PDF
- The final file either exists completely or doesn't exist at all

---

#### Step 7: Summary & Exit (`pipeline.py`)

```
================================================================================
SUMMARY
================================================================================
Company         Ticker   CIK          Filing Date  Status   PDF/Error
--------------------------------------------------------------------------------
Apple           AAPL     320193       2024-11-01   OK       output/pdf/AAPL_2024-11-01_10-K.pdf
Meta            META     1326801      2024-02-02   OK       output/pdf/META_2024-02-02_10-K.pdf
--------------------------------------------------------------------------------
Total: 2 | OK: 2 | FAILED: 0
================================================================================
```

**Exit codes:**
- `0`: At least one PDF succeeded
- `1`: All companies failed

**Why this exit code strategy:**
- Common Unix convention: 0 = success, non-zero = failure
- Partial success (some PDFs generated) is still useful, so exit 0
- Allows scripting: `python -m src.main && echo "At least one worked"`

---

### Key Design Decisions Summary

| Decision | Choice | Why | Alternatives Rejected |
|----------|--------|-----|----------------------|
| HTTP library | `requests` | Simple, well-known, sufficient | `httpx` (async not needed), `aiohttp` (overkill) |
| Retry library | `tenacity` | Flexible, decorators, well-maintained | Manual retry loops (error-prone), `backoff` (less features) |
| PDF conversion | Playwright | Accurate rendering of complex HTML | WeasyPrint (poor CSS), wkhtmltopdf (deprecated) |
| CLI parser | `argparse` | Built-in, sufficient | `click` (extra dependency), `typer` (overkill) |
| Data models | `dataclasses` | Built-in, simple | `pydantic` (heavier, validation not critical here) |
| Parallelism | Sequential | SEC rate limits make parallel inefficient | `asyncio` (adds complexity, minimal benefit) |

---

## Key Implementation Details

### SEC API Compliance (Critical!)

**User-Agent Header (Required by SEC):**
```python
# settings.py
USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "Amirul Islam (amirulislamalmamun@gmail.com)"
)

# sec_http.py - Applied to ALL requests
self._session.headers.update({"User-Agent": self.user_agent})
```

Why this matters:
- SEC will block requests without proper User-Agent
- Must include contact email per SEC fair access policy
- Environment variable allows override without code changes

**Rate Limiting:**
```python
# Default: 2 requests per second
def simple_rate_limiter(max_per_second: float):
    min_interval = 1.0 / max_per_second
    last_call = [0.0]
    
    def limiter():
        elapsed = time.time() - last_call[0]
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        last_call[0] = time.time()
    
    return limiter
```

Why a simple limiter vs token bucket:
- For sequential processing, a simple sleep-based limiter is sufficient
- Token bucket would be useful for burst handling in async scenarios
- Keeps code simple and predictable

**Retry Strategy:**
```python
@retry(
    stop=stop_after_attempt(4),  # 1 initial + 3 retries
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type((RetryableHttpError, ConnectionError, Timeout)),
    reraise=True,
)
```

What gets retried:
- HTTP 429 (Too Many Requests)
- HTTP 5xx (Server Errors)
- Connection errors
- Timeouts

What doesn't get retried:
- HTTP 4xx (except 429) - Client errors indicate a bug, not transient failure
- JSON parse errors - Data issue, not network issue

**Retry-After Header:**
```python
if response.status_code == 429:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        time.sleep(float(retry_after))
```

---

## Demo Checklist

- [ ] Clean run: `python -m src.main` generates PDFs for all 6 companies
- [ ] Custom companies: `python -m src.main --companies "TSLA,MSFT"`
- [ ] Show output directories: `ls output/pdf/ output/html/ output/json/`
- [ ] Open a generated PDF and HTML to show they match
- [ ] Show the summary table output
- [ ] Run tests: `pytest -v`
- [ ] Run linter: `ruff check .`
- [ ] Explain the logs as they appear
- [ ] Show error handling: try an invalid ticker to demonstrate graceful failure

---

## Quick Reference Card

### Key URLs

```
Ticker → CIK mapping:  https://www.sec.gov/files/company_tickers.json
Submissions:           https://data.sec.gov/submissions/CIK{cik10}.json
Archives:              https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{document}
Filing index:          https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{accession}-index.html
```

### CIK Formats

```
cik10 = "0000320193"  → Used in: CIK0000320193.json (submissions)
cik_int = 320193      → Used in: /edgar/data/320193/ (archives)
```

### Accession Number

```
Original:   "0000320193-24-000081"
No dashes:  "000032019324000081"  → Used in archive paths
```

### Exit Codes

```
0 = At least one PDF succeeded
1 = All companies failed
```

END
