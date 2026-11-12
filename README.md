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
│   ├── settings.py              # env-based config (pydantic-settings)
│   ├── agent_registry.yaml      # canonical registry of the 79 built agents (PDF Document 01C)
│   └── project_flows.yaml       # project flow used by the Control Room runner
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
│   ├── SAM-AG-<id>_<Name>/      # 79 agents: one folder per canonical ID
│   │                            # IDs, positions, titles and managers: config/agent_registry.yaml
├── tests/
│   ├── conftest.py              # SQLite test DB setup
│   ├── test_authority.py        # authority guard tests
│   ├── test_message_bus.py      # durable bus tests
│   ├── test_stage1a_agents.py   # Stage 1A agent tests
│   ├── test_stage1b_agents.py   # Stage 1B agent tests
│   ├── test_stage1c_agents.py   # Stage 1C agent tests
│   └── test_phase1_agents.py    # Phase 1 P1 agent tests
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
On Windows add `--pool=solo`.

## Control Room (web UI + project flow)

One command runs everything (Redis via Docker if it is not running, migrations,
agent-registry seed, Celery worker, API + UI):
```bash
python -m scripts.run_all
```
- New UI: `http://localhost:8000/` — Projects (new project, start, live run, approvals), History, Agents
- Previous UI: `http://localhost:8000/legacy/` (agent detail, activation gate, lifecycle transitions)
- API docs: `http://localhost:8000/docs`

A project runs the flow in `config/project_flows.yaml` (Smriti → Anvesh → Yojana →
Lekha → Roop → Shuddhi → Pariksha, mapped onto Daksh's delivery stages). The
runner (`backend/projects/`) only dispatches the existing `run_agent_task`
Celery task; it refuses agents that are not Active, checks each step's
permission with the authority guard, and asks a signed-in human for approval
after the compliance check and the final review. Without Redis the same task
runs in a local process and the UI polls every 5 seconds.

New tables (Alembic migration `migrations/versions/0001_project_tables.py`):
`projects`, `project_messages`, `project_steps`, `approval_decisions`.

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
- **Stage 1C (Assurance agents):** 12 agents under Satya, as in the PDF registry: Pramana, Nishtha, Maryada, Seema, Gopniya, Sakshi, Sankat (service-first, no model) and Yogyata, Pramanik, Gunvatta, Nishpaksh, Swasthya (role agents that judge but never produce). Swasthya blocks high-risk health claims in code; Gopniya flags personal and other-client data; Pramanik recommends but cannot certify.
- **Phase 1 (P1 Pilot Leadership):** ✅ Complete — 4 executive agents (Daksh COO, Aarya CCO, Mitra CXO, Medha Intelligence). Each has 13 authority-guarded tools, 5 registers (20 new DB tables), workflow state machines, and full I/O contracts. Build order: Daksh → Aarya → Mitra → Medha.
- **Registry:** `config/agent_registry.yaml` is the single source of truth for every agent's ID, position, title, department and manager, taken from the PDF canonical registry. `python -m scripts.seed_agents` reconciles the database with it, and `tests/test_registry.py` fails if the code drifts from it.

## Next Steps (per build plan)

1. **Stage 1B** — 14 technology service agents (service-first, mostly no LLM)
2. **Stage 1C** — 12 assurance agents
3. **Phase 1** — Daksh, Aarya, Mitra, Medha (P1 pilot leadership)
4. **Website** — frontend control room (Dashboard, Positions, Tokens, Approvals, Findings)
