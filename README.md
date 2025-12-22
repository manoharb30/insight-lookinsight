# Insight Lookinsight

Multi-agent SEC filing analysis platform for bankruptcy risk detection.

## Overview

This platform analyzes SEC filings to identify early warning signals of corporate distress. It uses a multi-agent architecture powered by GPT-4o to extract, validate, and score bankruptcy risk indicators.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js)                          │
├─────────────────────────────────────────────────────────────────────┤
│  /                    - Landing page + ticker input                 │
│  /analysis/[ticker]   - Results page (SSE for real-time updates)    │
│  /compare             - Compare two companies                       │
│  /methodology         - How it works                                │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                           │
├─────────────────────────────────────────────────────────────────────┤
│  Agent 1: Fetcher    → SEC EDGAR API                                │
│  Agent 2: Extractor  → GPT-4o + Supabase pgvector                   │
│  Agent 3: Validator  → Neo4j (signals)                              │
│  Agent 4: Scorer     → Pattern matching                             │
│  Agent 5: Reporter   → Final report                                 │
└─────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, Tailwind CSS, TypeScript |
| Backend | FastAPI (Python 3.11+) |
| Multi-Agent | CrewAI |
| LLM | OpenAI GPT-4o |
| Vector DB | Supabase pgvector |
| Graph DB | Neo4j Aura |

## Getting Started

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Copy .env.example to .env and fill in credentials
cp .env.example .env

# Run the server
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

- `POST /api/v1/analyze` - Start analysis for a ticker
- `GET /api/v1/analyze/{job_id}` - Get analysis status
- `GET /api/v1/stream/{job_id}` - SSE stream for real-time updates
- `GET /api/v1/company/{ticker}` - Get cached analysis
- `GET /health` - Health check

## Signal Types

The platform detects 15 types of distress signals:

1. GOING_CONCERN - Auditor doubt about survival
2. CEO_DEPARTURE - CEO resignation/termination
3. CFO_DEPARTURE - CFO resignation/termination
4. MASS_LAYOFFS - >10% workforce reduction
5. DEBT_DEFAULT - Missed payments, acceleration
6. COVENANT_VIOLATION - Loan covenant breach
7. AUDITOR_CHANGE - Change in auditor
8. BOARD_RESIGNATION - Director departures
9. DELISTING_WARNING - Exchange compliance issues
10. CREDIT_DOWNGRADE - Rating agency downgrades
11. ASSET_SALE - Distressed asset sales
12. RESTRUCTURING - Formal restructuring plans
13. SEC_INVESTIGATION - SEC subpoenas, enforcement
14. MATERIAL_WEAKNESS - Internal control failures
15. EQUITY_DILUTION - Emergency stock issuance

## License

MIT
