# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

PokerLeakLab — an AI-powered poker coaching platform. Users upload PokerStars or GGPoker hand history files; the backend parses them, evaluates each decision (equity, position, MTT context), and uses Claude Haiku to generate explanations and study plans. Results are stored per-user and visualized in a React SPA frontend.

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

```bash
cd frontend
npm install
npm run dev        # dev server on :8080, proxies /api to :5000
npm run build      # production build → dist/
```

## Architecture

```
backend/
  api/app.py                     # Flask server — 60+ REST endpoints, ~3500 lines
  leaklab/
    parser.py                    # Parses PokerStars/GGPoker hand history text
    pipeline.py                  # Converts parsed hands into decision inputs
    decision_engine_v11.py       # Scores each decision (equity, position, bet sizing)
    mtt_context.py               # MTT context: M ratio, ICM pressure, stage
    postflop_range_evaluator.py  # Postflop hand strength
    draw_detector.py             # Equity adjustment for flush/straight draws
    llm_explainer.py             # Claude Haiku calls with in-memory prompt-cache keyed by decision hash
    report_generator.py          # Builds final analysis reports
    coach_system.py              # Coach–student linking logic
  database/
    schema.py                    # Multi-backend: SQLite (dev) / PostgreSQL (prod) + all migrations
    repositories.py              # All DB queries (~3000 lines)
    auth.py                      # JWT issue/verify; prod enforces LEAKLAB_SECRET ≥32 chars
  tests/                         # 13 test files, ~227 test cases
frontend/
  src/
    pages/
      Index.tsx                  # Main dashboard (player view)
      Training.tsx               # Training hub — Ghost Table + Sparring landing
      Sparring.tsx               # AI Sparring Mode — interactive hand replayer
      Docs.tsx                   # User-facing documentation (12 sections)
      admin/AdminDashboard.tsx   # Admin panel — stats, users, finance, support tickets
    components/hud/
      HudHeader.tsx              # Sticky nav, upload queue, coach chat drawer, support modal trigger
      GhostTable.tsx             # Ghost Table drill system with SRS
      SupportModal.tsx           # Support ticket form + inbox (student view)
      EmptyDashboard.tsx         # Onboarding / upload prompt for new users
    lib/
      api.ts                     # All API calls (typed, ~1650 lines)
      auth.tsx                   # Auth context + JWT storage (sessionStorage)
  leaklab-replayer-v3.html       # Standalone hand replay page
```

### Data flow

1. User uploads hand history → `POST /analyze`
2. `parser.py` extracts hands → `pipeline.py` builds decision objects
3. `decision_engine_v11.py` evaluates each decision and flags leaks
4. `llm_explainer.py` sends decisions to Claude Haiku (with caching) for natural-language explanations
5. Results written to database via `repositories.py`
6. Frontend fetches history/evolution/study plan/AI narratives via REST and renders them

### Database

`schema.py` switches transparently between SQLite (local dev, in-memory for tests) and PostgreSQL (production) — no ORM, raw SQL with placeholder normalization (`?` → `%s`). All schema migrations are in `_run_migrations()` called every startup.

**Tables:** `users`, `tournaments`, `decisions`, `coach_profiles`, `llm_cache`, `coach_study_overrides`, `coach_hand_annotations`, `coach_baselines`, `coach_reviews`, `payments`, `coach_payments`, `drill_sessions`, `achievements`, `session_goals`, `coach_plan_templates`, `coach_messages`, `coach_applications`, `support_tickets`

### Authentication

JWT Bearer tokens (`Authorization: Bearer <token>`). `auth.py` issues tokens on `/auth/login`; protected routes use `@require_auth`, `@require_coach`, or `@require_admin` decorators. In production (Render env), startup raises `RuntimeError` if `LEAKLAB_SECRET` is missing or weak.

### AI integration

`llm_explainer.py` calls Claude Haiku via the Anthropic SDK. Responses are cached in-memory by a hash of the decision. Falls back to a Python template if the API is unavailable. All prompts include `_POKER_TERMS_EN` to prevent translation of technical poker terms. When adding new LLM calls, follow the same cache-keyed pattern.

### Key feature modules

| Feature | Backend | Frontend |
|---|---|---|
| Ghost Table / SRS drills | `/player/spots/drill`, `/player/spots/drill/submit` | `GhostTable.tsx` |
| AI Sparring Mode | `/player/sparring/hand`, `/player/sparring/submit` | `Sparring.tsx`, `PokerTable.tsx` |
| Strategic Career Graph | `/player/career` | `CareerGraphCard.tsx` |
| Cognitive Failure Mapper | `/player/cognitive-failures` | `CognitiveFailureCard.tsx` |
| Personal Strategic Twin | `/player/strategic-twin` | `StrategicTwinCard.tsx` |
| Leak Causal Map | `/player/leak-graph` | `LeakCausalMapCard.tsx` |
| Coach system | `/coach/*`, `/student/*` | `CoachDashboard.tsx`, `CoachMessagesPanel.tsx` |
| Admin panel | `/admin/*` | `AdminDashboard.tsx` |
| Support tickets | `/support/*`, `/admin/support-tickets/*` | `SupportModal.tsx` |
| Gamification (XP/levels) | `/metrics/level`, `/metrics/achievements` | `LevelCard.tsx`, `AchievementsCard.tsx` |

### CORS / Security

CORS origins are controlled by the `ALLOWED_ORIGINS` env var (comma-separated). Defaults to `*` in dev. Set to the actual frontend domain(s) in production via `render.yaml`. The `/analyze/guest` endpoint is rate-limited at 10 req/hour.

## Environment variables (production)

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude Haiku API key |
| `LEAKLAB_SECRET` | JWT signing secret (≥32 chars, auto-generated by Render) |
| `DATABASE_URL` | PostgreSQL connection string (absent → SQLite) |
| `ALLOWED_ORIGINS` | Comma-separated frontend origins for CORS (e.g. `https://leaklab.vercel.app`) |
| `PORT` | HTTP port (defaults to 5000) |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `SENTRY_DSN` | Sentry DSN para error tracking no backend (opcional — sem a var, Sentry é no-op) |
| `ENVIRONMENT` | `production` / `development` — usado pelo Sentry para separar ambientes |

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
