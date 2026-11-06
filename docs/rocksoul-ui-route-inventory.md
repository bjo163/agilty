# ROCKSOUL UI — g4f GUI Route Inventory

This inventory defines the live GUI migration boundary. ROCKSOUL is a bundled static frontend served by the existing g4f Python GUI process. It does not add a gateway, provider runtime, model registry, or separate backend.

## Primary GUI pages migrated

| Existing URL | ROCKSOUL workspace | Existing g4f data/API source |
|---|---|---|
| `/`, `/home.html`, `/index.html` | Overview / command center | `/backend-api/v2/status`, `/backend-api/v2/stats` |
| `/chat/`, `/chat/*`, `/chat.html` | Chat workspace | `/v1/models`, `/v1/chat/completions`; media submissions use `/backend-api/v2/conversation`; document upload/extraction uses `/backend-api/v2/files/<bucket_id>` and `/stream`; opt-in shared history uses `/backend-api/v2/chat/<id>` |
| `/providers`, `/providers/`, `/providers.html` | Provider catalog | `/backend-api/v2/providers` |
| `/providers/<name>` | Provider detail, model list, optional login/health/quota controls | `/backend-api/v2/providers`, `/backend-api/v2/models/<provider>`, `/backend-api/v2/oauth/<provider>`, `/backend-api/v2/health/<provider>`, `/backend-api/v2/quota/<provider>` |
| `/status`, `/status/`, `/status.html` | Runtime status and model catalog | `/backend-api/v2/status`, `/backend-api/v2/version`, `/v1/models` |
| `/stats`, `/stats/`, `/stats.html` | Usage and token analytics | `/backend-api/v2/stats` |
| `/logs`, `/logs/`, `/logs.html` | Recent backend events | `/backend-api/v2/log` |
| `/agent`, `/agent/`, `/agent.html` | WebMCP tool registry | `/backend-api/v2/webmcp/tools` |
| `/browser`, `/browser/`, `/browser.html` | Research/browser tool discovery | `/backend-api/v2/webmcp/tools` (only tools actually advertised are shown) |
| `/playground/`, `/playground/*`, `/playground.html` | Prompt experiment workspace | `/v1/models`, `/v1/chat/completions` |
| `/apps/`, `/apps/*`, `/apps.html` | Extension and PA provider catalog | `/pa/providers` |
| `/private/`, `/private/*`, `/private.html` | Private utilities and existing cookie import endpoint | `/backend-api/v2/upload_cookies` |

The existing navigation is unified in `g4f/gui/rocksoul/index.html`; route-aware rendering and data loading live in `app.js`. The shell reuses same-origin APIs and keeps provider execution, authentication, tools, files, and data ownership inside g4f.

## Preserved non-page routes

| Route family | Behavior |
|---|---|
| `/rocksoul-assets/*` | Serves the bundled ROCKSOUL CSS/JS assets |
| `/v1/*`, `/backend-api/*`, `/pa/*` | Existing inference and backend APIs remain unchanged |
| `/media/*`, `/images/*`, `/thumbnail/*`, `/files/*` | Existing media and file delivery remains unchanged |
| `/dist/*` | Existing g4f static distribution assets remain unchanged |
| `/v<version>/*` | Historical version-pinned GUI snapshots remain available and are not rewritten |
| `/headers`, `/country-ip`, `/meta`, `/sitemap.xml` | Existing metadata/diagnostic endpoints remain unchanged |

Nested non-HTML assets requested beneath legacy `/chat/*`, `/apps/*`, `/private/*`, and `/playground/*` paths continue through their existing handlers. Unknown legacy content pages also remain available. The migration targets primary interactive GUI surfaces, not arbitrary upstream content URLs or immutable historical snapshots.

## Workspace behavior

- **Overview:** summarizes live provider/model/request counts using the runtime's status and usage APIs.
- **Chat:** uses the OpenAI-compatible g4f model and streaming endpoints. Normal conversations remain browser-local. The user may explicitly choose Share chat to persist a snapshot through `/backend-api/v2/chat/<id>`; anyone possessing that link can read it. Image/audio/video attachments use the existing multipart `/backend-api/v2/conversation` endpoint. Supported documents are uploaded to the existing g4f file bucket, extracted by the Python runtime, and added to the prompt as text context; temporary buckets are deleted after extraction.
- **Providers:** filters the existing provider registry, loads provider-specific models, and exposes login, health, and quota controls through existing g4f endpoints where supported.
- **Status:** displays runtime version, provider counts, and the current public model catalog.
- **Stats:** displays stored request/token totals and top models/providers with selectable windows.
- **Logs:** reads recent events from the existing backend log endpoint.
- **Agent / Browser:** discovers tools actually advertised by WebMCP. ROCKSOUL asks for per-invocation browser confirmation. The backend also enforces a trust guard: loopback requests are accepted; remote requests require the configured API key. A reverse proxy must inject the key server-side; browser confirmation is not user authentication.
- **Playground:** uses the same chat runtime in a focused prompt experimentation layout.
- **Apps:** lists the existing PA provider registry. Entries with a missing or unsafe launch URL are displayed as informational cards rather than clickable links.
- **Private utilities:** exposes the existing JSON/HAR cookie import endpoint. It never reads or displays cookie contents. Remote cookie/HAR uploads require the configured API key; use an authenticated reverse proxy to inject it server-side.

## Privileged endpoint trust boundary

The existing g4f GUI backend applies a shared trust guard to WebMCP, log, usage, file-bucket upload/read/delete, cookie/HAR upload, and shared-chat writes. Direct loopback requests are accepted; remote requests require the configured `G4F_API_KEY` in `x-api-key` or Bearer authorization. Public shared-chat reads remain bearer-link based by design. This guard is defense in depth, not a replacement for a reverse proxy protecting every legacy route or a per-user identity system.

## Rollback

Set `ROCKSOUL_UI_ENABLED=0` in the existing g4f process environment and restart. Primary GUI routes return to their legacy handlers. The same single Python service remains the canonical deployment.

## Verification requirements

- [x] Route-level tests cover all primary GUI handler families and preserved non-page route registrations.
- [x] Playwright mocked-browser coverage includes overview, chat, shared-history restore/share, media attachment submission, provider login/health/quota, secure share-ID fallback, status, stats, logs, agent tools, browser tool discovery, playground, apps, and private utilities.
- [ ] Run route and browser workflows successfully on the exact final `main` commit.
- [ ] Verify live provider authentication and streaming, including upstream disconnect semantics.
- [x] Add CI checks for built wheel assets, canonical Compose configuration, and Docker image asset inclusion; [ ] wait for the exact-main CI run to complete.
- [x] Add canonical Compose healthcheck, restart policy, optional API-key pass-through, and named-volume backup/restore instructions.
- [ ] Run canonical Docker Compose smoke test on a local host. Coolify testing is intentionally out of scope.
- [x] Add skip navigation, keyboard focus visibility, reduced-motion styling, landmark names, active-route announcements, and persisted Indonesian/English locale selection.
- [ ] Complete keyboard, screen-reader, contrast, responsive, and translation-completeness review.
- [ ] Retire legacy page templates only after the preceding gates pass.

## Product boundary

ROCKSOUL is the UI. g4f Python remains authoritative for provider discovery, model discovery, execution, streaming, OAuth/login, files, media, sessions, and public APIs. Optional operator-console services are not required for these pages.
