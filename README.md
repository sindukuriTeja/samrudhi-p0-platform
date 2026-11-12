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

A project runs the documented chain in `config/project_flows.yaml`, taken from
"How a Project Runs" and the PDF pilot sequence (Document 01C §7): 10 blocks from the start
check (Adhikar) and kick-off (Arjun, Samanvay) through client understanding (Mitra, Smriti,
Shruti), delivery planning (Daksh, Yojana, Sankalan, Samay, Niyojan, Kshamata, Vitaran,
Pravartan), content decisions (Aarya, Anvesh, Disha, Kalpana, Tarangini), production (Lekha,
Roop, Chitra), checks (Shuddhi, Pariksha, Gunvatta, Swasthya, Gopniya, Nirikshan, Pramaan,
Sweekriti), publishing, measurement and close (Arjun's final brief).

- Model steps run the agent through the existing `run_agent_task` Celery task; code steps run the
  agent's own authority-guarded tool (work packages, schedule, assignments, claim screening,
  privacy check, acceptance, cost); steps with no real data yet are recorded as skipped with
  the reason.
- Checkers send work back: Punargathan opens a rework round, Lekha/Roop/Chitra run again and
  every check repeats; after 3 rounds a human decides.
- Human Gate 1 after Tarangini (direction and calendar) and Gate 2 after Sweekriti (final
  content). "Approve with changes" re-runs the documented steps with your note.
- The runner refuses agents that are not Active and checks every step's permission. The start
  screen can run the existing activation gate for all missing agents in one click (signed-in
  founder or assurance lead); agents that fail the gate stay inactive.

Structured outputs: every model step returns one JSON object in the shape given by its
`output` schema in the flow file (Ollama JSON mode). The runner validates it in code (fields,
types, one item per post), asks the agent once more with the exact problems if it is wrong, and
stops the step after a second failure. The next agents receive the whole structured record, the
code checks read the posts' text from it, and values the model must not decide are set in code
(research facts stay "not verified" until a live source connector exists). Each record is also
saved to the agent's register: initiatives, actions, workflow_instances (Daksh's state machine
from planning to delivered), work_packages, allocations, content_strategies, content_calendars,
content_packages, qa_reviews, approval_workflows, client_communications, reports and briefs.

Planning drives production: Sankalan's work packages, Samay's due dates, Kshamata's capacity
check and Vitaran's assignments decide who produces what. Vitaran assigns a package only to
agents that are Active and under `max_per_agent`; Pravartan turns the assignments into the
production plan, and each producer (Lekha, Roop, Chitra) receives exactly its packages and must
return one item per package. A producer with no packages is skipped.

Safety rules in code (`config/safety_rules.yaml`, matched by `backend/core/safety_rules.py`; no
model decides them). Global rules apply to every client; a client's block can add forbidden
claims, patterns and required disclaimers, never remove a global one.
- Lekha and Shuddhi are given the client's rules, but the code still checks the result.
- Shuddhi: after the model's review, forbidden claims, forbidden patterns (cure claims, "best
  hospital", guarantees, "stop your medication"…), other clients' names and figures that are not
  in Anvesh's research pack force a send-back, even if the model said pass.
- Gunvatta: every post has headline, caption and call to action filled in, no repeated
  captions, captions within the length limit.
- Swasthya: forbidden claims and patterns in every post and in the artwork text, and the
  client's required disclaimer on every post.
- Gopniya: personal data and the names of the other clients.
- Prakash (release guard): schedules only if a signed-in human approved Gate 2 and a fresh
  check of the final copy finds nothing; otherwise the project stops for a human.
- Any failed check sends the work back through Punargathan; after `max_rework_rounds` (3) a
  human decides. The rules for a client: `GET /api/projects/safety-rules?client_id=…`.

Real information (Knowledge page, `#/knowledge`; settings in `config/knowledge.yaml`):
- Client knowledge store (`client_profiles`): brand voice, audience, services, locations, key
  messages. Smriti's step is code: it loads the approved profile and the client's rules. A client
  with no approved profile stops at Smriti with the reason; nothing is invented.
- Source library (`knowledge_sources`): a signed-in person adds a page (fetched from an allowed
  https health site, or pasted text). Fetching refuses other sites, private and local addresses,
  unsafe redirects, non-web files and pages over 2 MB. Agents never fetch or browse.
- Four-eyes rule in code: a profile edit or a new source is a draft until a *different*
  signed-in person approves it (roles in `config/knowledge.yaml`); any edit resets the approval.
- Anvesh receives only the approved passages that match the project and must cite a
  `source_id` and an exact `quote` per fact. His guarded `verify_facts` tool marks a fact
  verified only if the quote is in that approved source and the fact's figures are in the quote;
  title, publisher and link come from the library. Shuddhi accepts a figure in a post only if
  it is in a verified fact.
- Finding new client hospitals (Khoj, Sampark, Lakshit) is Phase 6 Sales work and not built.

API: `GET/PUT /api/knowledge/clients/{id}`, `POST /api/knowledge/clients/{id}/approve`,
`GET/POST /api/knowledge/sources`, `POST /api/knowledge/sources/fetch`,
`POST /api/knowledge/sources/{id}/approve|retire`, `GET /api/knowledge/search?q=`.
Migration `0003_knowledge.py` adds the two tables.

New tables (Alembic migration `migrations/versions/0001_project_tables.py`):
`projects`, `project_messages`, `project_steps`, `approval_decisions`;
migration `0002_step_result_json.py` adds `project_steps.result_json`.

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
