# NetSleuth UI

Next.js 16 app, exported as static files (`out/`) that the NetSleuth backend serves on its own port. It talks to the backend through the v1 API in [`docs/API_CONTRACT.md`](../docs/API_CONTRACT.md).

## Scripts

| Command | What it does |
|---|---|
| `npm run dev:mock` | Dev server on :3000 with a built-in fake API. No backend needed. |
| `npm run dev` | Dev server on :3000 that proxies `/api` to `BACKEND_URL` (default `http://localhost:5000`). Start the backend with `--dev` so it accepts changes from :3000. |
| `npm run build` | Static export to `out/`. The backend picks it up automatically. |
| `npm run check` | Type check, lint and unit tests. |

## Layout

- `src/app/`: pages: Devices (`/`, the drawer opens with `?device=<mac>`), Activity, Settings
- `src/lib/api.ts`: typed client. `guards.ts` reshapes responses so bad data can't crash a page.
- `src/lib/mock.ts`: the fake API used by `dev:mock`. All of its data is invented.
- `src/context/LiveContext.tsx`: one live connection per tab: a server-sent event stream, with polling while the stream is down and the tab is visible
- `src/hooks/useResource.ts`: fetch, cancel and refresh logic shared by every page
