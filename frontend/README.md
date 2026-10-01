# PRAMANA frontend

Vite + React 19 + strict TypeScript frontend for the PRAMANA plan. The API base path is `/v1`; all backend calls live in `src/api/client.ts`, with provisional request/response types centralized in `src/api/types.ts`.

## Run locally

```sh
npm install
npm run dev
```

`VITE_API_MODE=mock` is the default and starts MSW with fixtures in `../contracts/fixtures/provisional.json`. Use `VITE_API_MODE=live` with `VITE_API_BASE_URL` set to the backend `/v1` URL to bypass MSW and call the backend. `VITE_DEMO_KEY` is optional and is sent as `X-Demo-Key` when set. See `.env.example`.

## Contract handoff

The local fixture bundle and `src/api/types.ts` are provisional and based on the frontend requirements and examples in `../PRAMANA_IMPLEMENTATION_PLAN.md`. The values are UI demonstrations, not legal advice or verified corpus content. Reconcile them with backend-owned Pydantic schemas and `../contracts/openapi.yaml` before live integration. Once that OpenAPI file exists, run `npm run types:generate`; then update the single type boundary and fixtures against the generated schema. Screen components should continue to call `src/api/client.ts` and must not depend directly on fixture data.

Some endpoint response details are not fully specified in the plan (notably corpus summary and escalation list item fields). Their minimal provisional frontend shapes are documented in `src/api/types.ts` and require backend confirmation during contract freeze.

## Checks

```sh
npm run lint
npm test
npm run test:e2e
npm run build
```
