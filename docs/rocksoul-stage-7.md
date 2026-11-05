# ROCKSOUL Stage 7 — Next.js Console Foundation

## Goal
Introduce a new Next.js frontend without deleting or breaking the existing g4f HTML GUI. The console consumes the Stage 6 HTTP API and is a product-facing operator surface.

## Delivered foundation
- Next.js App Router with TypeScript and React 19.
- Responsive dark industrial console shell.
- Live API status and provider inventory.
- Read-only route explanation.
- Same-origin Next.js API rewrites to the private API origin.
- No provider implementation or secrets in the browser bundle.

## Migration boundary
- Existing `g4f/gui/server` HTML routes remain untouched for compatibility.
- New frontend lives in `frontend/rocksoul-console`.
- ROCKSOUL API remains a separate service/process.
- Set `ROCKSOUL_API_INTERNAL_URL` in the Next.js server environment. Never publish `ROCKSOUL_API_KEY` as a frontend variable.

## Remaining Stage 7 work
- Route parity audit for all legacy GUI screens.
- Mesh node/lease views and operator actions.
- Arena suites, campaigns, verification and report views.
- Execution trace explorer and safe operator execution form.
- Authentication/session management, role-based access and audit UI.
- Locale routing and persisted light/dark theme.
- Component, accessibility, browser E2E, responsive and production build gates.
- Docker Compose/Coolify deployment topology and health checks.

The foundation is not a claim that all legacy GUI features have been migrated.
