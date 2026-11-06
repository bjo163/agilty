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
- Private utilities use the existing `/backend-api/v2/upload_cookies` endpoint; ROCKSOUL does not read or display cookie contents. The existing handler only applies a loopback restriction when G4F_API_KEY is absent and does not validate a per-request key in that handler. The UI therefore no longer presents a misleading API-key field; protect remote access at the network/reverse-proxy layer.
- Chat and playground use the existing `/v1/models` and `/v1/chat/completions` endpoints.
- Legacy handlers remain available when `ROCKSOUL_UI_ENABLED=0`.
- File/media delivery, `/dist/*`, API routes, nested non-HTML assets beneath legacy GUI paths, and historical `/v<version>/*` snapshots are not rewritten.
- Bundled assets remain part of Python package data and canonical deployment remains the existing single g4f Python service.

## Remaining feature parity / certification

The primary page routes now render the ROCKSOUL shell, but a route migration is not proof of complete feature parity. These capabilities still require implementation or verification where applicable:

- Server persistence is opt-in through **Share chat** and the existing `/backend-api/v2/chat/<id>` API. Private chats remain browser-local by default. Anyone with a shared URL can read its contents; do not share secrets or credentials.
- Image/audio/video attachments are submitted through the existing multipart `/backend-api/v2/conversation` endpoint. Rich rendering of returned image/audio/video and document extraction/upload parity still require completion.
- Private chat snapshots are not sent to the server until the user explicitly shares them. A regression test now asserts that private conversations do not create server snapshots and that a failed share does not copy a dead link.
- Provider detail now exposes the existing OAuth/login, quota, and health endpoints when the provider advertises login support; device-flow polling and provider-specific credential UX still require verification.
- The ROCKSOUL tool runner asks for a browser confirmation and records metadata-only outcomes through `/backend-api/v2/log`. This confirmation is a UI affordance, not server-side authorization: the existing `/backend-api/v2/webmcp/tools` endpoint accepts direct calls, and the MCP server does not enforce this browser confirmation. Do not expose tool execution to untrusted networks without upstream authentication/network restrictions. The log endpoint is also directly writable; these events are not a tamper-proof audit trail.
- Full browser research/navigation workflow; the Browser page only displays capabilities advertised by WebMCP.
- Complete legacy Apps/private sub-page interaction parity beyond the migrated primary surfaces.
- Keyboard focus-visible and reduced-motion/contrast affordances are present; full screen-reader, contrast, responsive QA, and Indonesian/English localization are not yet certified. External Google Fonts loading was removed so the UI does not depend on a third-party font host.
- Real-provider end-to-end streaming and upstream disconnect behavior.
- Successful GitHub Actions runs on the exact final `main` commit. Current GitHub Actions runs are queued; no green result is claimed.
- CI checks wheel assets, Compose configuration, and builds a Docker image with bundled ROCKSOUL asset verification. A live Coolify deployment/runtime smoke test still requires a reachable deployment environment.


## Security and privacy review notes

- **Private chat:** the UI keeps ordinary chat in browser storage. Only an explicit Share chat action writes a snapshot to the existing g4f chat bucket. The backend GET/POST share endpoints do not implement per-user authorization; a share ID is a bearer link, and anyone who knows it can read or replace that snapshot. Treat links as public secrets.
- **WebMCP tools:** the browser confirmation is not a security boundary. The backend WebMCP route accepts direct tool calls and does not verify that a user confirmed them in ROCKSOUL. Use only behind a trusted private network or authenticated reverse proxy until the existing backend provides authorization.
- **Cookie/HAR upload:** the existing upload handler's remote-access condition checks whether G4F_API_KEY is configured, but does not compare a supplied request key in that handler. ROCKSOUL removed the ineffective API-key input and warns operators to restrict this endpoint at the network/reverse-proxy layer.
- **Tool audit:** metadata-only events are sent to the existing log endpoint. The endpoint is directly writable and does not provide tamper-proof audit guarantees.
- **Extension links:** PA-provider links are restricted to same-origin relative paths or HTTP(S); javascript: and other active URL schemes are rejected.
- **Offline deployment:** UI CSS no longer imports Google Fonts; it uses system font stacks.

## Route inventory

See [rocksoul-ui-route-inventory.md](rocksoul-ui-route-inventory.md) for the primary route map, preserved non-page routes, data sources, and rollback contract.

## Acceptance checks

- [x] One existing g4f Python runtime; no second inference service.
- [x] Unified ROCKSOUL shell mounted through the existing g4f GUI server.
- [x] Primary live GUI page routes are served by ROCKSOUL by default.
- [x] Existing g4f APIs are used for models, chat, providers, status, stats, logs, tools, apps, and guarded private upload.
- [x] Legacy page handlers can be restored with `ROCKSOUL_UI_ENABLED=0`.
- [x] Flask route tests added for the migrated page handler families.
- [x] Playwright mocked-browser tests added for all migrated workspace sections, including private-chat persistence and failed-share regression assertions.
- [ ] Automated route and browser workflows pass on the exact final `main` commit; GitHub Actions is currently queued and cannot yet be certified.
- [ ] Real-provider streaming and provider authentication are verified.
- [ ] Full interaction parity, localization, and accessibility review pass.
- [x] CI validates Compose configuration and builds the canonical Docker image with bundled ROCKSOUL assets.
- [ ] A live Coolify deployment/runtime smoke test is verified.

## Important boundary

ROCKSOUL is the new UI for the primary live GUI surfaces. This does not mean every historical HTML file or arbitrary content URL has been deleted. Legacy templates remain as rollback and compatibility material until the live deployment and parity gates are certified. Do not remove them early or describe mock-browser tests as live-provider certification.
