# ROCKSOUL UI — Finalization Status

Date: 2026-11-06

## Product contract

ROCKSOUL is the replacement web UI for the existing g4f Python runtime. It is not a gateway, router, provider registry, model registry, inference engine, or required control plane.

- g4f Python remains the source of truth for provider/model discovery, execution, streaming, tools, media, sessions, and public APIs.
- ROCKSOUL owns presentation, interaction, navigation, accessibility, localization, and visual identity.
- The optional Next.js operator console and Arena/Mesh/WorkItem/WorkGraph/evidence modules are not required for ordinary chat.

## Implemented in the repository

- Bundled UI assets: `g4f/gui/rocksoul/index.html`, `app.css`, `app.js`.
- Existing GUI server serves the app shell on `/` and `/chat/` by default.
- `/rocksoul-assets/<path>` serves packaged assets.
- Model list is read from the existing `GET /v1/models` endpoint.
- Chat uses the existing `POST /v1/chat/completions` streaming endpoint.
- Browser-local conversation history and dark/light theme preference.
- Legacy UI rollback is supported with `ROCKSOUL_UI_ENABLED=0`.
- Assets are declared in Python package data in `setup.py`.
- Canonical deployment remains the single g4f Python service in `docker-compose.yml`; `docker-compose.rocksoul.yml` is optional operator tooling.

## Not certified / still open

- Server-backed g4f conversation/session persistence.
- Attachments and upload parity.
- Provider login/cookie-management UX parity.
- Rich tool-call and media response rendering.
- Settings, logs, diagnostics and provider page visual parity.
- Indonesian/English UI translations.
- Full keyboard, screen-reader, contrast and responsive QA.
- Automated route tests for UI enabled/disabled, asset traversal and installed package.
- Browser tests for streaming edge cases, cancellation/disconnect and reload.
- Real-provider end-to-end streaming test on exact candidate commit.
- Wheel and Docker image package-asset verification.
- Coolify deployment smoke test.

## Cutover policy

The initial ROCKSOUL UI is mounted by default, with the legacy UI retained as a rollback path. Do not delete legacy assets or claim full UI parity until every open release gate above is tested on the exact final main commit. A successful operator-console build does not count as ROCKSOUL UI certification.

## Acceptance checks

- [x] One existing g4f Python runtime; no second inference service.
- [x] ROCKSOUL app shell served by existing g4f GUI server.
- [x] Existing g4f model and chat API endpoints used.
- [x] Legacy UI rollback switch exists.
- [ ] Automated route and package tests pass.
- [ ] Real-provider streaming and browser regression checks pass.
- [ ] UI parity and accessibility review passes.
- [ ] Canonical Compose/Coolify deployment is verified.
