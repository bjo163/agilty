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
| `ROCKSOUL_CONSOLE_COOKIE_SECURE` | Optional explicit Secure-cookie override; default is enabled in production |
| `PORT` | Console listen port; default `3000` |

Use unique high-entropy secrets in production. Do not commit real credentials or place secrets in browser-visible variables.

## Authentication and authorization

- Password login creates a signed HTTP-only, SameSite=Strict session cookie.
- Sessions expire after 12 hours.
- Operator sessions may execute bounded requests.
- Administrator sessions may additionally change provider and Mesh control state.
- The server-side proxy checks the session and role before forwarding API calls.
- The ROCKSOUL API key remains on the server and is attached only to upstream POST requests.
- Logout clears the session cookie.

This is a single-instance, environment-configured operator login. It is not an SSO or multi-tenant identity provider.

## Console workspaces

- Overview and recent execution traces
- Provider fleet health and administrator controls
- Explainable routing
- Mesh nodes, leases, and administrator controls
- Arena pack/campaign evidence and integrity verification
- Trace explorer
- Bounded operator execution

Arena evidence integrity is not a model-quality certification. Reports continue to state `NOT_CERTIFIED` until the separate dataset and methodology requirements are satisfied.

## Docker Compose / Coolify

The repository root contains `docker-compose.rocksoul.yml`, which runs the API and Console as separate services and persists control-plane state in the `rocksoul-data` volume.

Set the five required secrets listed above in the Compose environment. Deploy the Compose file as a Docker Compose application in Coolify or run:

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
