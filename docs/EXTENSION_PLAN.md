# SEC EDGAR 10-K FILINGS - Extending to Other Filing Types

### Current State: 10-K Only

The code currently hardcodes `"10-K"` in `filings.py`:

```python
def fetch_latest_10k_meta(...):
    # ...
    for i, form in enumerate(forms):
        if form == "10-K":  # ← Hardcoded
            # ...
```

### What Changes for Other Filing Types (10-Q, 8-K, etc.)

#### Minimal Changes Needed:

**1. Make filing type a parameter:**

```python
# filings.py - CHANGE
def fetch_latest_filing_meta(
    client: SecHttpClient,
    cik10: str,
    cik_int: int,
    ticker: str,
    form_type: str,  # NEW PARAMETER: "10-K", "10-Q", "8-K"
    out_json_dir: Path | None = None,
) -> FilingMeta:
    for i, form in enumerate(forms):
        if form == form_type:  # Use parameter instead of hardcoded
            # ...
```

**2. Update CLI to accept filing type:**

```python
# cli.py - ADD
parser.add_argument(
    "--form",
    type=str,
    default="10-K",
    help="SEC form type to fetch (e.g., 10-K, 10-Q, 8-K)"
)
```

**3. Update pipeline to pass form type:**

```python
# pipeline.py - CHANGE
def process_company(
    company_name: str,
    client: SecHttpClient,
    ticker_map: dict[str, int],
    output_dirs: dict[str, Path],
    form_type: str = "10-K",  # NEW PARAMETER
) -> CompanyResult:
    meta = fetch_latest_filing_meta(
        ...,
        form_type=form_type,
    )
```

**4. Update file naming:**

```python
# Currently:
pdf_filename = safe_filename(ticker, meta.filing_date, "10-K", extension=".pdf")

# Change to:
pdf_filename = safe_filename(ticker, meta.filing_date, form_type, extension=".pdf")
```

#### What Stays Unchanged:

| Module | Unchanged? | Why |
|--------|------------|-----|
| `sec_http.py` | Yes | Generic HTTP client, doesn't know about filing types |
| `cik.py` | Yes | CIK resolution is independent of filing type |
| `download.py` | Yes | Downloads any document URL, doesn't care about form type |
| `pdf.py` | Yes | Converts any HTML to PDF |
| `models.py` | Mostly | `FilingMeta` already has `form_type` field |
| `utils.py` | Yes | Pure utilities, no filing type knowledge |

END
