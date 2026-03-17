# UK Resell ADK Visualizer

Production multi-agent workflow for sourcing and evaluating UK resale opportunities, with a live frontend for real-time agent execution.

## Architecture

```text
Frontend (React/Vite)
  ├─ shared/api/runClient.ts      -> REST snapshot/start/stop
  ├─ shared/api/eventClient.ts    -> SSE stream with cursor reconnect
  └─ features/events/eventReducer -> reducer-driven stream state
                 │
                 ▼
Backend (ThreadingHTTPServer)
  ├─ api/handlers.py              -> thin route/transport handlers
  ├─ application/run_service.py   -> run lifecycle orchestration
  ├─ application/workflow/*       -> source / profitability / report stages
  ├─ infrastructure/event_store.py-> thread-safe live store + sequence replay
  └─ infrastructure/artifact_store.py -> secure artifact serving
```

## Canonical Event Contract

- Canonical backend contract: `src/uk_resell_adk/contracts/events.py`.
- Frontend mirror constants: `frontend/src/shared/contracts/eventContracts.ts`.
- Drift guard test: `tests/contracts/test_frontend_event_contract_sync.py`.

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Backend visualizer API (127.0.0.1:8008)
PYTHONPATH=src python -m uk_resell_adk.visualizer_server
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Default frontend: `http://127.0.0.1:4173`  
Default backend: `http://127.0.0.1:8008`

## Runbook

1. Start backend server and verify health: `curl http://127.0.0.1:8008/health`.
2. Start frontend and open `http://127.0.0.1:4173`.
3. Click `Start run`.
4. Observe live agent transitions and profitable items as SSE events stream in.
5. Validate report artifact link appears on report agent completion.
6. Start a second run without restarting services (back-to-back reliability path).

## Testing & Quality Gates

Backend:

```bash
pytest
mypy src/uk_resell_adk
```

Frontend unit/integration:

```bash
cd frontend
npm run test -- --run
npm run test:coverage
npm run build
```

Frontend E2E (Playwright):

```bash
cd frontend
npx playwright install chromium
npm run e2e
```

## CI Required Checks

CI workflow: `.github/workflows/ci.yml`

Configure branch protection to require these job checks:

- `backend-tests`
- `backend-typecheck`
- `frontend-tests`
- `frontend-e2e`

These checks enforce:

- backend tests with coverage threshold (`application` + `domain` >= 85%),
- strict backend type-checking,
- frontend coverage threshold (features >= 80%),
- full Playwright lifecycle verification (start run, observe transitions, open report, run again).
