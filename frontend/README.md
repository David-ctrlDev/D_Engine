# dataprep — frontend

Next.js 16 (App Router) + TypeScript + Tailwind 4 + shadcn/ui. Managed by
[pnpm](https://pnpm.io/).

## Prerequisites

- Node 20+ (we test on 24)
- pnpm 10+ (`corepack enable && corepack prepare pnpm@latest --activate` if
  you have admin; otherwise `npm install -g pnpm` after pointing
  `npm config set prefix` at a user-writable location)
- The backend running on <http://localhost:8000> (see `../backend/README.md`)

## Setup

```bash
cd frontend

# Install dependencies (creates node_modules/ inside this folder).
pnpm install

# Copy the env template and adjust if your backend isn't on :8000.
cp .env.example .env.local

# Start the dev server.
pnpm dev
```

App at <http://localhost:3000>.

## Common commands

```bash
pnpm dev            # Next.js dev server (Turbopack)
pnpm build          # production build
pnpm start          # serve the production build
pnpm lint           # ESLint (with Prettier compatibility shim)
pnpm format         # rewrite files with Prettier
pnpm format:check   # CI-friendly: fail if anything would change
pnpm typecheck      # tsc --noEmit
pnpm test           # vitest run (single pass)
pnpm test:watch     # vitest in watch mode
pnpm test:ui        # vitest UI on http://localhost:51204
```

## Layout

```
src/
  app/                     App Router pages + root layout
  components/
    ui/                    shadcn-generated primitives (button, input, ...)
    theme-provider.tsx     next-themes wrapper
    theme-toggle.tsx       light/dark switcher
    query-provider.tsx     TanStack Query client (per-browser)
  lib/
    api.ts                 fetch wrapper (credentials: "include")
    auth-actions.ts        typed wrappers around /api/v1/auth/*
    utils.ts               cn() helper
  types/
    auth.ts                TypeScript mirrors of the backend Pydantic schemas
tests/
  setup.ts                 testing-library / jsdom hookup
  api.test.ts              smoke tests for the api primitive
```

See [`../docs/architecture.md`](../docs/architecture.md) for the full picture.
