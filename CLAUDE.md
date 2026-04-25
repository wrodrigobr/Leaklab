# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

PokerLeakLab — an AI-powered poker coaching platform. Users upload PokerStars or GGPoker hand history files; the backend parses them, evaluates each decision (equity, position, MTT context), and uses Claude Haiku to generate explanations and study plans. Results are stored per-user and visualized in a single-page frontend.

## Commands

### Running the backend

```bash
cd backend
pip install -r requirements.txt
python api/app.py
```

### Running tests

```bash
cd backend
pip install -r requirements_test.txt

# All tests
python tests/run_all_tests.py

# By suite
python tests/run_all_tests.py --suite engine
python tests/run_all_tests.py --suite api
python tests/run_all_tests.py --suite llm
python tests/run_all_tests.py --suite database
python tests/run_all_tests.py --suite regression

# Single file
python tests/test_api_endpoints.py
python tests/test_decision_engine.py
```

Test output ends with `Total: X Passed: Y Failed: Z`. There is no pytest — tests use a custom runner.

### Frontend

No build step. Open `frontend/index.html` directly in a browser, or serve it statically via Vercel.

## Architecture

```
backend/
  api/app.py              # Flask server — 40+ REST endpoints, ~1200 lines
  leaklab/
    parser.py             # Parses PokerStars hand history text
    pipeline.py           # Converts parsed hands into decision inputs
    decision_engine_v11.py# Scores each decision (equity, position, bet sizing)
    mtt_context.py        # MTT-specific context: M ratio, ICM pressure, stage
    postflop_range_evaluator.py  # Postflop hand strength
    draw_detector.py      # Equity adjustment for flush/straight draws
    llm_explainer.py      # Claude Haiku calls with in-memory prompt-cache keyed by decision hash
    report_generator.py   # Builds final analysis reports
    coach_system.py       # Coach–student linking logic
  database/
    schema.py             # Multi-backend abstraction: SQLite (dev) / PostgreSQL (prod)
    repositories.py       # All DB queries (users, tournaments, decisions, coaches)
    auth.py               # JWT issue/verify
  tests/                  # 13 test files, ~227 test cases
frontend/
  index.html              # Full SPA — HTML + CSS + JS, no framework (~220 KB)
  leaklab-replayer-v3.html# Hand replay variant
```

### Data flow

1. User uploads hand history → `POST /analyze`
2. `parser.py` extracts hands → `pipeline.py` builds decision objects
3. `decision_engine_v11.py` evaluates each decision and flags leaks
4. `llm_explainer.py` sends decisions to Claude Haiku (with caching) for natural-language explanations
5. Results written to database via `repositories.py`
6. Frontend fetches history/evolution/study plan via REST and renders it

### Database

`schema.py` switches transparently between SQLite (local dev, in-memory for tests) and PostgreSQL (production) — no ORM, raw SQL with placeholder normalization (`?` → `%s`). Tables: `users`, `tournaments`, `decisions`, `coaches`, `coaches_profiles`, `leaks_summary`.

### Authentication

JWT Bearer tokens. `auth.py` issues tokens on `/auth/login`; protected routes call `verify_token()` from `app.py`.

### AI integration

`llm_explainer.py` calls Claude Haiku via the Anthropic `requests`-based SDK. Responses are cached in-memory by a hash of the decision. Falls back to a Python template if the API is unavailable. When adding new LLM calls, follow the same cache-keyed pattern used there.

## Environment variables (production)

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude Haiku API key |
| `JWT_SECRET_KEY` | JWT signing secret |
| `DATABASE_URL` | PostgreSQL connection string (absent → SQLite) |
| `PORT` | HTTP port (defaults to 5000) |

## Deployment

- **Backend**: Render — `Dockerfile` + `render.yaml`
- **Frontend**: Vercel — `vercel.json`
- **CI/CD**: `.github/workflows/ci-cd.yml` — runs full test suite; deploys only if all tests pass

## Test suites

| Suite | Files | Coverage |
|---|---|---|
| `engine` | `test_decision_engine.py`, `test_pipeline.py`, `test_draw_detector.py`, `test_postflop_evaluator.py`, `test_mtt_context.py` | Core decision logic |
| `database` | `test_database.py`, `test_coach_system.py` | Schema, auth, repositories |
| `llm` | `test_llm_explainer.py`, `test_study_plan.py` | LLM integration |
| `api` | `test_api_endpoints.py` | All REST endpoints (uses in-memory SQLite) |
| `regression` | `test_tournament.py`, `test_multi_decision.py` | Real tournament hand histories |
