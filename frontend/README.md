# PRAMANA frontend (Ritwik)

Owned by frontend. See `docs/IMPLEMENTATION_PLAN.md` §7 for the full spec.

Stack: Vite + React 19 + TypeScript + Tailwind + TanStack Query + Zustand + pdfjs-dist +
@xyflow/react + Recharts + i18next + vite-plugin-pwa + MSW + openapi-typescript.

Runs against `contracts/fixtures/` in mock mode (`VITE_API_MODE=mock`) or the live backend
(`VITE_API_MODE=live`). Types are generated from `contracts/openapi.yaml` via `make types`.

Not yet scaffolded — placeholder for M0 frontend setup.
