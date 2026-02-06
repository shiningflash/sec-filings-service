## SEC EDGAR 10-K Fetch + PDF Conversion (Implementation Requirements)

## 0) High-level objective
Build a Python program that, given a list of companies, fetches the latest SEC 10-K filing for each company via EDGAR APIs, downloads the primary filing document, converts it to PDF, and saves the PDFs locally.

Target companies:
- Apple
- Meta
- Alphabet
- Amazon
- Netflix
- Goldman Sachs

Time expectation: keep the “happy path” runnable in < 5 minutes after setup.

---

## 1) Functional requirements (must-have)
### 1.1 Input
- Accept a list of company names OR tickers via:
  - CLI flag `--companies` (comma-separated), OR
  - a config file (JSON/YAML), OR
  - default hardcoded list (the six companies above).
- Map company -> ticker (default mapping is fine if explicitly stated):
  - Apple=AAPL, Meta=META, Alphabet=GOOGL (or GOOG), Amazon=AMZN, Netflix=NFLX, Goldman Sachs=GS

### 1.2 CIK lookup
- Resolve each ticker to a CIK using SEC-provided ticker mapping file:
  - Download and parse the mapping (cache locally to avoid repeated downloads in the same run).
- Convert CIK to:
  - `cik10`: zero-padded 10-digit string (required for submissions endpoint)
  - `cik_int`: integer/no-leading-zeros (useful for Archives path)

### 1.3 Find latest 10-K
- Fetch submissions JSON:
  - `https://data.sec.gov/submissions/CIK{cik10}.json`
- From `filings.recent`, find the latest entry where `form == "10-K"`.
- Capture:
  - `accessionNumber`
  - `primaryDocument`
  - `filingDate`
  - (optional) `reportDate` if present

### 1.4 Download filing document
- Build Archives URL:
  - `https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{primaryDocument}`
  - `accession_no_dashes` = accessionNumber with "-" removed
- Download the HTML (or txt if it is txt) and save:
  - `output/html/{ticker}_{filingDate}_{accession}.html` (or .txt)

### 1.5 Convert to PDF
- Convert the downloaded primary filing document into a PDF.
- Store PDFs to:
  - `output/pdf/{ticker}_{filingDate}_10-K.pdf`

### 1.6 Summary output
- Print a final summary table to stdout:
  - company/ticker, cik, filingDate, accessionNumber, pdf_path, status (OK/FAILED), error message if failed

### 1.7 Failure isolation
- If one company fails, do not stop the whole run.
- Mark it FAILED in summary and continue with others.

---

## 2) Non-functional requirements (best practices)
### 2.1 SEC request policy compliance
- Every HTTP request MUST set a descriptive User-Agent header.
  - User-Agent format: "Amirul Islam (amirulislamalmamun@gmail.com)"
- Use modest request rate (avoid concurrency blast).
- Add timeouts to all HTTP requests (e.g., connect=5s, read=30s).
- Implement retries with exponential backoff for transient errors (429/5xx/timeouts).
- Respect Retry-After header if present.

### 2.2 Code quality and structure
- Use a small “clean architecture” layout:
  - `src/` package with modules for:
    - sec_client.py (HTTP + retry + headers)
    - cik_resolver.py (ticker mapping + caching)
    - filings.py (parse submissions JSON + pick latest 10-K)
    - downloader.py (download primary doc)
    - pdf_converter.py (HTML->PDF)
    - cli.py / main.py (argument parsing + orchestration)
  - `tests/` minimal tests
- Add typing (type hints) across public functions.
- Add docstrings to key functions.
- Use dataclasses / pydantic models for structured data:
  - `Company`, `FilingMeta`, `DownloadResult`, `ConversionResult`

### 2.3 Logging
- Use Python `logging` (not print) for internal logs:
  - INFO: high-level steps per company
  - DEBUG: URLs and response metadata (avoid dumping huge content)
  - WARNING/ERROR: failures with context
- Keep stdout user-friendly:
  - progress + final summary

### 2.4 Deterministic output
- Ensure output directory exists (create if missing).
- Clean file naming (no spaces, stable).
- Avoid embedding secrets.

---

## 3) PDF conversion approach
Pick ONE method and justify briefly in README.

### Option A: Playwright (recommended for robustness)
- Use Playwright Chromium to render HTML and print to PDF.
- Handle local file rendering:
  - Load downloaded HTML file via `file://...`
  - Wait until network idle if necessary
- Note: requires `playwright install chromium`

Requirement:
- The solution must reliably generate PDFs for the 6 companies on a normal laptop environment.

---

## 4) CLI requirements (must-have)
Implement:
- `python -m src.main` OR `python main.py`
Arguments:
- `--companies "Apple,Meta,Alphabet,Amazon,Netflix,Goldman Sachs"` (optional)
- `--out output` (optional default `output`)
- `--max-per-second 2` (optional)
- `--retries 3` (optional)

Exit codes:
- 0 if at least 1 PDF succeeded
- 1 if all companies failed

---

## 5) Repository requirements (must-have)
### 5.1 Files
- `README.md` with:
  - what it does
  - how it works (short)
  - prerequisites
  - install + run
  - where output is saved
  - design decisions + tradeoffs (brief)
- `requirements.txt`
- `src/` code
- `.gitignore` (ignore output/)
- `LICENSE` optional

### 5.2 Run instructions (README minimum)
Example:
1) `python -m venv .venv && source .venv/bin/activate`
2) `pip install -r requirements.txt`
3) If Playwright: `playwright install chromium`
4) `python -m src.main`
5) PDFs appear in `output/pdf/`

---

## 6) Testing requirements (nice to have, but recommended)
Provide at least 3 unit tests:
- test parsing submissions JSON chooses latest 10-K
- test accession number dash removal + URL construction
- test ticker->CIK resolution (using a small fixture file or mocked response)

Use pytest:
- `pytest -q`

Avoid calling SEC in unit tests (mock HTTP).
Not any unnecessary tests, tests that make sense to exist.

---

## 7) Tooling (optional but strong signal)
### 7.1 Lint/format/type-check (recommended)
- Ruff for lint + format OR black + flake8
- mypy optional
Provide commands in README, e.g.:
- `ruff check .`
- `ruff format .`
- `mypy src/`

### 7.2 Pre-commit (optional)
- `.pre-commit-config.yaml` with ruff + trailing whitespace

### 7.3 GitHub Actions (optional “wow”)
Add `.github/workflows/ci.yml`:
- run tests
- run ruff
- (optional) run mypy

Keep it minimal and fast.

---

## 8) Implementation notes (edge cases to handle)
- Some `primaryDocument` may be .htm or .html; treat both.
- If `primaryDocument` missing or download fails:
  - fallback: use the filing “index page” `*-index.html` to locate the primary 10-K document
  - If implementing fallback is too long, document the limitation clearly.
- Handle HTTP 403/429 gracefully (wait and retry).
- Ensure each company is processed independently.
- Write short, reusable functions with proper and meaningful name following best programming practices.

---

## 9) What to submit (final checklist)
MUST:
- GitHub repo link containing:
  - source code
  - README with run instructions
  - outputs saved locally when run
  - converts latest 10-K for each company to PDF

NICE TO PROVIDE:
- tests
- ruff + formatting
- GitHub Actions CI
- Dockerfile (optional) that runs the script

---

---

## 10) Definition of Done
- Running the program produces up to 6 PDFs in output/pdf for the six companies.
- The final console summary clearly shows success/failure per company.
- The code is readable, modular, typed, and has basic error handling + retries.
- README enables someone new to run it confidently.
