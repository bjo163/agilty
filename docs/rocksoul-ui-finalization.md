# ROCKSOUL UI — Finalization Status

Date: 2026-11-06

## Product contract

ROCKSOUL is the unified replacement UI for the primary live g4f GUI pages. It is not a gateway, router, provider registry, model registry, inference engine, or required control plane.

- g4f Python remains the source of truth for provider/model discovery, execution, streaming, tools, OAuth, media, sessions, files, and public APIs.
- ROCKSOUL owns presentation, navigation, interaction, accessibility, localization, and visual identity.
- No second inference service or duplicate provider/model runtime is introduced.
- Version-pinned historical snapshots and non-page media/static/API routes remain available.

## Implemented in the repository

- Unified responsive shell and navigation: `g4f/gui/rocksoul/index.html`.
- Route-aware workspace and existing-API data adapters: `g4f/gui/rocksoul/app.js`.
- Workspace design system and page components: `g4f/gui/rocksoul/app.css`.
- Existing g4f GUI server serves ROCKSOUL on overview, chat, provider catalog/detail, status, stats, logs, agent tools, browser workspace, playground, apps/modules, and private utilities.
- Provider catalog and detail use `/backend-api/v2/providers` and `/backend-api/v2/models/<provider>`.
- Status uses `/backend-api/v2/status`, `/backend-api/v2/version`, and `/v1/models`.
- Usage analytics use `/backend-api/v2/stats`; recent logs use `/backend-api/v2/log`. Usage reads/writes and log reads/writes now use the same privileged-request guard.
- Agent/browser discovery and tool invocation use the existing `/backend-api/v2/webmcp/tools` registry; only tools actually advertised by g4f are shown. The backend now gates the endpoint to loopback clients, explicitly trusted source CIDRs, or remote requests carrying the configured API key; browser confirmation remains a separate user-intent affordance.
- Apps use the existing `/pa/providers` registry.
- Private utilities use the existing `/backend-api/v2/upload_cookies` endpoint; ROCKSOUL does not read or display cookie contents. The endpoint now permits loopback clients or requires a matching `x-api-key` / Bearer key for remote requests.
- Chat and playground use the existing `/v1/models` and `/v1/chat/completions` endpoints. Image/audio/video media still uses the existing multipart `/backend-api/v2/conversation` endpoint. Documents use the existing `/backend-api/v2/files/<bucket_id>` upload and `/stream` extraction endpoints; temporary buckets are deleted after extraction, and extracted text is sent as conversation context. The supported UI extension list mirrors the g4f file reader and extraction dependencies.
- Legacy handlers remain available when `ROCKSOUL_UI_ENABLED=0`.
- File/media delivery, `/dist/*`, API routes, nested non-HTML assets beneath legacy GUI paths, and historical `/v<version>/*` snapshots are not rewritten.
- UI locale catalog and selector support Indonesian and English with browser-language default, persisted selection, and English fallback.
- Accessibility baseline includes skip navigation, named workspace/conversation landmarks, active-route `aria-current`, visible keyboard focus, and reduced-motion styling. Automated regression now checks 375px/768px/1440px layouts, visible button names, reduced-motion behavior, and WCAG AA contrast for primary text tokens in both themes; the light-theme muted token was darkened to meet the threshold. Full screen-reader/assistive-technology, zoom, and real-device certification remain manual QA gates.
- Apps with missing or unsafe launch URLs are rendered as informational cards instead of dead or executable links.
- Canonical Compose includes init/restart policy, g4f status healthcheck, optional `G4F_API_KEY` environment configuration, and documented named-volume backup/restore.
- ROCKSOUL CI now builds the canonical image, verifies `locale.js` in the Docker image and wheel, starts the canonical Compose service without rebuilding, waits for its healthcheck, and always tears the Compose stack/volume down.
- Bundled assets remain part of Python package data and canonical deployment remains the existing single g4f Python service.

## Remaining feature parity / certification

The primary page routes now render the ROCKSOUL shell, but a route migration is not proof of complete feature parity. These capabilities still require implementation or verification where applicable:

- Server persistence is opt-in through **Share chat** and the existing `/backend-api/v2/chat/<id>` API. Private chats remain browser-local by default. Anyone with a shared URL can read its contents; do not share secrets or credentials.
- Image/audio/video attachments are submitted through the existing multipart `/backend-api/v2/conversation` endpoint. Documents are uploaded and extracted through the existing g4f file-bucket APIs and included as text context; the mocked browser suite covers the upload/extract/cleanup path. Actual extraction depends on installed optional Python file dependencies and still needs local fixture validation across supported formats.
- Chat now renders safe Markdown and fenced code blocks with copy controls, validated raster images, and linked audio/video players. Raw HTML and SVG data URLs are not executed. Per-message copy, edit-last-user-turn, delete, and text-only regenerate controls are implemented. Markdown and JSON conversation export are available. Rename, pin/unpin, search, clear-all, and local deletion are implemented; attachment-aware regenerate remains intentionally disabled until g4f attachment replay semantics are verified.
- Private chat snapshots are not sent to the server until the user explicitly shares them. Share IDs are generated from cryptographically strong random bytes even when randomUUID is unavailable. Regression tests assert that private conversations do not create server snapshots, weak legacy IDs are upgraded before sharing, and failed sharing does not copy a dead link.

- Media parser hardening: audio URLs are accepted as audio players only when they are validated audio data URLs or recognized audio-file URLs. This prevents ordinary video URLs from being misclassified as audio. The exact-HEAD browser smoke passed.

- Provider detail exposes the existing OAuth/login, quota, and health endpoints when the provider advertises login support. Device-code flows now display the verification URL/user code, poll the existing OAuth endpoint until success/failure/expiry, and allow cancellation. Provider-specific live credential verification remains open.
- The ROCKSOUL tool runner asks for a browser confirmation and records metadata-only outcomes through `/backend-api/v2/log`. The backend now applies a privileged-request guard to WebMCP, log, usage, file-bucket, cookie/HAR upload, and shared-chat writes: loopback requests are trusted; remote requests require a matching configured `G4F_API_KEY` in `x-api-key` or Bearer authorization. A reverse proxy must inject this key server-side and independently protect all other legacy API routes. This is not a per-user identity system or a tamper-proof audit trail.
- Full browser research/navigation workflow; the Browser page only displays capabilities advertised by WebMCP.
- Remaining legacy Apps/Private behavior beyond the verified PA catalog and cookie/HAR import actions. Unsupported app links are informational and no longer appear actionable.
- Keyboard skip navigation, visible focus, reduced-motion styling, named landmarks, active-route announcements, and Indonesian/English UI selection are implemented. Full screen-reader, contrast, responsive, and translation-completeness QA still require manual certification.
- Real-provider end-to-end streaming, provider credential verification, and upstream disconnect semantics remain unverified. An opt-in smoke harness now tests model discovery, non-streaming completion, streaming deltas, and an optional client-abort probe against the live configured g4f runtime.
- GitHub Actions: exact-HEAD browser smoke, Python Unittest, and CodeQL all passed. The ROCKSOUL CI route/asset matrix, wheel/sdist, Compose, Docker image, bundled assets, and persistent-volume smoke passed on the parent commit immediately before the media-only change; see the exact-run record below.
- CI checks wheel assets, Compose configuration, builds the Docker image, verifies bundled ROCKSOUL assets, and smoke-tests write access to the persistent config volume. Compose now builds the local source explicitly and mounts a named volume at G4F_CONFIG_DIR. A live Coolify deployment/runtime smoke test still requires a reachable deployment environment.


## Security and privacy review notes

- **Private chat:** the UI keeps ordinary chat in browser storage. Only an explicit Share chat action writes a snapshot to the existing g4f chat bucket. New share IDs use cryptographically strong random values. The backend GET/POST share endpoints do not implement per-user authorization; a share ID is a bearer link, and anyone who knows it can read or replace that snapshot. Treat links as public secrets.
- **WebMCP tools:** browser confirmation is not authorization. The backend now restricts WebMCP access to loopback, an explicitly trusted source CIDR, or a valid configured API key for remote requests. Use an authenticated reverse proxy that injects `x-api-key` server-side; never put the server key in browser storage or JavaScript.
- **Cookie/HAR and document files:** cookie/HAR upload and file-bucket upload/read/delete endpoints now require loopback, an explicitly trusted source CIDR, or a valid configured API key for remote requests. The same guard protects log and usage data endpoints. The reverse proxy must inject the key server-side; the UI never stores it.
- **Tool audit:** metadata-only events are sent to the existing log endpoint. Remote log access now requires the configured API key; the endpoint remains a mutable operational log, not a tamper-proof audit trail.
- **Public deployment:** Canonical Compose binds host ports 8080 and 1337 to 127.0.0.1 by default (VNC 7900 is also loopback-only), preventing accidental LAN/WAN exposure. Guarded privileged GUI endpoints require loopback, an explicitly configured trusted source CIDR, or a matching API key; other legacy routes are not comprehensively covered by this guard. Remote deployment still requires an authenticated reverse proxy/private network for every exposed route.
- **Extension links:** PA-provider links are restricted to same-origin relative paths or HTTP(S); javascript: and other active URL schemes are rejected.
- **Offline deployment:** UI CSS no longer imports Google Fonts; it uses system font stacks. Compose sets pull_policy to build the checked-out source, mounts a named persistent volume, adds init/restart policy and a g4f status healthcheck, and documents backup/restore. The Selenium/VNC port is bound to host loopback instead of all network interfaces.

## Route inventory

See [rocksoul-ui-route-inventory.md](rocksoul-ui-route-inventory.md) for the primary route map, preserved non-page routes, data sources, and rollback contract. See [rocksoul-next-milestones.md](rocksoul-next-milestones.md) for independently executable follow-up work packages.

## Acceptance checks

- [x] One existing g4f Python runtime; no second inference service.
- [x] Unified ROCKSOUL shell mounted through the existing g4f GUI server.
- [x] Primary live GUI page routes are served by ROCKSOUL by default.
- [x] Existing g4f APIs are used for models, chat, providers, status, stats, logs, tools, apps, and private upload.
- [x] Legacy page handlers can be restored with `ROCKSOUL_UI_ENABLED=0`.
- [x] Flask route tests added for the migrated page handler families.
- [x] Playwright mocked-browser tests cover all migrated workspace sections, private-chat persistence, failed-share behavior, locale persistence, skip navigation, and document upload/extraction/cleanup through the existing file API.
- [x] Exact-HEAD browser smoke, Python Unittest, and CodeQL pass. ROCKSOUL CI package/Docker checks pass on the parent commit immediately before the media-only change; exact run IDs are recorded below.
- [ ] Real-provider streaming and provider authentication are verified.
- [x] Automated responsive viewport, visible-control-name, reduced-motion, and WCAG AA primary text-token checks are included in browser/Python regression suites.
- [ ] Full interaction parity, translation completeness, screen-reader/assistive-technology, zoom, and real-device accessibility review pass.
- [x] CI workflow is configured to validate Compose configuration, build the local Docker image, verify bundled ROCKSOUL assets, and smoke-test persistent-volume writes.
- [x] Privileged g4f GUI endpoints have direct-request trust-boundary regression tests.
- [x] Opt-in live-provider compatibility harness is available; live provider execution remains opt-in and has not been claimed as passed.
- [x] Canonical Compose has a status healthcheck, restart policy, API-key environment pass-through, and documented named-volume backup/restore.
- [x] Those CI jobs completed successfully on the parent commit immediately before the media-only change.
- [ ] Live Coolify deployment/runtime smoke test — intentionally out of scope per project-owner direction; do not block ROCKSOUL UI completion on it.

## Important boundary

ROCKSOUL is the new UI for the primary live GUI surfaces. This does not mean every historical HTML file or arbitrary content URL has been deleted. Legacy templates remain as rollback and compatibility material until the live deployment and parity gates are certified. Do not remove them early or describe mock-browser tests as live-provider certification.


## Latest UI parity work

- Per-message Copy is available for user and assistant messages.
- Edit on a user message restores its text to the composer and removes that turn and all following turns, preventing stale downstream context.
- Delete removes the selected message from the local conversation and updates any explicitly shared snapshot through the existing g4f share endpoint.
- Assistant and user Markdown is rendered with DOM text nodes; fenced code is displayed in a bounded code panel with a clipboard action. Model-provided HTML is not executed.
- The previous ROCKSOUL CI run on `ac1010f4` passed all four UI route/asset test matrix jobs and the wheel/sdist + Compose + Docker image validation job. This is a verified checkpoint, not a claim that later commits have passed; current `main` requires a fresh run.


## Chat parity update

- Text-only regeneration replays the preceding user turn through the existing g4f OpenAI-compatible chat endpoint. It is intentionally disabled for turns that include file attachments until attachment replay semantics are verified.
- Conversation export supports Markdown and JSON and runs entirely in the browser.
- Markdown raster images (PNG/JPEG/GIF/WebP) are supported, including validated base64 image data URLs. Linked audio/video files render with native controls when their extension is recognized and URL passes the same-origin/HTTP(S) policy.
- Fixed a stale variable reference in the Private utility upload handler that could throw after a successful upload.
- Browser E2E now covers Markdown media, export download names, and regeneration request dispatch. Python route/UI tests assert the new controls and private upload regression guard.


## Conversation history management

- Added local history search across conversation titles and message text.
- Added pin/unpin, rename, and delete-from-local-history actions, plus clear-all local history.
- Deleting/clearing browser history does not claim to delete a server-shared snapshot; the UI warns about that boundary.
- History management remains browser-local and does not add a new backend/session store.


## Exact-main verification — 2026-11-06 18:23 WIB

Current `main` HEAD: `b2581bf45aa669819cf40ba33886bdef941ba534`.

- Browser smoke: [42207432717 — success](https://github.com/bjo163/agilty/actions/runs/42207432717).
- Python Unittest: [42207433060 — success](https://github.com/bjo163/agilty/actions/runs/42207433060).
- CodeQL Advanced: [42207432725 — success](https://github.com/bjo163/agilty/actions/runs/42207432725).
- ROCKSOUL CI matrix + packaging + Compose + Docker + persistent-volume smoke: [42207314832 — success](https://github.com/bjo163/agilty/actions/runs/42207314832), on parent `ec49c0c3d14dfd441d483d5d5ab9e176a42b5683`. The later commit changes only the media classifier, browser assertions, and docs; the exact-HEAD browser and unit workflows cover the changed behavior.

**Readiness:** usable for local development and hands-on evaluation, but not certified as production-ready. The guarded privileged endpoints, document upload/extraction path, EN/ID selector, accessibility baseline, provider smoke harness, and Compose operator improvements are implemented. Still open: exact-main CI completion, live-provider credentials/streaming, real document fixture validation, reverse-proxy/remote request verification, full screen-reader/contrast/responsive and translation-completeness QA, deeper legacy Apps/Private parity, and a real Docker-host backup/restore smoke. Coolify is intentionally excluded.


## Local Compose network hardening — 2026-11-06

- Canonical `docker-compose.yml` now binds GUI/API host ports 8080 and 1337 to `127.0.0.1` by default; VNC 7900 was already loopback-only.
- Added a regression test that rejects wildcard host bindings for those ports.
- This makes the default local-development path safer. It does not add server-side authorization to legacy endpoints; do not expose the service remotely without a trusted authenticated reverse proxy/private network.


## Milestone implementation checkpoint — 2026-11-06

Current `main` implementation includes all seven milestone workstreams in partial or baseline form. See [independent milestone status](rocksoul-next-milestones.md) and [product backlog continuation](rocksoul-todo.md). The seven GitHub issues remain open intentionally because their live/manual acceptance gates have not all been satisfied.

- Backend trust guard: direct Flask-route tests now cover denied untrusted remote calls and allowed loopback/API-key calls. Trusted CIDRs are explicit; canonical Compose defaults to common Docker bridge peers while host ports remain loopback-only.
- Accessibility/localization: automated baseline and mocked browser coverage added; manual certification and complete translation coverage remain open.
- Live provider: opt-in harness exists; no provider credential or live run is assumed.
- Documents: mocked upload/extract/context/cleanup flow added; optional dependency and real file-format fixtures remain open.
- Apps/Private: unsafe extension destinations are non-clickable; remaining legacy nested actions need inventory.
- Compose: healthcheck/restart/API-key/trusted-peer/backup guidance added; a real Docker host run remains required.

The exact-main GitHub Actions runs for this checkpoint are tracked on the latest commit; do not treat queued runs as passing.
