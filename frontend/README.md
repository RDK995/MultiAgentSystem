# Agent Activity Visualizer Frontend

This is the first working prototype of the mission-control dashboard described in the root implementation plan.

## What it includes

- React + TypeScript + Vite app scaffold
- cinematic three-panel dashboard layout
- real backend-driven event stream only
- agent cards, event timeline, and inspector panel
- a frontend event contract ready for real backend wiring

## Run locally

```bash
cd /Users/ryankenny/Projects/ADKVisuals/MultiAgentSystem
PYTHONPATH=src python -m uk_resell_adk.visualizer_server

cd frontend
npm install
npm run dev
```

The Vite dev server is configured for `http://localhost:4173`.
The backend stream server runs on `http://127.0.0.1:8008`.

If your backend runs somewhere else, set `VITE_API_BASE_URL` before starting the frontend.

## Integration path

The frontend reads its initial snapshot and live updates from [src/lib/streaming.ts](/Users/ryankenny/Projects/ADKVisuals/MultiAgentSystem/frontend/src/lib/streaming.ts).
It requires the Python SSE backend and does not fall back to mock data.
