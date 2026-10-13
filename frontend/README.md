# The Back Desk (dashboard)

React + Vite + TypeScript dashboard for the Campus Customs agent team. It talks
directly to the desk server (`backend/main.py`); there is no proxy.

## Install and start

```bash
npm install
npm run dev
```

`npm run dev` serves the app on http://localhost:5173 (the port is fixed with
`strictPort`, because the backend's CORS list allows exactly that origin) and
opens the browser. Start the backend first, from the `backend/` folder:
`uvicorn main:app --reload --port 8000`.

Other scripts:
- `npm run build`: strict type-check and production build.
- `npm run lint`: oxlint, with warnings treated as errors.
- `npm test`: unit tests for the pure logic.

## Environment variable

One variable, `VITE_API_BASE`: the desk server URL (default
`http://localhost:8000`). Copy `.env.example` to `.env` to change it. The front
end needs no API keys.

## Viewing a finished run

Open `http://localhost:5173/?run=<run_id>` (for example `?run=124ecff114e0`) to
see one finished run read-only: its agents, routing slip, memo, time cards and
event log, loaded from the desk server's memory with GET requests only. Ticket
stamps, approvals, drafts and the till always show the desk as it is now. Run
records live in memory, so this only works until the backend restarts.
