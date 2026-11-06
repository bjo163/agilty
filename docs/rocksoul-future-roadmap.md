# ROCKSOUL Roadmap — Native g4f UI Replacement

This roadmap is intentionally UI-first. g4f remains the runtime and API authority. No second gateway, provider registry, model catalog, routing engine or inference service is in scope.

## P0 — Scope and compatibility

- [x] Establish ROCKSOUL as the g4f UI replacement, not a control plane or gateway.
- [x] Define runtime/UI responsibility boundaries.
- [x] Classify Arena, Mesh, WorkItem, WorkGraph and evidence modules as optional engineering/operator utilities.
- [ ] Inventory all current GUI routes, HTML assets, API endpoints, cookies, sessions and provider-login flows.
- [ ] Add a documented UI bundle mount point and a legacy fallback switch.
- [ ] Define a route parity matrix with owners and automated checks.

## P1 — ROCKSOUL shell and chat

- [x] Build the initial bundled chat-first ROCKSOUL shell with desktop/mobile layout.
- [x] Mount the initial frontend through the existing g4f GUI serving layer; / and /chat/ select it by default with ROCKSOUL_UI_ENABLED=0 rollback.
- [ ] Complete visual/product parity, accessibility review and installed-wheel deployment verification.
- [ ] Preserve the existing g4f API and Python SDK contracts.
- [x] Implement initial incremental SSE text streaming using the existing g4f chat completions API; real-provider and disconnect/cancellation regression tests remain open.
- [ ] Preserve browser disconnect/cancellation behavior where supported by the backend.
- [ ] Implement conversation creation, switching and history using existing g4f session behavior.
- [ ] Populate model/provider selectors from live runtime metadata.
- [ ] Implement composer, generation controls, errors, retry affordances and loading states.
- [ ] Support existing attachments and modalities progressively, based on actual backend support.

## P2 — Existing GUI parity

- [ ] Port settings and locale controls without changing runtime configuration semantics.
- [ ] Port provider discovery/details and provider login entry points.
- [ ] Port status, logs and usage diagnostics as secondary screens.
- [ ] Preserve playground, apps, media and other supported routes or provide explicit links.
- [ ] Test deep links, browser refresh, cookies, cache headers and static assets.
- [ ] Provide dark/light themes, keyboard shortcuts, accessibility and reduced-motion support.

## P3 — Deployment and cutover

- [ ] Bundle the ROCKSOUL UI with the existing g4f Python application.
- [ ] Keep Docker Compose/Coolify deployment to one primary g4f runtime service for chat.
- [ ] Verify clean install, persistent data, provider login and restart behavior.
- [ ] Switch / and /chat/ to ROCKSOUL only after parity tests pass.
- [ ] Keep an explicit legacy UI rollback path for at least one release.
- [ ] Remove old HTML assets only after parity and compatibility certification.

## P4 — Quality gates

- [ ] Existing g4f Python/API/SDK tests pass unchanged.
- [ ] UI tests cover streaming, cancellation, history, model selection and error states.
- [ ] Playwright smoke tests cover desktop and mobile layouts.
- [ ] Security checks confirm no provider secrets reach browser bundles or logs.
- [ ] Docker build and Coolify-compatible Compose validation pass.
- [ ] Exact final main commit has green required CI before declaring cutover complete.

## Optional modules (not core product scope)

Arena, Mesh, WorkItem, WorkGraph, verifier/evidence stores and the operator console may remain as independent developer/operator modules. They are not dependencies of chat, are not required for startup, and must not be presented as the ROCKSOUL product's defining architecture.
