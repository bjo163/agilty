# ROCKSOUL Console

The Next.js operator console is the product-facing control plane for the existing g4f/ROCKSOUL runtime. It does not implement provider adapters or duplicate the runtime.

## Requirements

- Node.js 24 (Node.js 20.9+ is supported)
- Python environment with the repository's `rocksoul-api` extra installed
- ROCKSOUL API reachable from the Next.js server (default: `http://127.0.0.1:8765`)

## Local development

```bash
npm install
# Start the API separately, then:
npm run dev
```

Open `http://localhost:3000/login`.

## Production build

```bash
npm install
npm run lint
npm run build
npm start
```

The production server listens on `PORT` and `HOSTNAME` (default Next.js values). The standalone output is used by the production start script and container image.

## Required runtime environment

| Variable | Purpose |
| --- | --- |
| `ROCKSOUL_API_INTERNAL_URL` | Private URL of the ROCKSOUL API; default `http://127.0.0.1:8765` |
| `ROCKSOUL_API_KEY` | Server-side API key; never expose through `NEXT_PUBLIC_*` |
| `ROCKSOUL_CONSOLE_ADMIN_PASSWORD` | Administrator login password |
| `ROCKSOUL_CONSOLE_OPERATOR_PASSWORD` | Operator login password |
| `ROCKSOUL_CONSOLE_SESSION_SECRET` | HMAC session signing secret; minimum 32 characters |
| `ROCKSOUL_CONSOLE_ADMIN_ID` | Stable configured principal ID for signed administrator approvals |
| `ROCKSOUL_CONSOLE_OPERATOR_ID` | Stable configured operator principal ID |
| `ROCKSOUL_APPROVAL_SIGNING_SECRET` | Separate HMAC key shared only by Console server and API; minimum 32 characters |
| `ROCKSOUL_CONSOLE_COOKIE_SECURE` | Optional explicit Secure-cookie override; default is enabled in production |
| `PORT` | Console listen port; default `3000` |

Use unique high-entropy secrets in production. Do not commit real credentials or place secrets in browser-visible variables.

## Authentication and authorization

- Password login creates a signed HTTP-only, SameSite=Strict session cookie.
- Sessions expire after 12 hours.
- Operator sessions may execute bounded requests.
- Administrator sessions may additionally change provider and Mesh control state, and may issue signed approvals for governed WorkItems.
- Approval signatures bind the decision to the immutable WorkItem contract digest, configured administrator principal, timestamp, and one-time nonce. The API enforces a five-minute signature window and records approvals in the hash-chained event ledger.
- High/critical WorkItems cannot transition to `RUNNING` or execute until an approved signature is recorded. Rejections remain visible and do not authorize execution.
- Configure `ROCKSOUL_CONSOLE_ADMIN_ID` and `ROCKSOUL_APPROVAL_SIGNING_SECRET` identically on the Console/API trust boundary, use a distinct high-entropy signing secret, and sign in again after changing principal configuration.
- The server-side proxy checks the session and role before forwarding API calls.
- The ROCKSOUL API key remains on the server and is attached only to upstream POST requests.
- Logout clears the session cookie.

This is a single-instance, environment-configured operator login. The configured principal ID identifies the administrator credential/session, not a verified natural person. It is not SSO, per-person identity proof, multi-tenant identity, or legal non-repudiation.

## Console workspaces

- Overview and recent execution traces
- Provider fleet health and administrator controls
- Explainable routing
- Mesh nodes, leases, and administrator controls
- Arena pack/campaign evidence and integrity verification
- Trace explorer
- Bounded operator execution
- Signed administrator approval for high/critical WorkItems
- Per-criterion evidence diff and metadata-only evidence bundle export

Arena evidence integrity is not a model-quality certification. Reports continue to state `NOT_CERTIFIED` until the separate dataset and methodology requirements are satisfied.

## Docker Compose / Coolify

The repository root contains `docker-compose.rocksoul.yml`, which runs the API and Console as separate services and persists control-plane state in the `rocksoul-data` volume.

Set the required API/session/password/principal/signing environment variables in the Compose environment. `ROCKSOUL_APPROVAL_SIGNING_SECRET` must be the same high-entropy secret for the API and Console, and must be distinct from the API key and session secret. Deploy the Compose file as a Docker Compose application in Coolify or run:

```bash
docker compose -f docker-compose.rocksoul.yml config
docker compose -f docker-compose.rocksoul.yml up -d --build
```

The API is private to the Compose network; only the Console publishes a host port. Both services have health checks. Configure the public domain and TLS at the Coolify proxy layer. A real Coolify deployment still requires target credentials, domain/DNS, and production secrets; CI validates the Compose topology but does not claim a live deployment.

## Verification

```bash
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

The GitHub Actions workflow `.github/workflows/rocksoul-console-ci.yml` runs lint, production build, Playwright Chromium smoke tests, and Docker Compose configuration validation on Node.js 24.

## Compatibility boundary

The legacy g4f HTML routes remain available during migration. Route-by-route parity for every legacy HTML-only screen is tracked separately and is not silently claimed by the Next.js console.
