# CoverYield web

The CoverYield frontend: Next.js (App Router), TypeScript and Tailwind CSS.
It talks to the FastAPI backend in [`../api`](../api) through `/api/*`, which
`next.config.ts` proxies to `API_URL` (default `http://127.0.0.1:8000`).

```bash
npm install
npm run dev        # http://localhost:3000 (start the API first)
npm run lint
npm run typecheck
npm run gen:api    # regenerate src/lib/api-types.ts from the API's OpenAPI schema
```

`src/lib/api-types.ts` is generated from the backend's Pydantic models, so the
request and response types stay in sync with the API.
