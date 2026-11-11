# Samrudhi Agentic OS — P0 Platform

Production-grade, locally-run agentic AI platform. All agents run on **Ollama** (`qwen2.5:7b`) — no cloud APIs.

## Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | LangGraph |
| LLM | Ollama + Qwen (`qwen2.5:7b`) @ `localhost:11434` |
| Database | PostgreSQL (asyncpg) — SQLite for tests |
| Task queue | Celery + Redis |
| API | FastAPI |
| Auth | JWT (human control room only) |
| Tests | pytest + pytest-asyncio |

## Architecture Principles (from `P0_Architecture_5.md`)

- **Rules enforced in code, not prompts** — permissions, approvals, client separation checked by the authority guard before any tool call executes.
- **Serialized LLM calls** — one 7B model, all calls queued through a shared lock.
- **Durable message bus** — every event written to Postgres FIRST (source of truth), then Redis pub/sub for live delivery only.
- **Append-only audit trail** — findings, certifications, lifecycle events, execution log are immutable.
- **8-state agent lifecycle** — `proposed → registered → configured → evaluated → approved → active → monitored → restricted/retired` with a 5-check activation gate.
- **Honest failures** — if Ollama is down, agents report "model unavailable" instead of faking output.

## Project Structure

```
samrudhi-p0/
├── config/
│   └── settings.py              # env-based config (pydantic-settings)
├── backend/
│   ├── main.py                  # FastAPI app + startup/shutdown
│   ├── database.py              # async SQLAlchemy engine + session
│   ├── models/                  # ORM models (all tables from arch §8.3)
│   │   ├── agent.py             # agents, versions, lifecycle_events, specs
│   │   ├── execution.py         # execution_log, capacity_metrics
│   │   ├── bus.py               # bus_events (durable log)
│   │   ├── assurance.py         # findings, evaluations, certifications, incidents
│   │   └── registers.py         # initiatives, decisions, risks, actions, briefs, approvals
│   └── core/
│       ├── message_bus.py       # publish/query durable bus events
│       ├── authority.py         # @authority_guard decorator + permission checks
│       ├── auth.py              # JWT auth for human users
│       ├── llm.py               # serialized Ollama queue wrapper
│       └── agent_runtime.py     # lifecycle state machine + activation gate
├── backend/routes/
│   ├── auth.py                  # /api/auth/login
│   └── agents.py                # /api/agents (list, detail, transition, gate)
├── workers/
│   ├── celery_app.py            # Celery config (Redis broker)
│   └── tasks.py                 # run_agent_task dispatcher
├── agents/
│   ├── base.py                  # BaseAgent + dynamic registry loader
│   ├── SAM-AG-001_Arjun/        # AI CEO (Stage 1A)
│   ├── SAM-AG-007_Sutra/        # AI CTO (Stage 1A)
│   ├── SAM-AG-010_Satya/        # Chief Assurance Agent (Stage 1A)
│   ├── SAM-AG-158_Niyantrak/    # AgentOps & DWMS Lead (Stage 1A)
│   ├── SAM-AG-011_Prakash/      # Compliance verification (Stage 1C)
│   ├── SAM-AG-012_Rajat/        # Risk assessment (Stage 1C)
│   ├── SAM-AG-013_Niti/         # Policy governance (Stage 1C)
│   ├── SAM-AG-014_Satark/       # Security review (Stage 1C)
│   ├── SAM-AG-015_Sachit/       # Evidence management (Stage 1C)
│   ├── SAM-AG-016_Pramaan/      # Certification (Stage 1C)
│   ├── SAM-AG-017_Aarogya/      # Quality assurance (Stage 1C)
│   ├── SAM-AG-018_Samay/        # SLA monitoring (Stage 1C)
│   ├── SAM-AG-019_Sabhyata/     # Audit trail (Stage 1C)
│   ├── SAM-AG-020_Ansh/         # Incident response (Stage 1C)
│   ├── SAM-AG-021_Benchmark/    # Benchmarking (Stage 1C)
│   ├── SAM-AG-022_Satark2/      # Anomaly detection (Stage 1C)
│   ├── SAM-AG-153_Vinyas/       # Platform architecture service (Stage 1B)
│   ├── SAM-AG-154_Setubandh/    # MCP connector service (Stage 1B)
│   ├── SAM-AG-155_Yantra/       # Runtime orchestration service (Stage 1B)
│   ├── SAM-AG-156_Smaran/       # Context/memory service (Stage 1B)
│   ├── SAM-AG-157_Suraksha/     # Security enforcement service (Stage 1B)
│   ├── SAM-AG-159_Pehchaan/     # Identity registry service (Stage 1B)
│   ├── SAM-AG-160_Jod/          # Integration connector service (Stage 1B)
│   ├── SAM-AG-161_Adhikar/      # Permission/access service (Stage 1B)
│   ├── SAM-AG-162_Pravahika/    # Workflow orchestration service (Stage 1B)
│   ├── SAM-AG-163_Sandarbhika/  # Context retrieval service (Stage 1B)
│   ├── SAM-AG-166_Nirikshak/    # Telemetry/monitoring service (Stage 1B)
│   ├── SAM-AG-167_Parikshak/    # Testing/QA service (Stage 1B)
│   ├── SAM-AG-168_Sanskaran/    # Version control service (Stage 1B)
│   └── SAM-AG-170_Chaukidar/    # Security monitoring service (Stage 1B)
├── tests/
│   ├── conftest.py              # SQLite test DB setup
│   ├── test_authority.py        # authority guard tests
│   ├── test_message_bus.py      # durable bus tests
│   ├── test_stage1a_agents.py   # Stage 1A agent tests
│   ├── test_stage1b_agents.py   # Stage 1B agent tests
│   └── test_stage1c_agents.py   # Stage 1C agent tests
├── requirements.txt
└── pytest.ini
```

## Quick Start

### Prerequisites
- Python 3.11+
- Ollama running locally: `ollama serve` + `ollama pull qwen2.5:7b`
- PostgreSQL (for production) — SQLite works for tests
- Redis (for Celery + bus live delivery)

### Install
```bash
cd samrudhi-p0
pip3 install -r requirements.txt
cp .env.example .env   # edit credentials
```

### Run tests
```bash
python3 -m pytest tests/ -v
```

### Start the backend
```bash
uvicorn backend.main:app --reload --port 8000
```
Health check: `http://localhost:8000/api/health`

### Start the Celery worker
```bash
celery -A workers.celery_app worker --loglevel=info
```

## Adding a new agent

1. Create folder `agents/<CANONICAL_ID>_<Name>/`
2. Add `agent.py` with a `@register_agent` class extending `BaseAgent`
3. Set `canonical_id`, `name`, `agent_type`, `AUTHORITY` dict, `SYSTEM_PROMPT`
4. Implement `run(task, **kwargs) → AgentResult` and any `@authority_guard` tools
5. Tests pass automatically via the dynamic loader (`load_all()`)

## Current Status

- **Phase 0 (Platform):** ✅ Complete — DB models, message bus, authority guard, auth, LLM queue, lifecycle gate, FastAPI, Celery.
- **Stage 1A (Core agents):** ✅ Complete — Arjun, Sutra, Satya, Niyantrak.
- **Stage 1B (Technology services):** ✅ Complete — 14 service-first agents (Vinyas, Setubandh, Yantra, Smaran, Suraksha, Pehchaan, Jod, Adhikar, Pravahika, Sandarbhika, Nirikshak, Parikshak, Sanskaran, Chaukidar). All enforce authority guard; graceful model-unavailable handling.
- **Stage 1C (Assurance agents):** ✅ Complete — 12 thinking agents under Satya (Prakash, Rajat, Niti, Satark, Sachit, Pramaan, Aarogya, Samay, Sabhyata, Ansh, Benchmark, Satark2). Full assurance spectrum: compliance, risk, policy, security, evidence, certification, quality, SLA, audit, incidents, benchmarking, anomaly detection.
- **Total tests:** 54 passing.

## Next Steps (per build plan)

1. **Stage 1B** — 14 technology service agents (service-first, mostly no LLM)
2. **Stage 1C** — 12 assurance agents
3. **Phase 1** — Daksh, Aarya, Mitra, Medha (P1 pilot leadership)
4. **Website** — frontend control room (Dashboard, Positions, Tokens, Approvals, Findings)
