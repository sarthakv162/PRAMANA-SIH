# PRAMANA frontend

React 19, TypeScript, Vite, TanStack Query, and MSW. API request types are in `src/api/types.ts`; generated OpenAPI types are in `src/api/types.gen.ts`; fixtures live in `../contracts/fixtures`.

## Run

Requires Node 22 or newer.

```bash
npm ci
npm run dev                 # VITE_API_MODE defaults to mock/MSW
VITE_API_MODE=live npm run dev  # same-origin /v1 proxy to localhost:8000
```

For the connected demo, use the root Docker Compose workflow instead: `cd ..`, copy `.env.example` to `.env`, and run `make up`. The app's Mock data/Live API status is read from the backend `/v1/health` response, so it reflects server mode rather than the Vite build flag.

MSW fixtures are explicitly illustrative. In isolated frontend mock mode, Markdown dossier export is available; PDF and DOCX export run through the fixture-backed backend renderers. The source PDF isn't included, so evidence drawers fall back to the verbatim text panel.

## Checks and contracts

```bash
npm run lint
npm test
npm run test:e2e
npm run build
npm run types:generate   # after `make contracts` at repository root
```

Contract changes should update the Pydantic schema, fixture, `contracts/CHANGELOG.md`, and generated OpenAPI types together.
