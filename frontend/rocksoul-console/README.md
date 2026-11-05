# ROCKSOUL Console (Next.js)

New product frontend; the existing g4f HTML GUI remains available for compatibility during migration.

## Requirements
- Node.js 20.9+ (Node 24 recommended)
- ROCKSOUL API reachable from the Next.js server (default http://127.0.0.1:8765)

## Development
```bash
npm install
# Optional: ROCKSOUL_API_INTERNAL_URL=http://127.0.0.1:8765
npm run dev
```
Open http://localhost:3000.

## Production
```bash
npm run build
npm start
```

Set `ROCKSOUL_API_INTERNAL_URL` on the Next.js server. Browser calls use same-origin `/api/*` rewrites; no CORS wildcard is needed. Never put `ROCKSOUL_API_KEY` or secrets in `NEXT_PUBLIC_*` variables.

## Foundation scope
- System status and inventory metrics
- Provider health/state table
- Read-only route explanation
- Responsive dark operator console

Execution controls, Mesh operations, Arena evidence, auth/session management, localization, and full legacy GUI parity remain staged follow-ups. No legacy g4f GUI files are removed.
