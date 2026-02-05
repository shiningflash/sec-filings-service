# SEC EDGAR 10-K FILINGS — Confirmed Decisions (Single Source of Truth)

## Chosen stack / tooling
- Python: 3.12
- Environment: `uv venv --python 3.12`
- Dependency management: requirements.txt (installed via uv/pip)
- CLI: argparse
- HTTP: requests
- Retry/backoff: tenacity
- Rate limit: simple sleep limiter (default max 2 req/sec)
- Execution: sequential (no parallelism)
- HTML -> PDF: Playwright (Chromium print-to-PDF)
- Lint/format: Ruff
- Tests: pytest (mocked HTTP; no real SEC calls)
- CI: GitHub Actions (ruff + pytest)

## Output policy
- Output directories (gitignored):
  - output/html/   (downloaded primary documents)
  - output/pdf/    (final PDFs)
  - output/json/   (saved submissions JSON for debugging/traceability)
- Save submissions JSON is ON by default (can be optional flag if desired).

## Fallback policy (must implement)
- If downloading `primaryDocument` fails or is missing:
  - fetch `{accessionNumber}-index.html` for the filing
  - parse to locate the main 10-K HTML document
  - retry download + PDF conversion using the discovered document link

## SEC compliance (must follow)
- Set a descriptive User-Agent header for ALL SEC requests (include email).
- Use timeouts for all HTTP calls; no infinite waits.
- Retry on 429/5xx/timeouts with exponential backoff; respect Retry-After.
- Do not overwhelm SEC endpoints; keep requests modest and sequential.

## Quality bar
- Per-company failure isolation (one failure must not stop others).
- Final summary printed to stdout (OK/FAILED per company + paths + error).
- Deterministic file naming; atomic PDF writes (temp -> rename).

END
