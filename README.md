# UniLog Enricher

Product enrichment pipeline that ingests product data (CSV/XLSX), performs web research using Tavily search, scrapes manufacturer pages and PDFs, and extracts structured product data via LLM.

## What it does

1. **Ingest** — Accepts CSV/XLSX uploads with product rows (manufacturer part number, description, brand, etc.)
2. **Research** — Generates 5 targeted search queries per row, searches via Tavily (advanced mode, 5 queries/row), selects credible sources
3. **Collect** — Downloads and parses manufacturer PDFs, scrapes webpages, follows immediate PDF links only
4. **Extract** — Feeds input row + evidence to LLM with a strict extraction prompt; outputs structured `ExtractedProduct` JSON
5. **Output** — Generates CSV/XLSX with enriched product data

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│  CSV/XLSX   │────▶│  Job/Row DB  │────▶│  Processing     │────▶│  Enriched    │
│  Upload     │     │  (PostgreSQL)│     │  Pipeline       │     │  Output      │
└─────────────┘     └──────────────┘     │  (per row)      │     └──────────────┘
                                          │  Research →     │
                                          │  Evidence →     │
                                          │  Extraction     │
                                          └─────────────────┘
```

### Pipeline per row

1. **Query Generation** — LLM generates 5 targeted search queries from input row
2. **Search** — Tavily advanced search (5 queries, 2 credits each = 10 credits/row)
3. **Source Selection** — LLM classifies sources (official/manufacturer_document/secondary), filters junk
4. **Collection** — Downloads PDFs, scrapes webpages, follows immediate PDF links only
5. **Evidence Building** — Deduplicates, truncates large docs (>100K chars), formats for LLM
6. **Extraction** — Single LLM call with input row + evidence + schema → `ExtractedProduct` JSON

### Concurrency

- `WORKER_CONCURRENCY` (default 1) controls threads per job
- Each worker claims rows via `SELECT ... FOR UPDATE SKIP LOCKED`
- `MAX_OFFICIAL_PDFS = 5` per row limits manufacturer PDF ingestion

## Repository Structure

```
src/
├── api/                    # FastAPI routes, models, storage
├── database/               # SQLAlchemy models, repositories, connection
├── models/                 # Pydantic models (input, extraction, search, research, document)
├── pipeline/
│   ├── extraction/         # Extraction prompt, evidence builder, ProductExtractor
│   ├── ingestion/          # Web scraper (Firecrawl), PDF fetcher/parser, resource resolver
│   ├── llm/                # LLM client (NVIDIA), factory, config, debug logging
│   ├── research/           # Query gen, Tavily search, source selector, orchestrator
│   └── input/              # CSV/XLSX loaders
├── services/               # ProcessingService, Worker, TavilyUsageTracker, JobService
├── unilog_enricher/        # FastAPI app, lifespan, middleware
└── prompts/                # Extraction prompt, query generation, source selection
frontend/                   # React + Vite + Tailwind (upload, jobs, capacity UI)
alembic/                    # SQLAlchemy migrations
compose.yaml                # Docker Compose (app + PostgreSQL)
Dockerfile                  # Multi-stage build (uv + Python 3.12)
pyproject.toml              # uv project config
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/jobs` | Upload CSV/XLSX, create job (202) |
| GET    | `/api/jobs` | List all jobs |
| GET    | `/api/jobs/{job_id}` | Job status + counts |
| GET    | `/api/jobs/{job_id}/rows` | Per-row status |
| POST   | `/api/jobs/{job_id}/retry-failed` | Requeue failed rows |
| GET    | `/api/jobs/{job_id}/download` | Download enriched CSV/XLSX |
| GET    | `/api/usage` | Tavily credits used/remaining, estimated rows remaining |

### Job lifecycle

`queued` → `processing` → `completed` / `failed`

Row states: `pending` → `processing` → `completed` / `failed`

## Configuration

Environment variables (see `compose.yaml`):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `NVIDIA_API_KEY` | Yes | — | NVIDIA NIM API key |
| `LLM_PROVIDER` | No | `nvidia` | `nvidia` only currently |
| `LLM_MODEL` | No | `nvidia/nemotron-3-ultra-550b-a55b` | Model name |
| `TAVILY_API_KEY` | Yes | — | Tavily search API key |
| `FIRECRAWL_API_KEY` | Yes | — | Firecrawl web scraping |
| `TAVILY_MONTHLY_CREDITS` | No | `1000` | Monthly credit limit for UI estimate |
| `CORS_ORIGINS` | No | `` | Comma-separated origins |
| `WORKER_CONCURRENCY` | No | `1` | Threads per job |
| `TAVILY_API_KEY` | Yes | — | Tavily API key |
| `FIRECRAWL_API_KEY` | Yes | — | Firecrawl API key |

## Running Locally

### Prerequisites

- Docker + Docker Compose
- PostgreSQL (via compose)
- NVIDIA API key, Tavily API key, Firecrawl API key

### Start

```bash
# Create .env with required keys
cp .env.example .env  # or create manually

# Start PostgreSQL + API
docker compose up -d

# API at http://localhost:8000
# Frontend at http://localhost:5173 (dev) or served by API in prod
```

### Frontend dev

```bash
cd frontend
npm install
npm run dev
```

## Running Tests

```bash
# Backend
python -m pytest test_api.py -v

# Frontend typecheck
cd frontend && npx tsc --noEmit
```

## Input Format

CSV/XLSX with columns (case-sensitive):

| Column | Required | Description |
|--------|----------|-------------|
| `Mfg_Part_Num` | Recommended | Manufacturer part number |
| `Part_Desc` | Recommended | Product description |
| `Part_Manuf` | Optional | Manufacturer name |
| `MANUFACTURER_PART_NUMBER` | Optional | Enriched field (output) |
| `PART_NUMBER` | Optional | Internal part number |
| `SKU - MY_PART_NUMBER` | Optional | Internal SKU |
| `E1_Brand` / `Unilog_Brand` / `DIB_Brand` | Optional | Brand fields |
| `Dept` / `Class` / `Fine` | Optional | Classification |

Minimum viable row: at least one identifier (MPN, model number, or description).

## Output Format

Enriched CSV/XLSX with all input columns + extracted fields:

- **Identity**: `MFR URL`, `Ref URL 1-5`, `PART_NUMBER`, `Mfg_Part_Num`, `SKU`, `MANUFACTURER_PART_NUMBER`, `ALTERNATE_PART_NUMBER`
- **Classification**: `Dept`, `Class`, `Fine`, `Classpath`
- **Descriptions**: `INVOICE_DESC` (≤40 chars), `MOBILE_DESC` (60-80), `RETAIL_DESC`, `LONG_DESC1`, `MARKETING_DESCRIPTION`
- **Identity**: `MANUFACTURER_NAME`, `BRAND_NAME`, `TRADE_NAME`, `E1_Brand`, `Unilog_Brand`, `DIB_Brand`, `Part_Manuf`
- **Attributes**: Up to 50 `ExtractedAttribute` (label, value, UOM)
- **Features**: Up to 20 `item_features`
- **Identifiers**: `UPC`, `EAN`, `GTIN`, `UNSPSC`
- **Commercial**: `Warranty`, `List Price`, `Selling Qty`, `Selling UOM`, `Standard Packaging Information`
- **Dimensions**: `LENGTH`, `WIDTH`, `HEIGHT`, `WEIGHT`, `VOLUME` + UOMs
- **Images**: `Product Image`, `Alternate Image 1-4`
- **Documents**: `SDS`, `SDS_1`, `Warranty Information`, `Catalog`, `Specification Sheet`, `Instruction/Installation Manual`, `Service Manual`, `Owners/User Manual`, `Line Drawing`, `MTR`, `RoHS`, `Full Engineering Drawing`, `Energy Star Guide`, `Technical Bulletin`, `Submittal`, `Compatibility Chart`, `Size Chart`, `Product Label/Insert`, `Video Link`, `Video Link 1`
- **Meta**: `Country Of Origin`, `Discontinued` ("Yes"/"No"), `Actual Image (Yes/No)`

## Key Implementation Details

### Evidence grounding

- **Closed world**: LLM only uses input row + supplied evidence + schema
- **No invention**: "NEVER INVENT PRODUCT INFORMATION" — null preferred over guess
- **Population gate**: Field populated only if (1) explicitly established, (2) relevant to field, (3) exact target product
- **Conflict handling**: Manufacturer evidence > secondary; normalized values compared before conflict

### Source authority

1. Manufacturer product page
2. Manufacturer technical documentation
3. Manufacturer specification sheet
4. Manufacturer installation/manual
5. Manufacturer catalog
6. Manufacturer warranty/documentation
7. Other official manufacturer-hosted
8. Distributor/dealer/retailer
9. Other third-party
10. Marketplace listing

### Document collection rules

- Direct PDFs: downloaded + parsed
- Webpages: scraped via Firecrawl, markdown + links extracted
- Only immediate PDF links followed from webpages (no recursion)
- Max 5 official PDFs per row, max 5 total PDFs per resolution pass
- Language-variant deduplication (English preferred)

### Tavily usage tracking

- Per-row credit tracking via `SearchUsage` (per-request `credits_used` + `credits_remaining`)
- `/api/usage` endpoint returns session usage + estimated rows remaining
- `TAVILY_MONTHLY_CREDITS` env var (default 1000) for estimate
- Estimate: `floor(remaining / 10)` where 10 credits/row (5 queries × 2 credits)

### Retry / recovery

- Per-stage retries (default 3) with independent attempt counting
- Startup recovery: jobs in `queued`/`processing` with pending rows reset to `queued`, processing rows → `pending`
- `/retry-failed` endpoint requeues failed rows, preserves attempts/error history

### Input validation

- Max upload: 50 MB
- Formats: `.csv` (UTF-8) or `.xlsx` (sheet named "Input")
- Duplicate headers rejected, empty headers rejected, header-only rejected

## Known Limitations

- **LLM provider**: Only NVIDIA (Nemotron) supported via `LLM_PROVIDER=nvidia`
- **Single LLM call per extraction** — no multi-pass refinement
- **Tavily advanced only** — basic/fast not configurable
- **No deep research iterations** — single-pass query → search → select → collect
- **Firecrawl required** for web scraping (no fallback)
- **PostgreSQL only** in production (SQLite for tests)
- **No auth** on API endpoints
- **No pagination** on `/jobs` or `/jobs/{id}/rows`

## Development Notes

### Adding a new LLM provider

1. Create `src/pipeline/llm/<provider>.py` implementing `LLMClient` protocol
2. Update `src/pipeline/llm/factory.py` to route provider
3. Add config in `src/pipeline/llm/config.py`

### Running migrations

```bash
alembic upgrade head
alembic revision --autogenerate -m "description"
```

### Debug logging

LLM calls logged to `debug/llm_calls/` (request/response JSON + summary.jsonl). Falls back to console only if directory not writable.

### Debug extraction for one row

```bash
python test_extraction_direct.py
```

Uses `ProcessingService` directly with hardcoded test row.

## Project Status

Actively developed. Core pipeline stable. Extraction prompt actively refined (see `src/prompts/extraction/extract_product.md` — 3000+ lines of extraction rules).

## License

MIT