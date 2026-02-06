# SEC EDGAR 10-K Filings — Correctness & Compliance Checklist

A concise reference of things that **must not** go wrong. For architecture details see [ARCHITECTURE.md](ARCHITECTURE.md); for step-by-step flow see [FLOW_EXPLANATION.md](FLOW_EXPLANATION.md).

---

## 1) Primary correctness risks (do not mess these up)
- CIK formatting:
  - Submissions endpoint requires 10-digit, zero-padded CIK: `CIK##########.json`
  - Archives path typically uses CIK without leading zeros (int form).
- Latest 10-K selection:
  - Use filings array index alignment (columnar arrays). `form[i]`, `accessionNumber[i]`, `primaryDocument[i]`, `filingDate[i]` must all use the same `i`.
  - Choose the newest by `filingDate` (ISO date string).
- Accession number:
  - Archives directory uses accession with dashes removed: `0000320193-23-000106` -> `000032019323000106`.
- Primary document:
  - Do not assume it’s always `10k.htm`; use the `primaryDocument` field.
  - Some might be `.htm`, `.html`, or `.txt`.

## 2) SEC request policy compliance (non-negotiable)
- Every request must include a descriptive `User-Agent` header (with email).
- Add timeouts on requests; do not use “infinite wait”.
- Rate-limit requests; avoid large concurrency.
- Retries:
  - Retry on: 429, 500–599, connection reset, timeouts.
  - Respect `Retry-After` if present (especially for 429).
- Avoid calling SEC endpoints in unit tests: mock.

## 3) PDF conversion: reliability guidance
- Prefer Playwright for real-world rendering robustness:
  - Convert from local HTML file path to PDF.
  - Use `page.goto(file_url, wait_until="load")` and optionally `networkidle` if needed.
- If using WeasyPrint:
  - Be careful with relative assets; base_url should be set to the HTML file directory.
- Always write PDFs atomically:
  - Write to temp file, then rename, to avoid partial files on failure.

## 4) Defensive coding patterns
- Isolate per-company execution:
  - Each company returns a Result object: `{status, meta, paths, error}`.
- Make HTTP client a single reusable component:
  - Session reuse (requests.Session) for performance.
  - Central retry/backoff logic; do not duplicate across modules.
- Validate inputs early:
  - If a ticker is unknown in mapping -> mark FAILED, continue.
- Always create output dirs with `mkdir(parents=True, exist_ok=True)`.

## 5) Observability: logs + user output
- Use `logging` with structured-ish messages:
  - Include ticker, cik, accession in log context.
- Keep user-facing stdout minimal:
  - progress lines + final summary.
- Do not dump full HTML contents in logs.

## 6) Data handling + caching (keep it fast)
- Cache the ticker->CIK mapping in memory and optionally to disk (e.g., `.cache/company_tickers.json`).
- Avoid downloading the mapping repeatedly in one run.
- Save the submissions JSON per CIK to `output/json/` (optional) for debugging; ignore in git.

## 7) Fallback strategy (optional, but strong if implemented)
If primaryDocument download fails:
- Try the filing index page:
  - `https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{accessionNumber}-index.html`
- Parse it to locate the main document link (HTML) that corresponds to the 10-K.
- If fallback not implemented, document limitation clearly in README.

## 8) Security + repo hygiene
- Never include personal tokens/secrets.
- Ensure `.gitignore` excludes:
  - `output/`, `.venv/`, `.cache/`, `__pycache__/`, `.pytest_cache/`
- Keep dependencies minimal.
- Keep code minimal, and professional. This is a small project, remember that.
- Don't write any unnecessary lines of code that are not in use, or not in explicitely in requirements.

**Logging** - Use `src/core/logging.py` throughout:
```python
from src.core.logging import get_logger
logger = get_logger(__name__)

logger.info("Processing %s", company.ticker)
logger.debug("URL: %s", url)
logger.warning("Retry attempt %d", attempt)
logger.error("Failed: %s", error)
```

**Settings** - Use `src/core/settings.py` for constants:
```python
from src.core.settings import (
    USER_AGENT,              # From env SEC_USER_AGENT or default
    SEC_SUBMISSIONS_URL,     # URL templates
    SEC_ARCHIVES_URL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_COMPANY_TICKERS, # The 6 target companies
)
```

- `USER_AGENT` can be overridden via `SEC_USER_AGENT` environment variable.
- All SEC URLs, default values, and company mappings live in settings.py.

## 9) “Quality bar” checklist for final review
- Run: `python -m src.main` from a clean venv, confirm PDFs are generated.
- Confirm one company failing does not stop others.
- Confirm User-Agent header present for ALL SEC calls.
- Confirm final summary clearly shows each company status.
- Confirm README is runnable and accurate.
- Follow best coding and programming practices.
