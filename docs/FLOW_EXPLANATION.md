# SEC EDGAR 10-K Filings — Step-by-Step Flow & Design Rationale

> A Python CLI tool that fetches the latest 10-K annual filings from the SEC EDGAR database for specified companies and converts them to PDF format.

For the architecture diagram and module reference, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Pipeline Walkthrough

### Step 1: Input Parsing (`cli.py`)

```
User runs: python -m src.main --companies "Apple,Meta,AAPL,TSLA"
     ↓
argparse parses --companies flag
     ↓
Output: ["Apple", "Meta", "AAPL", "TSLA"]
```

- Accepts company names OR tickers (flexible input).
- Configures logging, output directory, rate limiting, and retry count.
- Creates a single `SecHttpClient` instance (reused for all requests via connection pooling).

---

### Step 2: Company Name → Ticker Resolution (`cik.py`)

```
"Apple" → "AAPL"       (via DEFAULT_COMPANY_TICKERS mapping)
"Goldman Sachs" → "GS"
"AAPL" → "AAPL"        (already a ticker — passthrough)
```

A hardcoded dict maps the 6 assignment companies to tickers. Unknown inputs are treated as tickers directly, which keeps the code minimal and avoids over-engineering (e.g., fuzzy matching, external API).

---

### Step 3: Ticker → CIK Resolution (`cik.py`)

```
"AAPL" → cik_int=320193, cik10="0000320193"
```

1. Downloads SEC's `company_tickers.json` (cached to `.cache/` to avoid re-downloading).
2. Builds a ticker→CIK lookup dict.
3. Returns **two CIK formats** — required because SEC uses different formats in different endpoints:
   - `cik10` (zero-padded): `CIK0000320193.json` — submissions endpoint
   - `cik_int` (integer): `/edgar/data/320193/` — archives path

---

### Step 4: Fetch Submissions & Find Latest 10-K (`filings.py`)

```
GET https://data.sec.gov/submissions/CIK0000320193.json
     ↓
Parse columnar JSON arrays → find first form=="10-K"
     ↓
Extract: accessionNumber, primaryDocument, filingDate
```

**Critical detail — columnar array alignment:**

```python
forms      = data["filings"]["recent"]["form"]              # ["10-K", "8-K", ...]
accessions = data["filings"]["recent"]["accessionNumber"]   # ["0000320193-24-...", ...]
dates      = data["filings"]["recent"]["filingDate"]        # ["2024-11-01", ...]

# All arrays share the same index — form[i], accessions[i], dates[i] are the same filing
for i, form in enumerate(forms):
    if form == "10-K":
        # found it at index i
```

Submissions JSON is also saved to `output/json/` for debugging and traceability.

---

### Step 5: Download Primary Document (`download.py`)

```
Accession: "0000320193-24-000081" → no dashes: "000032019324000081"
     ↓
GET https://www.sec.gov/Archives/edgar/data/320193/000032019324000081/aapl-20240928.htm
     ↓
Parse HTML → find <img> tags → download each image → embed as base64
     ↓
Save self-contained HTML to output/html/
```

**Why base64 image embedding?**
SEC servers return 403 Forbidden when headless browsers (Playwright) try to load images. By downloading images through our HTTP client (which has the correct User-Agent) and embedding them inline as data URLs, the HTML becomes self-contained and renders correctly in Playwright.

**Fallback strategy:**
If the `primaryDocument` download fails, we fetch the filing index page (`{accession}-index.html`), parse it to find the main 10-K document link, and download that instead.

---

### Step 6: Convert to PDF (`pdf.py`)

```
Playwright loads file:///path/to/output/html/AAPL_2024-11-01_000032019324000081.htm
     ↓
page.pdf() generates PDF with scale=0.9, Letter format
     ↓
Atomic write: temp file → rename to output/pdf/AAPL_2024-11-01_10-K.pdf
```

**Why Playwright?**

| Approach | Pros | Cons |
|----------|------|------|
| **Playwright** (chosen) | Full Chromium rendering, handles CSS/JS, most accurate | Requires Chromium install (~300MB) |
| WeasyPrint | Pure Python, no browser | Limited CSS support, breaks on complex layouts |
| wkhtmltopdf | Fast, decent CSS | Deprecated, requires system install |

**Why atomic writes?**
Write to `.tmp` first, then rename. If the process crashes mid-write, we get a temp file instead of a corrupt PDF. The final file either exists completely or not at all.

---

### Step 7: Summary & Exit (`pipeline.py`)

```
================================================================================
SUMMARY
================================================================================
Company         Ticker   CIK          Filing Date  Status   PDF/Error
--------------------------------------------------------------------------------
Apple           AAPL     320193       2024-11-01   OK       output/pdf/AAPL_2024-11-01_10-K.pdf
Meta            META     1326801      2024-02-02   FAILED   HTTP 500: Server error
--------------------------------------------------------------------------------
Total: 2 | OK: 1 | FAILED: 1
================================================================================
```

- Exit code `0` if at least one PDF succeeded, `1` if all failed.
- Per-company isolation: one failure never stops the pipeline.

---

## Extending to Other Filing Types

The current code hardcodes `"10-K"`. Supporting other form types (10-Q, 8-K, DEF 14A, etc.) requires **minimal changes**:

### Changes Required

| Where | What |
|-------|------|
| `cli.py` | Add `--form` argument (default `"10-K"`) |
| `filings.py` | Rename `fetch_latest_10k_meta()` → `fetch_latest_filing_meta(form_type)`, filter by parameter |
| `pipeline.py` | Pass `form_type` through to filings + file naming |
| File naming | Use `form_type` in `safe_filename()` instead of hardcoded `"10-K"` |

### What Stays Unchanged

| Module | Why |
|--------|-----|
| `sec_http.py` | Generic HTTP client — no knowledge of filing types |
| `cik.py` | CIK resolution is independent of form type |
| `download.py` | Downloads any document URL regardless of form type |
| `pdf.py` | Converts any HTML to PDF |
| `utils.py` | Pure utilities, no filing type awareness |

This demonstrates that the architecture separates concerns well — filing-type logic is isolated to the orchestration and metadata layers.

---

## Quick Reference

### SEC URLs

```
Ticker → CIK:   https://www.sec.gov/files/company_tickers.json
Submissions:     https://data.sec.gov/submissions/CIK{cik10}.json
Archives:        https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{document}
Filing index:    https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{accession}-index.html
```

### CIK Formats

```
cik10   = "0000320193"  → submissions endpoint
cik_int = 320193        → archives path
```

### Accession Number

```
Original:   "0000320193-24-000081"
No dashes:  "000032019324000081"    → used in archive URL paths
```

### Exit Codes

```
0 = at least one PDF succeeded
1 = all companies failed
```

---

## Demo Checklist

- [ ] Clean run: `python -m src.main` — generates PDFs for all 6 default companies
- [ ] Custom input: `python -m src.main --companies "TSLA,MSFT,BRK-B"`
- [ ] Inspect output: `ls output/pdf/ output/html/ output/json/`
- [ ] Open a PDF and its source HTML side by side
- [ ] Run tests: `pytest -v`
- [ ] Run linter: `ruff check .`
- [ ] Error handling: try an invalid ticker to show graceful failure
