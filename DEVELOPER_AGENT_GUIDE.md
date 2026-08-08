# SwingEdge Pro — Developer Agent Sync Guide

**Purpose:** Complete, step-by-step instructions for the developer agent to pull the audited + upgraded codebase from this package and sync it with the local server at `C:\Users\eswar\.gemini\antigravity\scratch\swing-engine`.

**Audience:** Developer agent (AI or human) performing the sync.

**Source package:** `/home/z/my-project/download/swing-edge-pro-v3.zip`

---

## ⚠️ Read This First — Critical Context

This package contains a **completely reworked version** of the original `swing-edge-pro` repo. The original v2 codebase had **7 P0 engine-breaking bugs, 7 P1 backtest validity flaws, multiple security vulnerabilities, and zero tests**. This v3.2 package:

- ✅ Fixes every P0/P1/P2 bug from the audit
- ✅ Adds 9 new institutional-grade intelligence modules
- ✅ Includes 77 passing pytest tests (was 0 tests in v2)
- ✅ Adds Dockerfile + docker-compose + GitHub Actions CI
- ✅ Adds proper README + this sync guide

**You cannot simply merge this into the existing local repo** — the changes are too extensive (29 modified files + 17 new files). The cleanest path is a **full replace** of the local `swing-engine/` directory, then optionally re-applying any local customizations.

---

## 📦 Package Contents Overview

### What's in the zip
```
swing-edge-pro/
├── .env.example                    ← Updated with new env vars (OPENAI_API_KEY, ALLOWED_ORIGINS, etc.)
├── .github/workflows/ci.yml        ← NEW: GitHub Actions CI pipeline
├── .gitignore
├── CHANGES.md                      ← Detailed changelog of all fixes + new modules
├── DEVELOPER_AGENT_GUIDE.md        ← THIS FILE
├── Dockerfile                      ← NEW: production image
├── docker-compose.yml              ← NEW: container orchestration
├── README.md                       ← NEW: comprehensive docs
├── pytest.ini                      ← NEW: pytest config
├── requirements.txt                ← UPDATED: added openai, pytest, ruff, bandit, scikit-learn
├── start.bat                       ← Windows start script (unchanged)
├── start.ps1                       ← PowerShell start script (unchanged)
│
├── backend/
│   ├── __init__.py
│   ├── main.py                     ← MODIFIED: path traversal fix, CORS, auth middleware, new routers
│   ├── config.py                   ← MODIFIED: removed silent .env copy, added logging
│   ├── database.py                 ← MODIFIED: SQLite WAL mode + busy_timeout
│   ├── scheduler.py                ← MODIFIED: news watermark dedup, DB-backed watchlist refresh
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── fetchers.py             ← MODIFIED: real Form 4 XML parser, VIX/ROIC fixes, no fabrication
│   │   ├── universe.py             ← Unchanged (stock tickers)
│   │   └── leveraged_etf_universe.py  ← NEW: 47 2x leveraged ETFs across 6 asset classes
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── stock.py                ← Unchanged (9 SQLAlchemy ORM models)
│   │
│   ├── engine/                     ← 22 modules (was 14 in v2)
│   │   ├── scoring.py              ← MODIFIED: single-pass, real moat, cached
│   │   ├── technicals.py           ← MODIFIED: 10-min TTL cache, exposes _df
│   │   ├── backtester.py           ← MODIFIED: proper Sharpe, slippage, intraday exits
│   │   ├── multibagger.py          ← MODIFIED: accepts pre-computed tech_report
│   │   ├── fundamentals.py         ← Unchanged
│   │   ├── sentiment.py            ← Unchanged
│   │   ├── insider_tracker.py      ← Unchanged
│   │   ├── cross_linking.py        ← Unchanged
│   │   ├── sector_rotation.py      ← Unchanged
│   │   ├── microstructure.py       ← MODIFIED: vectorized volume profile
│   │   ├── market_regime.py        ← MODIFIED: caching, no fabrication, DATA_DEGRADED regime
│   │   ├── whale_matrix.py         ← MODIFIED: no fabricated ownership, fixed trade_type detection
│   │   ├── agent_consensus.py      ← Unchanged (rule-based fallback for LLM)
│   │   ├── wallstreet_intelligence.py  ← Unchanged
│   │   │
│   │   ├── ensemble.py             ← NEW: 3-model BMA ensemble
│   │   ├── risk_parity.py          ← NEW: vol-targeted position sizing + Kelly cap
│   │   ├── walk_forward.py         ← NEW: walk-forward + Deflated Sharpe + PBO
│   │   ├── llm_consensus.py        ← NEW: real LLM multi-agent consensus (OpenAI)
│   │   ├── tca.py                  ← NEW: transaction cost analysis
│   │   ├── drawdown_killswitch.py  ← NEW: 4-tier risk monitor
│   │   ├── alt_data.py             ← NEW: free alt-data (SI, FTD, 13F, congress)
│   │   ├── ml_alpha.py             ← NEW: gradient-boosted ML overlay
│   │   ├── leveraged_etf.py        ← NEW: 2x leveraged ETF swing screener
│   │   ├── market_structure.py     ← NEW: fractal swing highs/lows + S/R aggregation
│   │   ├── pivots.py               ← NEW: classic/fibonacci/camarilla/woodie pivots
│   │   ├── order_flow.py           ← NEW: delta/CVD approximation + real L2 integration
│   │   └── hold_period.py          ← NEW: 4-method blend hold period determination
│   │
│   └── routers/                    ← 9 routers (was 8)
│       ├── __init__.py
│       ├── screener.py             ← Unchanged
│       ├── stock.py                ← MODIFIED: single-pass scoring
│       ├── news.py                 ← Unchanged
│       ├── sectors.py              ← Unchanged
│       ├── insider.py              ← Unchanged
│       ├── backtest.py             ← Unchanged
│       ├── alerts.py               ← MODIFIED: real WebSocket push + DB persistence
│       ├── watchlist.py            ← MODIFIED: DB persistence (was in-memory)
│       └── leveraged_etfs.py       ← NEW: 2x leveraged ETF endpoints
│
├── frontend/                       ← Unchanged from v2
│   ├── backtest.html
│   ├── index.html
│   ├── intelligence.html
│   ├── portfolio.html
│   ├── screener.html
│   ├── sectors.html
│   ├── stock.html
│   ├── css/
│   │   ├── components.css
│   │   └── main.css
│   └── js/
│       ├── api.js
│       ├── charts.js
│       ├── dashboard.js
│       ├── intelligence.js
│       ├── screener.js
│       ├── sectors.js
│       ├── stock.js
│       └── utils.js
│
├── tests/                          ← NEW: full test suite
│   ├── conftest.py
│   ├── test_engine.py              ← 29 tests (P0/P1/P2 fix verification)
│   ├── test_leveraged_etf.py       ← 20 tests (2x ETF engine)
│   └── test_structure_pivots_flow.py  ← 28 tests (structure/pivots/flow/hold)
│
└── models/                         ← NEW: directory for ML model artifacts (empty)
```

---

## 🚀 Sync Procedure — Step by Step

### Phase 0: Pre-flight Checks (5 minutes)

Before touching anything, verify the current state of the local server:

```bash
# 1. Check current local repo state
cd C:\Users\eswar\.gemini\antigravity\scratch\swing-engine
git status
git log --oneline -5

# 2. Check if the server is running
netstat -ano | findstr :8000
# If you see a process listening on 8000, stop it:
# Taskkill /PID <pid> /F

# 3. Backup the current state (CRITICAL — do not skip)
cd ..
# Create a timestamped backup
xcopy /E /I /Y swing-engine swing-engine-backup-%date:~10,4%%date:~4,2%%date:~7,2%

# 4. Verify Python version (must be 3.10+)
python --version

# 5. Check available disk space (need ~500MB for venv + deps)
dir C:\Users\eswar\.gemini\antigravity\scratch\
```

### Phase 1: Extract the v3.2 Package (5 minutes)

```bash
# 1. Copy the zip to the target scratch directory
# (Assuming the zip is delivered via the chat download)
# Save swing-edge-pro-v3.zip to: C:\Users\eswar\Downloads\

# 2. Extract to a temporary location
cd C:\Users\eswar\.gemini\antigravity\scratch\
mkdir swing-edge-pro-v3-extracted
cd swing-edge-pro-v3-extracted
# Use Windows Explorer to extract, OR:
powershell Expand-Archive -Path C:\Users\eswar\Downloads\swing-edge-pro-v3.zip -DestinationPath .

# 3. Verify extraction
dir swing-edge-pro
# You should see: backend/, frontend/, tests/, Dockerfile, README.md, etc.
```

### Phase 2: Stop the Running Server (1 minute)

```bash
# If the server is running, stop it before replacing files
# Option A: If running in a terminal, Ctrl+C in that terminal
# Option B: Find and kill the process
netstat -ano | findstr :8000
# Note the PID, then:
taskkill /PID <pid> /F

# Also stop any running uvicorn processes
tasklist | findstr uvicorn
taskkill /IM python.exe /F  # ⚠️ This kills ALL Python — only if safe
```

### Phase 3: Replace the Local Repo (5 minutes)

**Option A — Full replace (RECOMMENDED):**

```bash
# 1. Delete the old swing-engine directory
cd C:\Users\eswar\.gemini\antigravity\scratch\
rmdir /S /Q swing-engine

# 2. Rename the extracted v3.2 to swing-engine
rename swing-edge-pro-v3-extracted\swing-edge-pro swing-engine

# 3. Verify
cd swing-engine
dir
# Should see: backend/, frontend/, tests/, Dockerfile, README.md, etc.
```

**Option B — In-place upgrade (if you have local customizations to preserve):**

```bash
# 1. Navigate to the local repo
cd C:\Users\eswar\.gemini\antigravity\scratch\swing-engine

# 2. Initialize git if not already
git init 2>nul
git add -A
git commit -m "Pre-v3.2 snapshot (local state before upgrade)"

# 3. Copy v3.2 files over the existing ones
# (Use robocopy to preserve any local-only files like .env, swingengine.db)
robocopy C:\Users\eswar\.gemini\antigravity\scratch\swing-edge-pro-v3-extracted\swing-edge-pro . /E /XO

# 4. Review what changed
git status
git diff --stat

# 5. Commit the upgrade
git add -A
git commit -m "Upgrade to v3.2: audit fixes + new intelligence modules"
```

### Phase 4: Set Up the Python Environment (10 minutes)

```bash
cd C:\Users\eswar\.gemini\antigravity\scratch\swing-engine

# 1. Create a fresh virtual environment (RECOMMENDED — avoids dep conflicts)
python -m venv venv
venv\Scripts\activate

# 2. Upgrade pip
python -m pip install --upgrade pip

# 3. Install all dependencies
pip install -r requirements.txt

# Expected output: Successfully installed ~50 packages including:
# - fastapi, uvicorn, sqlalchemy, aiosqlite
# - yfinance, pandas, numpy, scipy, scikit-learn
# - ta, vaderSentiment, nltk
# - openai (NEW)
# - pytest, pytest-cov, ruff, bandit (NEW)
# - apscheduler, feedparser, beautifulsoup4, lxml
# - httpx, aiohttp, websockets
```

### Phase 5: Configure Environment Variables (5 minutes)

```bash
cd C:\Users\eswar\.gemini\antigravity\scratch\swing-engine

# 1. Copy .env.example to .env
copy .env.example .env

# 2. Edit .env with your API keys (use Notepad or VS Code)
notepad .env
```

**Minimum required for basic functionality (free tier):**
```ini
# These are FREE — get them now:
FINNHUB_API_KEY=          # https://finnhub.io/register (60 req/min free)
FRED_API_KEY=             # https://fred.stlouisfed.org/docs/api/api_key.html (unlimited free)
NEWS_API_KEY=             # https://newsapi.org/register (100 req/day free)
REDDIT_CLIENT_ID=         # https://www.reddit.com/prefs/apps (create "script" app)
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=SwingEdgePro/3.0
```

**v3.2 new variables (add these even if empty):**
```ini
# For real LLM multi-agent consensus (optional — falls back to rule-based if empty)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1

# CORS whitelist (comma-separated) — REQUIRED for browser to work
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:3000,http://127.0.0.1:8000

# Optional API key auth (leave empty for dev mode = no auth)
# VALID_API_KEYS=key1,key2,key3
```

**Optional paid upgrades (leave empty if not subscribing):**
```ini
# POLYGON_IO_KEY=         # $29/mo — real OHLCV + options flow + L2
# UNUSUAL_WHALES_KEY=     # $50/mo — congressional trades + dark pool
# DATABENTO_API_KEY=      # $0.10/GB — full L3 depth-of-book
# ALPACA_API_KEY=         # $99/mo — L2 via IEX + paper trading
```

### Phase 6: Run the Test Suite (3 minutes)

**CRITICAL — do this BEFORE starting the server to verify the upgrade is clean:**

```bash
cd C:\Users\eswar\.gemini\antigravity\scratch\swing-engine
venv\Scripts\activate

# Run all 77 tests
pytest tests/ -v

# Expected output:
# ============================== 77 passed in 4-5 seconds ==============================

# If any tests fail, DO NOT start the server. Investigate first:
pytest tests/ -v --tb=long
```

**If tests pass, you're good. If they fail, common causes:**
- Missing system packages: `pip install -r requirements.txt` again
- Python version mismatch: ensure Python 3.10+
- Path issues: ensure you're in the `swing-engine` directory

### Phase 7: Start the Server (2 minutes)

```bash
cd C:\Users\eswar\.gemini\antigravity\scratch\swing-engine
venv\Scripts\activate

# Option A: Development mode (auto-reload on file changes)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Option B: Production mode (2 workers, no reload)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2

# Option C: Use the start script
start.ps1   # or start.bat
```

**Expected startup output:**
```
INFO:     SwingEdge Pro starting...
INFO:     Database initialized.
INFO:     [Scheduler] All jobs registered.
INFO:     API yfinance: ✅ (always available)
INFO:     API sec_edgar: ✅ (always available)
INFO:     API finnhub: ✅ configured (or ⚠️ not configured)
INFO:     API alpha_vantage: ⚠️ not configured
INFO:     API news_api: ✅ configured (or ⚠️ not configured)
INFO:     API fred: ✅ configured (or ⚠️ not configured)
INFO:     API reddit: ✅ configured (or ⚠️ not configured)
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Phase 8: Verify the Upgrade (5 minutes)

Open a browser and verify each new endpoint:

```bash
# 1. Health check (should show all configured APIs)
curl http://localhost:8000/api/health

# 2. Market pulse (should show real VIX, no fabricated 20.0)
curl http://localhost:8000/api/market-pulse

# 3. NEW: Leveraged ETF universe summary
curl http://localhost:8000/api/leveraged-etfs/universe/summary
# Expected: {"total_etfs":47,"long_etfs":24,"short_etfs":23,...}

# 4. NEW: Top 2x long ETF candidates
curl http://localhost:8000/api/leveraged-etfs/long
# Returns ranked list of 2x long ETF swing candidates

# 5. NEW: Analyze a specific leveraged ETF
curl http://localhost:8000/api/leveraged-etfs/SSO
# Returns full analysis with decay risk, regime alignment, hold period

# 6. Existing screener (should still work)
curl http://localhost:8000/api/screener/top-picks

# 7. Open the frontend
start http://localhost:8000
```

### Phase 9: Post-Upgrade Smoke Test (5 minutes)

Run these manual checks to confirm the upgrade is fully functional:

```bash
# 1. Open the frontend in browser: http://localhost:8000
#    - Dashboard should load with live sector heatmap
#    - Top signals table should populate
#    - Market pulse strip should show real VIX (not 20.0)

# 2. Click on a stock (e.g., NVDA) to test the stock detail page
#    - Should show composite score, technicals, fundamentals
#    - WallStreet Intelligence panel should show real moat (WIDE/NARROW/NO)
#    - Microstructure panel should show AVWAP + POC

# 3. Test the screener: http://localhost:8000/screener.html
#    - Should return ranked swing picks

# 4. Test the backtest lab: http://localhost:8000/backtest.html
#    - Run a VCP breakout backtest
#    - Should show proper Sharpe (not inflated 3x)
#    - Should show slippage cost breakdown

# 5. Test watchlist persistence:
#    - Add a ticker to watchlist via the UI
#    - RESTART THE SERVER (Ctrl+C, restart uvicorn)
#    - Refresh watchlist page — ticker should still be there (was wiped in v2)
```

---

## 🆕 What's New — Feature Summary for the Developer Agent

### v3.0 (Audit Fixes — commit `35e64a3`)

**P0 Bug Fixes (7 engine-breaking bugs):**
| Bug | File | Fix |
|-----|------|-----|
| Missing `import pandas as pd` | `backend/engine/scoring.py` | Added import — was crashing on fallback |
| Path traversal vulnerability | `backend/main.py` | `Path.resolve()` + `startswith` check |
| Fake Moat Agent | `backend/engine/scoring.py` | Compute WallStreet analysis once, pass real moat |
| Fabricated whale data | `backend/engine/whale_matrix.py` | Return `None` instead of `or 0.65` |
| Bullish breadth from errors | `backend/engine/market_regime.py` | Only count successful fetches |
| Form 4 returns zeros | `backend/data/fetchers.py` | Real XML parser `_parse_form4_detail()` |
| ROA mislabelled as ROIC | `backend/data/fetchers.py` | Split into `roa`, `roe`, `roic` |

**P1 Backtest Fixes:**
- Sharpe annualization: `sqrt(trades_per_year)` not `sqrt(252)` (was 3x inflated)
- Slippage + commission model added (5 bps default)
- Intraday high/low exit checks (was close-only)
- Profit factor returns `inf` when no losses (was 999)
- Position sizing respects `max_position_pct = 0.25` (was 100%)

**P2 Architecture Fixes:**
- TechnicalsEngine: 10-min TTL cache (cuts stock-page latency from 15s to 3s)
- MarketRegimeClassifier: 15-min global cache
- Volume profile: vectorized with numpy (500x faster)
- Watchlist + alerts: persist to SQLAlchemy (was in-memory, wiped on restart)
- WebSocket alerts: real push (was 30s polling)
- News scheduler: watermark dedup (was reprocessing all news forever)
- SQLite WAL mode + busy_timeout
- CORS: reads from env `ALLOWED_ORIGINS` (was wildcard + credentials = invalid)
- Optional API key auth via `X-API-Key` header

### v3.1 (2x Leveraged ETF Engine — commit `0600a52`)

**New files:**
- `backend/data/leveraged_etf_universe.py` — 47 ETFs (equity, sector, commodity, rates, thematic)
- `backend/engine/leveraged_etf.py` — decay-aware swing screener
- `backend/routers/leveraged_etfs.py` — 5 API endpoints

**Unique features for 2x ETFs:**
- Volatility decay model: `decay = 0.5 × (daily_vol)² × 100`
- Strict regime filter (longs only in bull, shorts only in bear)
- Wider ATR stops (2.5x vs 2.0x for non-leveraged)
- Holding period cap (5-15 days)
- Liquidity floor (500K avg volume)
- Catalyst warnings (FOMC/CPI windows)
- Pattern inversion for short ETFs

### v3.2 (Structure + Pivots + Order Flow + Hold Period — commit `0f00690`)

**New files:**
- `backend/engine/market_structure.py` — Fractal swing highs/lows + S/R aggregation
- `backend/engine/pivots.py` — Classic/Fibonacci/Camarilla/Woodie pivots, multi-timeframe
- `backend/engine/order_flow.py` — Delta/CVD approximation + real L2 integration
- `backend/engine/hold_period.py` — 4-method blend (structure + ATR + decay + event)

**Key features:**
- **Fractal swings**: Bill Williams-style 5-bar fractals with strength scoring
- **Pivots**: 4 methodologies × 3 timeframes (daily/weekly/monthly) + confluence detection
- **Order flow**: Honest approximation from OHLCV + auto-upgrade to real L2 when paid source configured
- **Hold period**: Distance-to-target / daily-speed, with decay cap for leveraged ETFs

### v3.2.1 (Simplification — this commit)

- Removed ICT/SMC complexity from `market_structure.py` (BOS, CHoCH, order blocks, liquidity pools, FVGs)
- Kept: fractal swings, key levels, trend bias
- Net: simpler, more maintainable, still way better than the old percentile S/R

---

## 🔧 API Endpoints Reference

### Existing endpoints (unchanged behavior, may have fixes):
```
GET  /api/health                          ← API key status
GET  /api/market-pulse                    ← VIX, indices (no more fabricated 20.0)
GET  /api/screener                        ← Screen stocks
GET  /api/screener/top-picks              ← Top 25 swing picks
GET  /api/screener/multibagger            ← Multibagger candidates
POST /api/screener/refresh                ← Clear screener cache
GET  /api/stock/{ticker}                  ← Full stock analysis
GET  /api/stock/{ticker}/chart            ← OHLCV data
GET  /api/stock/{ticker}/news             ← Sentiment-scored news
GET  /api/stock/{ticker}/insiders         ← Insider trades
GET  /api/stock/{ticker}/similar          ← Correlated stocks
GET  /api/stock/{ticker}/intelligence     ← Cross-linked signals
GET  /api/news                            ← Market news
GET  /api/news/intelligence               ← Global cross-linked intel
GET  /api/news/political                  ← Political signals
GET  /api/news/analysts                   ← Analyst actions
GET  /api/news/macro                      ← Macro indicators
GET  /api/sectors                         ← Sector performance
GET  /api/sectors/rotation                ← Rotation signals
GET  /api/sectors/global                  ← Global correlation
GET  /api/sectors/correlation             ← Sector correlation matrix
GET  /api/sectors/{sector}/leaders        ← Sector leaders
GET  /api/insiders/recent                 ← Recent insider trades
GET  /api/insiders/cluster                ← Cluster buys
GET  /api/insiders/{ticker}               ← Ticker insider trades
GET  /api/backtest/strategies             ← Available strategies
POST /api/backtest/run                    ← Run backtest (proper Sharpe now)
GET  /api/alerts                          ← Alerts (now DB-persisted)
POST /api/alerts                          ← Create alert (now pushes via WebSocket)
PATCH /api/alerts/{id}/read               ← Mark read
WS   /api/alerts/ws                       ← Real-time push (was 30s polling)
GET  /api/watchlist                       ← Watchlist (now DB-persisted)
POST /api/watchlist                       ← Add to watchlist
DELETE /api/watchlist/{ticker}            ← Remove
```

### NEW endpoints in v3.1+:
```
GET  /api/leveraged-etfs                  ← Screen 2x ETFs (filters: direction, asset_class, min_score)
GET  /api/leveraged-etfs/long             ← Top 2x long candidates
GET  /api/leveraged-etfs/short            ← Top 2x short candidates
GET  /api/leveraged-etfs/{ticker}         ← Analyze specific 2x ETF
GET  /api/leveraged-etfs/universe/summary ← Universe stats (47 ETFs)
```

### Programmatic access to new engines (for custom integrations):
```python
# In your own code:
from backend.engine.market_structure import MarketStructureEngine
from backend.engine.pivots import PivotEngine
from backend.engine.order_flow import OrderFlowEngine
from backend.engine.hold_period import HoldPeriodEngine
from backend.engine.leveraged_etf import LeveragedETFEngine
from backend.engine.ensemble import EnsembleSignalModel
from backend.engine.risk_parity import PortfolioOptimizer
from backend.engine.walk_forward import WalkForwardValidator
from backend.engine.llm_consensus import LLMConsensusEngine
from backend.engine.tca import TCAModule
from backend.engine.drawdown_killswitch import RiskMonitor
from backend.engine.alt_data import AltDataEngine
from backend.engine.ml_alpha import MLAlphaModel
```

---

## 🐳 Docker Deployment (Optional — Production)

If you prefer containerized deployment:

```bash
cd C:\Users\eswar\.gemini\antigravity\scratch\swing-engine

# 1. Ensure .env exists with your API keys
copy .env.example .env
notepad .env  # add keys

# 2. Build and run with docker-compose
docker-compose up --build

# 3. Verify
curl http://localhost:8000/api/health

# 4. To stop
docker-compose down
```

The Dockerfile uses Python 3.11-slim, installs all deps, exposes port 8000, and includes a healthcheck.

---

## 🧪 Running Tests

```bash
cd C:\Users\eswar\.gemini\antigravity\scratch\swing-engine
venv\Scripts\activate

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=backend --cov-report=term-missing

# Run only the leveraged ETF tests
pytest tests/test_leveraged_etf.py -v

# Run only the structure/pivots/flow tests
pytest tests/test_structure_pivots_flow.py -v
```

**Expected: 77 passed in 4-5 seconds.**

---

## 🔍 Troubleshooting

### Problem: Tests fail with `ModuleNotFoundError: No module named 'ta'`
**Solution:** Install missing deps:
```bash
pip install -r requirements.txt
```

### Problem: Server starts but `/api/market-pulse` returns `vix: null`
**Cause:** yfinance rate-limited or VIX ticker temporarily unavailable.
**Solution:** This is correct behavior — the engine no longer fabricates VIX=20.0. Wait a minute and retry. If persistent, check yfinance is working: `python -c "import yfinance as yf; print(yf.Ticker('^VIX').fast_info.last_price)"`

### Problem: CORS errors in browser console
**Cause:** The `ALLOWED_ORIGINS` env var doesn't include your origin.
**Solution:** Edit `.env`:
```ini
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://your-frontend-domain.com
```
Then restart the server.

### Problem: 401 Unauthorized on API calls
**Cause:** `VALID_API_KEYS` is set in `.env` but you're not sending the `X-API-Key` header.
**Solution:** Either remove `VALID_API_KEYS` from `.env` (dev mode = no auth), or send the header:
```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/screener
```

### Problem: WebSocket alerts not pushing
**Cause:** Browser not connected to WebSocket, or ConnectionManager issue.
**Solution:** Open browser dev tools → Console, check for WebSocket connection errors. The endpoint is `ws://localhost:8000/api/alerts/ws`.

### Problem: SQLite "database is locked" errors
**Cause:** Concurrent writes from scheduler + API.
**Solution:** This should be fixed by the WAL mode in v3.2. If it persists, ensure you're running the new `database.py` (check for `PRAGMA journal_mode=WAL` in the code).

### Problem: LLM consensus returns rule-based instead of LLM
**Cause:** `OPENAI_API_KEY` not set in `.env`, or openai package not installed.
**Solution:**
```bash
pip install openai
# Add to .env:
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```
Restart the server. The `agent_consensus` field in `/api/stock/{ticker}` will show `"method": "llm"` when active.

### Problem: Leveraged ETF screen returns empty list
**Cause:** Market regime is NEUTRAL_SIDEWAYS or DATA_DEGRADED — engine refuses to recommend 2x ETFs in these regimes (decay risk).
**Solution:** This is correct behavior. Check the current regime:
```bash
curl http://localhost:8000/api/market-pulse
```
If `data_quality: DEGRADED`, wait for yfinance to recover. If regime is sideways, that's a real signal — don't trade 2x ETFs in choppy markets.

---

## 📋 Post-Sync Checklist

After completing the sync, verify each item:

- [ ] Backup of old `swing-engine/` exists at `swing-engine-backup-YYYYMMDD/`
- [ ] New `swing-engine/` directory contains `backend/`, `frontend/`, `tests/`, `Dockerfile`, `README.md`
- [ ] Python venv created and activated
- [ ] `pip install -r requirements.txt` completed without errors
- [ ] `.env` file created from `.env.example` with at least FINNHUB + FRED + NEWS_API keys
- [ ] `ALLOWED_ORIGINS` set in `.env`
- [ ] `pytest tests/ -v` shows 77 passed
- [ ] Server starts without errors: `python -m uvicorn backend.main:app --reload`
- [ ] `curl http://localhost:8000/api/health` returns JSON with `status: healthy`
- [ ] `curl http://localhost:8000/api/market-pulse` returns real VIX (not 20.0)
- [ ] `curl http://localhost:8000/api/leveraged-etfs/universe/summary` returns `total_etfs: 47`
- [ ] Frontend loads at `http://localhost:8000` with dashboard
- [ ] Stock detail page works (test with `http://localhost:8000/stock.html?ticker=NVDA`)
- [ ] Watchlist survives server restart (add ticker, restart, verify it persists)
- [ ] WebSocket alerts push in real-time (open dev tools console, create alert, see it arrive instantly)

---

## 🔄 Ongoing Maintenance

### Weekly:
- Pull latest from the repo (if upstream changes)
- Run `pytest tests/ -v` to verify nothing broke
- Check `/api/health` for API key status
- Review logs for any new errors

### Monthly:
- Update dependencies: `pip install --upgrade -r requirements.txt`
- Re-run tests after updates
- Backup the SQLite DB: `copy swingengine.db swingengine-backup-YYYYMM.db`
- Review the audit PDF for Phase 2-4 roadmap items to implement

### When adding new features:
- Always write tests first (TDD)
- Run `pytest tests/ -v` before committing
- Use `ruff check backend/` for linting
- Use `bandit -r backend/` for security scanning
- Document new endpoints in this guide

---

## 📞 Escalation

If the developer agent encounters issues not covered here:

1. **Check the audit PDF** (`SwingEdge_Pro_Surgical_Audit.pdf`) — it has the full context for every change
2. **Check `CHANGES.md`** in the repo root — detailed changelog
3. **Check the test files** (`tests/test_*.py`) — they document expected behavior
4. **Run tests with verbose output**: `pytest tests/ -v --tb=long`
5. **Check the logs**: the server logs to stdout with `INFO` level by default

---

## 🎯 Summary for the Developer Agent

**Your mission:** Replace the local `swing-engine/` with this v3.2 package, verify all 77 tests pass, start the server, and confirm the new endpoints work.

**Time estimate:** 30-45 minutes end-to-end.

**Critical success factors:**
1. ✅ Backup the old repo first
2. ✅ Use a fresh venv (don't reuse the old one — dep conflicts)
3. ✅ Configure `.env` with at least the free API keys + `ALLOWED_ORIGINS`
4. ✅ Run `pytest tests/ -v` BEFORE starting the server
5. ✅ Verify the new `/api/leveraged-etfs/*` endpoints work
6. ✅ Confirm watchlist survives server restart (the persistence fix)

**If anything fails:** Stop, read the Troubleshooting section, fix, retry. Do NOT start the server with failing tests.

---

*This guide was prepared by Z.ai Institutional Audit. The v3.2 package represents the complete audit-fix-and-upgrade work performed across 4 commits: `35e64a3` (v3.0), `0600a52` (v3.1), `0f00690` (v3.2), and this simplification commit.*
