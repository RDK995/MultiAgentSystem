# Frontend Visualizer

React + TypeScript + Vite dashboard for live agent-flow visualization.

## Frontend Structure

- `src/App.tsx`
  - composition shell only.
- `src/features/runs/`
  - `RunControls.tsx` run lifecycle controls.
- `src/features/events/`
  - `eventReducer.ts` and `eventStore.ts` for event-driven state updates.
  - `useLiveEventStream.ts` snapshot bootstrap + SSE subscription lifecycle.
  - selectors for profitable-item and report-artifact extraction.
- `src/features/agents/`
  - `AgentFlow.tsx` live flow rendering.
- `src/features/artifacts/`
  - `ReportLink.tsx` report artifact link rendering.
- `src/shared/api/`
  - `runClient.ts` run/snapshot API calls.
  - `eventClient.ts` SSE subscription with reconnect + cursor policy.
- `src/shared/contracts/`
  - `eventContracts.ts` frontend event/status contract mirror.

## Contract Sync

- Backend canonical contract: `../src/uk_resell_adk/contracts/events.py`
- Frontend mirror: `src/shared/contracts/eventContracts.ts`
- Drift test runs in backend CI: `tests/contracts/test_frontend_event_contract_sync.py`

## Run

```bash
npm install
npm run dev
```

Set backend URL if needed:

```bash
export VITE_API_BASE_URL="http://127.0.0.1:8008"
```

## Tests

Unit/integration:

```bash
npm run test -- --run
npm run test:coverage
```

Build validation:

```bash
npm run build
```

Playwright E2E:

```bash
npx playwright install chromium
npm run e2e
```
