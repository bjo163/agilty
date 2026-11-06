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
- Usage analytics use `/backend-api/v2/stats`; recent logs use `/backend-api/v2/log`.
- Agent/browser discovery and confirmed tool invocation use the existing `/backend-api/v2/webmcp/tools` registry; only tools actually advertised by g4f are shown, and every invocation requires a browser confirmation.
- Apps use the existing `/pa/providers` registry.
- Private utilities use the existing guarded `/backend-api/v2/upload_cookies` endpoint; ROCKSOUL does not read or display cookie contents.
- Chat and playground use the existing `/v1/models` and `/v1/chat/completions` endpoints.
- Legacy handlers remain available when `ROCKSOUL_UI_ENABLED=0`.
- File/media delivery, `/dist/*`, API routes, nested non-HTML assets beneath legacy GUI paths, and historical `/v<version>/*` snapshots are not rewritten.
- Bundled assets remain part of Python package data and canonical deployment remains the existing single g4f Python service.

## Remaining feature parity / certification

The primary page routes now render the ROCKSOUL shell, but a route migration is not proof of complete feature parity. These capabilities still require implementation or verification where applicable:

- Server persistence is opt-in through **Share chat** and the existing `/backend-api/v2/chat/<id>` API. Private chats remain browser-local by default. Anyone with a shared URL can read its contents; do not share secrets or credentials.
- Image/audio/video attachments are submitted through the existing multipart `/backend-api/v2/conversation` endpoint. Rich rendering of returned image/audio/video and document extraction/upload parity still require completion.
- Provider detail now exposes the existing OAuth/login, quota, and health endpoints when the provider advertises login support; device-flow polling and provider-specific credential UX still require verification.
- WebMCP calls require an explicit browser confirmation and outcome metadata is recorded through the existing `/backend-api/v2/log` endpoint. Fine-grained permissions, durable approval policies, and audit search/filter UX remain out of scope for the UI-only cutover.
- Full browser research/navigation workflow; the Browser page only displays capabilities advertised by WebMCP.
- Complete legacy Apps/private sub-page interaction parity beyond the migrated primary surfaces.
- Keyboard focus-visible and reduced-motion/contrast affordances are present; full screen-reader, contrast, responsive QA, and Indonesian/English localization are not yet certified.
- Real-provider end-to-end streaming and upstream disconnect behavior.
- Successful GitHub Actions runs on the exact final `main` commit. Current GitHub Actions runs are queued; no green result is claimed.
- CI checks wheel assets, Compose configuration, and builds a Docker image with bundled ROCKSOUL asset verification. A live Coolify deployment/runtime smoke test still requires a reachable deployment environment.

## Route inventory

See [rocksoul-ui-route-inventory.md](rocksoul-ui-route-inventory.md) for the primary route map, preserved non-page routes, data sources, and rollback contract.

## Acceptance checks

- [x] One existing g4f Python runtime; no second inference service.
- [x] Unified ROCKSOUL shell mounted through the existing g4f GUI server.
- [x] Primary live GUI page routes are served by ROCKSOUL by default.
- [x] Existing g4f APIs are used for models, chat, providers, status, stats, logs, tools, apps, and guarded private upload.
- [x] Legacy page handlers can be restored with `ROCKSOUL_UI_ENABLED=0`.
- [x] Flask route tests added for the migrated page handler families.
- [x] Playwright mocked-browser tests added for all migrated workspace sections.
- [ ] Automated route and browser workflows pass on the exact final `main` commit; GitHub Actions is currently queued and cannot yet be certified.
- [ ] Real-provider streaming and provider authentication are verified.
- [ ] Full interaction parity, localization, and accessibility review pass.
- [x] CI validates Compose configuration and builds the canonical Docker image with bundled ROCKSOUL assets.\n- [ ] A live Coolify deployment/runtime smoke test is verified.

## Important boundary

ROCKSOUL is the new UI for the primary live GUI surfaces. This does not mean every historical HTML file or arbitrary content URL has been deleted. Legacy templates remain as rollback and compatibility material until the live deployment and parity gates are certified. Do not remove them early or describe mock-browser tests as live-provider certification.
