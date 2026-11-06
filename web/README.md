# AisleScout web app

Next.js 16 (App Router) + React 19 + Tailwind CSS 4. See the [root README](../README.md) for the full setup.

```bash
npm install
npm run dev    # http://localhost:3000; needs the backend running (python -m aislescout serve --demo)
npm run lint
```

- `app/page.tsx`: page shell (static, prerendered)
- `components/search-app.tsx`: search form, URL state (`?q=&zip=&sale=1`), fetching, result groups
- `components/result-card.tsx`: one deal
- `lib/types.ts`: TypeScript mirror of the backend's Pydantic models
- `next.config.ts`: proxies `/api/*` to the backend (`AISLESCOUT_API_URL`, default `http://127.0.0.1:8000`)

This Next.js version has breaking changes from older releases. Check `node_modules/next/dist/docs/` before changing framework-level code (see `AGENTS.md`).
