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
- Agent/browser discovery uses the existing `/backend-api/v2/webmcp/tools` registry; only tools actually advertised by g4f are shown.
- Apps use the existing `/pa/providers` registry.
- Private utilities use the existing guarded `/backend-api/v2/upload_cookies` endpoint; ROCKSOUL does not read or display cookie contents.
- Chat and playground use the existing `/v1/models` and `/v1/chat/completions` endpoints.
- Legacy handlers remain available when `ROCKSOUL_UI_ENABLED=0`.
- File/media delivery, `/dist/*`, API routes, and historical `/v<version>/*` snapshots are not rewritten.
- Bundled assets remain part of Python package data and canonical deployment remains the existing single g4f Python service.

## Remaining feature parity / certification

The primary page routes now render the ROCKSOUL shell, but a route migration is not proof of complete feature parity. These capabilities still require implementation or verification where applicable:

- Server-backed conversation/session persistence; current chat history is browser-local.
- Full attachment/upload workflow in chat and rich image/audio/video/media rendering.
- Full provider login/OAuth UX and provider-specific quota/health controls.
- Executable agent tool invocation UX with explicit permissions/confirmation; current Agent/Browser pages are registry/discovery views.
- Full browser research/navigation workflow; the Browser page only displays capabilities advertised by WebMCP.
- Complete legacy Apps/private sub-page interaction parity beyond the migrated primary surfaces.
- Indonesian/English translations and full keyboard, screen-reader, contrast, reduced-motion, and responsive QA.
- Real-provider end-to-end streaming and upstream disconnect behavior.
- Successful GitHub Actions runs on the exact final `main` commit.
- Built wheel and Docker image asset verification plus canonical Compose/Coolify runtime smoke test.

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
- [ ] Automated route and browser workflows pass on the exact final `main` commit.
- [ ] Real-provider streaming and provider authentication are verified.
- [ ] Full interaction parity, localization, and accessibility review pass.
- [ ] Canonical Compose/Coolify deployment is verified.

## Important boundary

ROCKSOUL is the new UI for the primary live GUI surfaces. This does not mean every historical HTML file or arbitrary content URL has been deleted. Legacy templates remain as rollback and compatibility material until the live deployment and parity gates are certified. Do not remove them early or describe mock-browser tests as live-provider certification.
