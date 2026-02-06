# SEC EDGAR Filings Service — Architecture at Scale

How this service would evolve from a single-user CLI tool into a production system handling thousands of companies, multiple filing types, and concurrent users — while staying compliant with SEC access policies.

---

## 1. Current State vs. Target State

| Dimension | Current (CLI tool) | Target (Production service) |
|-----------|-------------------|----------------------------|
| Companies | 6 hardcoded defaults | 10,000+ (all SEC filers) |
| Filing types | 10-K only | 10-K, 10-Q, 8-K, DEF 14A, S-1, 20-F, etc. |
| Users | Single operator | Multiple teams / API consumers |
| Execution | CLI, sequential | API server + background workers |
| Storage | Local filesystem | Object storage (S3) + database |
| Scheduling | Manual trigger | Automated — daily/on-filing |
| Throughput | ~2 req/s | Maximized within SEC limits (~10 req/s) |
| Observability | stdout logs | Structured logging, metrics, alerting |

---

## 2. High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                     │
│   FastAPI / nginx                                                            │
│   - REST API: POST /filings/fetch, GET /filings/{id}, GET /filings/{id}/pdf  │
│   - Auth: API keys or OAuth2                                                 │
│   - Rate limiting per client                                                 │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           TASK QUEUE                                         │
│   Celery + Redis (or RQ)                                                     │
│   - Decouple request from processing                                         │
│   - Priority queues: urgent (user-triggered) vs. batch (scheduled)           │
│   - Retry + dead letter queue for persistent failures                        │
└────────────┬──────────────────────────────────────┬──────────────────────────┘
             │                                      │
             ▼                                      ▼
┌──────────────────────────┐          ┌──────────────────────────┐
│      FETCH WORKERS       │          │     PDF WORKERS          │
│   (CPU-light, I/O-bound) │          │   (CPU-heavy)            │
│                          │          │                          │
│   - CIK resolution       │          │   - Playwright Chromium  │
│   - Submissions fetch    │          │   - HTML → PDF render    │
│   - Document download    │          │   - Upload to S3         │
│   - Image embedding      │          │   - Horizontally scaled  │
│   - SEC rate limiter     │          │                          │
│     (shared, centralized)│          │                          │
└──────────┬───────────────┘          └──────────┬───────────────┘
           │                                     │
           ▼                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                                          │
│                                                                              │
│   PostgreSQL                           S3 / MinIO                            │
│   - companies table                    - output/html/{cik}/{accession}.htm   │
│   - filings table (metadata)           - output/pdf/{cik}/{accession}.pdf    │
│   - jobs table (status tracking)       - output/json/{cik}/submissions.json  │
│   - filing_documents table             - Lifecycle policies (archive/delete) │
│                                                                              │
│   Redis                                                                      │
│   - Ticker -> CIK cache (TTL: 24h)                                           │
│   - SEC rate limiter state (shared)                                          │
│   - Task queue broker                                                        │
└──────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        OBSERVABILITY                                         │
│                                                                              │
│   Structured Logging → ELK / Loki       Metrics → Prometheus / Grafana       │
│   - JSON logs with request_id,          - Filings processed/min              │
│     ticker, cik, form_type              - PDF conversion duration (p50/p99)  │
│   - Correlated across workers           - SEC error rate (429s, 5xx)         │
│                                         - Queue depth                        │
│   Alerting → PagerDuty / Slack / Teams                                       │
│   - SEC rate limit breaches             Health checks                        │
│   - Worker crash rate > threshold       - /health endpoint                   │
│   - Queue backlog > threshold           - Liveness + readiness probes        │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Critical Design Decisions

### 3.1 SEC Rate Limiting at Scale — Centralized Limiter

**Problem:** SEC allows ~10 req/s total (not per worker). Multiple workers must share a single rate limit.

**Solution:** Centralized rate limiter using Redis.

```text
Worker A ──┐
Worker B ──┼──► Redis (sliding window counter) ──► SEC EDGAR
Worker C ──┘
```

**Implementation options:**

| Approach | How it works | Pros | Cons |
|----------|-------------|------|------|
| **Redis sliding window** (recommended) | `INCR` key with TTL; check count before request | Simple, battle-tested | Slight race conditions under extreme load |
| Token bucket in Redis | `EVALSHA` Lua script to atomically consume tokens | Precise, handles bursts | More complex Lua scripting |
| Dedicated proxy | nginx/Envoy with rate limiting sits between workers and SEC | Language-agnostic, centralized | Extra infrastructure component |

**Recommendation 1: Redis sliding window for simplicity.** Lua-based token bucket if precision matters.

**Recommendation 2: 8 req/s instead of 10.** Leave headroom. SEC's limit isn't well-documented; 8 req/s provides safety margin and avoids 429s.

---

### 3.2 Separating Fetch Workers from PDF Workers

**Why separate?**

| Concern | Fetch workers | PDF workers |
|---------|---------------|-------------|
| Bottleneck | Network I/O (SEC rate limit) | CPU (Chromium rendering) |
| Scaling | Limited by SEC rate limit (can't add more workers to go faster) | Scales horizontally — more workers = more PDFs/min |
| Memory | Low (~50MB) | High (~500MB+ per Chromium instance) |
| Failure mode | Transient network errors | Rendering crashes |

Separating them means:
- PDF rendering doesn't block the SEC request pipeline
- Each can scale independently based on its bottleneck
- A Chromium crash doesn't lose the already-downloaded HTML

---

### 3.3 Database Schema

```sql
CREATE TABLE companies (
    id          SERIAL PRIMARY KEY,
    ticker      VARCHAR(10) UNIQUE NOT NULL,
    name        VARCHAR(255),
    cik_int     INTEGER UNIQUE NOT NULL,
    cik10       CHAR(10) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE filings (
    id                  SERIAL PRIMARY KEY,
    company_id          INTEGER REFERENCES companies(id),
    form_type           VARCHAR(20) NOT NULL,  -- "10-K", "10-Q", "8-K", etc.
    accession_number    VARCHAR(25) UNIQUE NOT NULL,
    filing_date         DATE NOT NULL,
    report_date         DATE,
    primary_document    VARCHAR(255),
    html_s3_key         TEXT,
    pdf_s3_key          TEXT,
    status              VARCHAR(20) DEFAULT 'pending',  -- pending, downloaded, converted, failed
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_filings_company_form ON filings(company_id, form_type);
CREATE INDEX idx_filings_status ON filings(status);
CREATE INDEX idx_filings_date ON filings(filing_date DESC);
```

**Why PostgreSQL?**
- ACID transactions for reliable status tracking
- Rich indexing for queries like "all failed 10-Ks from last week"
- JSON columns available if we want to store raw submissions metadata
- Well-supported by every ORM and migration tool

---

### 3.4 Object Storage for Documents

**Why S3 instead of local filesystem?**

| Concern | Local filesystem | S3 / MinIO |
|---------|-----------------|------------|
| Durability | Single disk | 99.999999999% (11 nines) |
| Scaling | Disk fills up | Virtually unlimited |
| Access | Only from host | Any worker, any region |
| Cost | Server storage | ~$0.023/GB/month |
| Lifecycle | Manual cleanup | Auto-archive to Glacier after 90 days |

**Key layout:**
```
s3://sec-filings/
├── html/{cik_int}/{accession_no_dashes}/{document}
├── pdf/{cik_int}/{accession_no_dashes}/{form_type}.pdf
└── json/{cik_int}/submissions.json
```

Use CIK-based paths (not ticker) because CIK is immutable. Tickers can change (e.g., Facebook → Meta).

---

## 4. Multiple Filing Types

### 4.1 Supported Form Types

| Form | Description | Frequency | Complexity |
|------|-------------|-----------|------------|
| 10-K | Annual report | 1/year | High — large HTML, many images |
| 10-Q | Quarterly report | 3/year | Medium — similar to 10-K but smaller |
| 8-K | Current event report | As needed | Low — usually short |
| DEF 14A | Proxy statement | 1/year | Medium — charts and tables |
| S-1 | IPO registration | Once | High — very large documents |
| 20-F | Foreign annual report | 1/year | High — similar to 10-K |

### 4.2 What Changes per Filing Type

Most of the pipeline is **form-type agnostic**. The only parts that care about form type:

1. **Filing selection** — filter by `form == form_type` in submissions JSON
2. **File naming** — include form type in output filename
3. **(Optional) Document selection** — 8-K filings may have multiple exhibits worth downloading

Everything else (HTTP client, CIK resolution, download, image embedding, PDF conversion) is generic.

### 4.3 Filing-Specific Edge Cases

**8-K (Current Events):**
- Multiple primary documents per filing (press releases, exhibits)
- Decision: Download only `primaryDocument`, or all exhibits?
- Recommendation: Configurable — default to primary only, `--include-exhibits` flag for full download

**S-1 (IPO Registration):**
- Very large documents (100+ pages)
- May have amendments (S-1/A)
- Playwright may need higher timeout and more memory

**20-F (Foreign Filers):**
- Same structure as 10-K but different form code
- May have non-English content
- PDF rendering should handle Unicode correctly (Playwright does)

---

## 5. Scheduling & Automation

### 5.1 Trigger Modes

| Mode | When | How |
|------|------|-----|
| **On-demand** | User requests via API | POST /filings/fetch → enqueue task |
| **Scheduled daily** | Every night at 2 AM UTC | Celery Beat / cron → check for new filings |
| **SEC RSS feed** | Real-time-ish (10 min lag) | Poll SEC EDGAR RSS, enqueue new filings |

### 5.2 Daily Batch Pipeline

```text
02:00 UTC  →  For each tracked company:
                1. Fetch submissions JSON
                2. Compare with last known filing in DB
                3. If new filing found → enqueue download + convert
                4. If no new filing → skip (no wasted work)
```

### 5.3 SEC EDGAR RSS Feed (Near Real-Time)

SEC publishes RSS feeds for new filings:
```
https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K&dateb=&owner=include&count=10&search_text=&action=getcompany&output=atom
```

A poller checks this feed every 10 minutes, and enqueues new filings it hasn't seen before.

---

## 6. API Design

### 6.1 REST Endpoints

```
POST   /api/v1/filings/fetch
       Body: { "tickers": ["AAPL", "META"], "form_type": "10-K" }
       Response: { "job_id": "abc-123", "status": "queued" }

GET    /api/v1/filings/jobs/{job_id}
       Response: { "status": "completed", "results": [...] }

GET    /api/v1/filings?ticker=AAPL&form_type=10-K&limit=5
       Response: { "filings": [...] }

GET    /api/v1/filings/{filing_id}/pdf
       Response: 302 redirect to S3 pre-signed URL

GET    /api/v1/health
       Response: { "status": "ok", "queue_depth": 12, "workers": 4 }
```

### 6.2 Technology Choice: FastAPI

| Why FastAPI | Details |
|-------------|---------|
| Async support | Can handle many concurrent API requests while workers do the heavy lifting |
| Auto-generated docs | OpenAPI/Swagger UI out of the box |
| Pydantic models | Request/response validation, consistent with Python typing |
| Performance | One of the fastest Python web frameworks |

---

## 7. Security

### 7.1 Authentication & Authorization

| Layer | Mechanism |
|-------|-----------|
| API access | API keys (simple) or OAuth2/JWT (enterprise) |
| Key rotation | Store keys in secrets manager (AWS Secrets Manager, HashiCorp Vault) |
| Per-client rate limiting | Separate from SEC rate limiting — prevents one client from starving others |

### 7.2 Data Security

| Concern | Mitigation |
|---------|-----------|
| SEC filings are public | No encryption needed for content, but secure transport (HTTPS) always |
| S3 access | IAM policies — workers get write, API gets read, no public access |
| Database | Encrypted at rest, connection via SSL, no plaintext credentials in config |
| Secrets management | Environment variables or secrets manager — never committed to repo |

### 7.3 Input Validation

- Validate tickers against known format (1-5 uppercase letters, plus hyphens)
- Validate form types against allowed list
- Sanitize all user input before using in file paths or URLs
- Reject requests for excessive company counts in single batch

---

## 8. Performance Optimization

### 8.1 Caching Strategy

| What | Where | TTL | Why |
|------|-------|-----|-----|
| Ticker → CIK mapping | Redis | 24 hours | Changes rarely; 10K+ entries, fast lookup |
| Submissions JSON | Redis / S3 | 1 hour | Avoid re-fetching during retries |
| Generated PDFs | S3 | Indefinite | Don't regenerate; serve from cache |
| Filing existence check | PostgreSQL | Permanent | "Have we already processed this filing?" |

### 8.2 Avoiding Redundant Work

```python
# Before processing:
existing = db.query(Filing).filter_by(
    accession_number=accession,
    status="converted"
).first()

if existing:
    return existing  # Already have this filing — skip
```

### 8.3 PDF Conversion Performance

Playwright/Chromium is the bottleneck. Optimizations:

1. **Browser pool** — Keep N Chromium instances warm instead of launching per-document
2. **Page reuse** — Reuse browser pages across conversions (clear state between)
3. **Resource limits** — Set memory limits per Chromium process to prevent OOM
4. **Timeout enforcement** — Kill conversions that exceed threshold (e.g., 60s)

```python
# Browser pool concept
class BrowserPool:
    def __init__(self, size: int = 4):
        self.pool = asyncio.Queue(maxsize=size)
        # Pre-launch browsers
        for _ in range(size):
            browser = await playwright.chromium.launch()
            await self.pool.put(browser)

    async def acquire(self) -> Browser:
        return await self.pool.get()

    async def release(self, browser: Browser):
        await self.pool.put(browser)
```

### 8.4 Throughput Estimates

| Bottleneck | Capacity | Notes |
|------------|----------|-------|
| SEC requests | ~8 req/s (conservative) | Shared across all workers |
| Fetch pipeline | ~480 filings/min | Avg 1 request per filing (cached CIK) |
| PDF conversion | ~4 PDFs/min per worker | 10-K filings are 50-200 pages |
| With 4 PDF workers | ~16 PDFs/min | Linear scaling |
| With 8 PDF workers | ~32 PDFs/min | Diminishing returns (memory pressure) |

---

## 9. Reliability & Error Handling

### 9.1 Retry Strategy (Multi-Level)

```text
Level 1: HTTP retry (Tenacity) — 429, 5xx, timeouts
Level 2: Task retry (Celery) — worker crash, OOM
Level 3: Dead letter queue — manual inspection after N failures
```

### 9.2 Failure Modes & Recovery

| Failure | Detection | Recovery |
|---------|-----------|----------|
| SEC returns 429 | HTTP status | Respect Retry-After, exponential backoff |
| SEC returns 5xx | HTTP status | Retry with backoff (max 3 attempts) |
| Chromium OOM | Worker crash | Celery auto-retries on different worker |
| S3 upload failure | Exception | Retry upload; filing stays in "downloaded" status |
| Database down | Connection error | Workers queue locally, flush when DB recovers |
| Network partition | Timeout | Circuit breaker pattern — stop hitting SEC, retry later |

### 9.3 Idempotency

Every operation is idempotent — re-running the same filing produces the same result:
- Download overwrites same S3 key
- PDF conversion overwrites same S3 key
- Database upserts on accession_number (unique)

This means retries and duplicate messages are safe.

---

## 10. Infrastructure & Deployment

### 10.1 Containerization

```
docker-compose.yml:
  api:        FastAPI server (2 replicas)
  fetch-worker: Celery worker for SEC fetching (2 replicas)
  pdf-worker:   Celery worker for PDF conversion (4 replicas, high memory)
  scheduler:    Celery Beat for scheduled jobs (1 replica)
  redis:        Task broker + cache
  postgres:     Metadata storage
```

### 10.2 Kubernetes (Production)

```yaml
# PDF worker deployment — needs more memory
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pdf-worker
spec:
  replicas: 4
  template:
    spec:
      containers:
      - name: pdf-worker
        image: sec-filings-service:latest
        command: ["celery", "-A", "worker", "--queues=pdf"]
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

### 10.3 Environment Progression

```text
Local dev  →  Docker Compose  →  Staging (K8s)  →  Production (K8s)
```

| Environment | Purpose | Infrastructure |
|-------------|---------|---------------|
| Local | Development + debugging | `python -m src.main` (current CLI) |
| Docker Compose | Integration testing | All services on one machine |
| Staging | Pre-production validation | K8s with reduced replicas |
| Production | Real workloads | K8s with autoscaling, monitoring |

---

## 11. Technology Summary

| Concern | Current | At Scale |
|---------|---------|----------|
| Runtime | Python 3.12 | Python 3.12 (same) |
| API framework | argparse CLI | FastAPI |
| Task queue | N/A (sequential) | Celery + Redis |
| HTTP client | requests + tenacity | Same (proven, reliable) |
| PDF engine | Playwright | Same (with browser pool) |
| Database | N/A (filesystem) | PostgreSQL |
| Cache | File-based | Redis |
| Storage | Local filesystem | S3 / MinIO |
| Logging | Python logging (text) | structlog (JSON) → ELK/Loki |
| Metrics | N/A | Prometheus + Grafana |
| CI/CD | GitHub Actions | GitHub Actions → ArgoCD |
| Container | N/A | Docker + Kubernetes |
| Rate limiting | In-process sleep | Redis distributed limiter |
| Auth | N/A (CLI tool) | API keys / OAuth2 |

---

## 12. Migration Path — From CLI to Service

The current codebase is well-structured for incremental migration:

### Phase 1: Add Database + S3

- Add SQLAlchemy models for `companies` and `filings` tables
- Replace filesystem writes with S3 uploads
- Keep CLI as the trigger mechanism
- **No changes to:** `sec_http.py`, `cik.py`, `filings.py`, `download.py`, `pdf.py`

### Phase 2: Add Task Queue

- Wrap `process_company()` as a Celery task
- Replace `simple_rate_limiter()` with Redis-based distributed limiter
- Add retry/dead-letter configuration
- **No changes to:** `sec_http.py`, `cik.py`, `filings.py`, `download.py`, `pdf.py`

### Phase 3: Add API Layer

- FastAPI app with endpoints from section 6.1
- Enqueue tasks instead of processing inline
- Add authentication
- **No changes to:** `sec_http.py`, `cik.py`, `filings.py`, `download.py`, `pdf.py`

### Phase 4: Observability + Hardening

- Switch to structured logging (structlog)
- Add Prometheus metrics
- Add health checks and alerting
- Load testing and capacity planning

**Key insight:** The core pipeline modules (`sec_http.py`, `cik.py`, `filings.py`, `download.py`, `pdf.py`) don't change at all across these phases. The layered architecture pays off — only the orchestration and infrastructure layers evolve.

---

## 13. Honest Limitations & Trade-offs

| Trade-off | Decision | Reasoning |
|-----------|----------|-----------|
| Python for PDF rendering | Accepted | Playwright does the heavy lifting; Python is the orchestrator |
| No real-time processing | Accepted | SEC rate limits make real-time impractical anyway |
| Chromium dependency | Accepted | Most accurate rendering; worth the ~300MB install |
| Single SEC identity | Limitation | All requests use one User-Agent; SEC may rate-limit by IP regardless |
| No full-text search | Out of scope | Would need Elasticsearch + document parsing pipeline |
| SEC API instability | Risk | SEC occasionally changes endpoints or formats without notice |

---

## 14. Compliance at Scale

### SEC Fair Access

Even at scale, all SEC compliance rules apply:

- **User-Agent**: Same requirement. One identity per organization.
- **Rate limit**: ~10 req/s total — doesn't increase with more infrastructure.
- **No scraping**: Use only documented EDGAR APIs and endpoints.
- **Respect robots.txt**: Don't crawl pages not intended for programmatic access.

### Data Handling

- SEC filings are **public data** — no privacy concerns for the documents themselves.
- User data (API keys, usage patterns) requires standard security practices.
- Retention policies: Keep filings indefinitely (they're public records), but manage storage costs with lifecycle policies (hot → warm → cold tiers).
