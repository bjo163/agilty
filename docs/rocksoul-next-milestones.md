# ROCKSOUL — Independent Next Milestone Plan

Date: 2026-11-06

## Product boundary

ROCKSOUL remains the UI replacing g4f's built-in HTML GUI. The existing g4f Python runtime, provider implementations, model discovery, inference APIs, streaming, tools, OAuth, media handling, and SDK remain authoritative. These milestones improve the UI integration and its safety; none creates a second gateway, router, provider registry, or inference service.

## Execution model

Each milestone below is an independently executable work package. It must be implemented, tested, documented, and closed without requiring another milestone to be completed first. Shared contracts must be preserved, but no milestone should introduce a cross-milestone blocker. Work may be parallelized. A milestone is complete only when its own acceptance criteria and relevant CI checks pass on its final commit.

Priority meanings: P0 = security/release risk; P1 = user-facing parity; P2 = quality and polish.

## Current implementation snapshot — 2026-11-06

The following work has been implemented on `main`, but none of the seven issues is being closed until its remaining acceptance gates pass:

| Milestone | Current state | Tracking |
|---|---|---|
| RS-UI-M01 | Trust guard and regression coverage implemented; exact-main and remote-proxy verification pending | [#25](https://github.com/bjo163/agilty/issues/25) |
| RS-UI-M02 | Accessibility baseline implemented; automated viewport, visible-control-name, reduced-motion, and WCAG AA theme-token checks added; assistive-technology certification pending | [#26](https://github.com/bjo163/agilty/issues/26) |
| RS-UI-M03 | EN/ID selector and initial catalog implemented; translation completeness QA pending | [#27](https://github.com/bjo163/agilty/issues/27) |
| RS-UI-M04 | Opt-in live-provider harness implemented; actual provider run pending | [#28](https://github.com/bjo163/agilty/issues/28) |
| RS-UI-M05 | Existing file API document flow implemented and mocked; real-format fixture validation pending | [#29](https://github.com/bjo163/agilty/issues/29) |
| RS-UI-M06 | Unsafe/missing app actions are non-clickable; deeper legacy parity audit pending | [#30](https://github.com/bjo163/agilty/issues/30) |
| RS-UI-M07 | Compose health/restart/backup guidance implemented; real Docker host smoke pending | [#31](https://github.com/bjo163/agilty/issues/31) |

Evidence and remaining gates are tracked in `docs/rocksoul-todo.md`, `docs/rocksoul-ui-finalization.md`, and the linked issues. "Implemented" is not equivalent to "certified".

## Milestones

### RS-UI-M01 — Backend trust-boundary hardening
- Priority: P0
- Scope: review the existing g4f handlers used by ROCKSOUL for WebMCP invocation, cookie/HAR upload, chat-share read/write, and writable log events. Add server-side authorization using the repository's existing supported auth/configuration mechanisms; do not rely on browser confirmation or UI hiding.
- Deliverables: route-level threat model, narrowly scoped auth/permission checks, negative and positive API tests, operator configuration notes, rollback-safe behavior.
- Acceptance:
  - unauthenticated and unauthorized direct HTTP calls are rejected for privileged operations;
  - valid authorized calls preserve existing supported client behavior;
  - secrets never appear in logs or error responses;
  - tests cover direct API calls, not only browser UI flows;
  - local Compose remains loopback-only by default.
- Independence: can be implemented without UI redesign, localization, or live provider credentials.
- Not included: redesigning the entire g4f authentication system or claiming every legacy API route is protected.

### RS-UI-M02 — Accessibility and responsive certification
- Priority: P1
- Scope: audit the actual ROCKSOUL pages at desktop, tablet, and mobile widths; keyboard-only navigation; focus order/visibility; semantic landmarks and names; screen-reader announcements for streaming/status/errors; contrast; reduced motion.
- Deliverables: reproducible checklist, focused UI fixes, Playwright assertions for deterministic behavior, manual QA notes for checks automation cannot prove.
- Acceptance:
  - all primary pages are navigable by keyboard with no trapped focus;
  - interactive controls have accessible names and visible focus;
  - streaming and error state changes are announced appropriately;
  - no horizontal overflow at agreed viewport sizes;
  - color contrast and reduced-motion behavior are documented and verified;
  - no regression in existing browser smoke.
- Independence: can proceed against the current UI without waiting for localization or backend changes.

### RS-UI-M03 — Indonesian and English localization
- Priority: P1
- Scope: extract user-facing ROCKSOUL UI strings into a small locale catalog; support Indonesian and English with a predictable locale selection and fallback. Do not translate provider/model names, user content, or runtime payloads.
- Deliverables: locale catalogs, locale resolver, language selector or documented browser-locale behavior, missing-key validation, UI tests.
- Acceptance:
  - every primary page uses catalog-backed UI strings;
  - Indonesian and English can be selected and persist across navigation/reload;
  - missing keys fall back deterministically and are detectable in tests;
  - long translations do not break responsive layouts;
  - runtime/API behavior is unchanged.
- Independence: no dependency on accessibility or provider certification.

### RS-UI-M04 — Real-provider and streaming compatibility harness
- Priority: P1
- Scope: create an opt-in smoke harness for a user-configured provider/model using the existing g4f runtime. Keep deterministic mocked tests as the default CI path; never require credentials in CI.
- Deliverables: documented environment variables/config, bounded smoke command, redacted result report, tests for timeout/cancel/error handling where deterministic.
- Acceptance:
  - no credential is committed, printed, or included in artifacts;
  - the harness has explicit opt-in and bounded request/time limits;
  - it verifies model discovery, non-streaming response, streaming completion, cancellation/disconnect behavior where supported;
  - unavailable providers are reported as skipped/blocked, not falsely passed;
  - mock CI remains deterministic and credential-free.
- Independence: can be delivered without changing the UI or adding provider implementations.

### RS-UI-M05 — Attachment and document parity
- Priority: P1
- Scope: compare legacy g4f GUI upload/document behavior with ROCKSOUL's existing multipart conversation flow. Identify supported file types, limits, extraction behavior, error messages, and media rendering. Implement only behavior already supported by the Python runtime.
- Deliverables: route/behavior parity matrix, file-type and size tests, safe UI validation, user-visible upload/extraction errors, regression coverage.
- Acceptance:
  - supported legacy file types remain usable through the existing endpoint;
  - unsupported/oversized files fail clearly before or during upload;
  - document extraction is performed by the existing runtime, never duplicated in JavaScript;
  - image/audio/video output continues to render safely;
  - no attachment is silently dropped or falsely described as processed.
- Independence: can proceed without live provider credentials, localization, or accessibility work.

### RS-UI-M06 — Legacy Apps and Private page parity
- Priority: P2
- Scope: inspect nested Apps and Private routes/actions against the legacy GUI. Preserve existing handlers and APIs; migrate only user-facing pages/actions with verified equivalents.
- Deliverables: nested route inventory, parity checklist, focused UI implementation, route and browser regression tests.
- Acceptance:
  - every retained navigation item opens a working destination;
  - each migrated action calls the existing supported g4f endpoint;
  - unsupported legacy actions are explicitly hidden or labeled, not represented as functional;
  - rollback via ROCKSOUL_UI_ENABLED=0 remains valid;
  - no static, media, API, or historical snapshot route is accidentally rewritten.
- Independence: can be completed without changing chat, auth, or locale architecture.

### RS-UI-M07 — Packaging and local operator experience
- Priority: P2
- Scope: validate the canonical single-service Docker Compose workflow on supported host environments; improve startup diagnostics and safe configuration documentation. Coolify is explicitly excluded.
- Deliverables: Compose smoke tests, Windows/macOS/Linux command notes where supported, health/readiness guidance, volume backup/restore notes, troubleshooting guide.
- Acceptance:
  - a clean checkout can build and start the existing Python service with ROCKSOUL assets;
  - ports remain loopback-only by default;
  - persistent data survives container recreation and documented backup/restore;
  - startup failures have actionable logs;
  - no second ROCKSOUL runtime/service is introduced.
- Independence: does not require the UI parity milestones to be complete.

## Suggested execution order

This is a priority order, not a dependency chain:

1. RS-UI-M01 — backend trust-boundary hardening
2. RS-UI-M02 — accessibility and responsive certification
3. RS-UI-M03 — Indonesian/English localization
4. RS-UI-M04 — opt-in real-provider compatibility harness
5. RS-UI-M05 — attachment/document parity
6. RS-UI-M06 — Apps/Private nested-route parity
7. RS-UI-M07 — packaging/local operator experience

Any milestone may be started independently or run in parallel when it does not edit the same files. Split implementation into small commits; run the narrow tests first, then the relevant browser/Python/CodeQL/ROCKSOUL CI workflows. Update `docs/rocksoul-ui-finalization.md` only with evidence-backed status changes.

## Remaining acceptance gates — execution instructions

These are the remaining checks that cannot honestly be certified from repository source alone. Run each independently; none requires another milestone.

### M01 — Remote trust-boundary verification
1. Keep the Python service on a private network and configure a high-entropy `G4F_API_KEY` outside the browser.
2. From an untrusted remote client, call `GET /backend-api/v2/webmcp/tools` without credentials; expect HTTP 403.
3. Configure the authenticated reverse proxy to inject `x-api-key` server-side and repeat; expect HTTP 200.
4. Confirm browser storage, page source, client logs, and proxy access logs do not reveal the key. The guard is not global authentication; protect every other legacy route at the proxy.

### M02 — Accessibility certification
- Automated coverage now checks 375px, 768px, and 1440px layouts, visible button names, reduced-motion behavior, and text-token contrast in both themes.
- Still perform keyboard-only navigation on the actual browser, NVDA (Windows) or VoiceOver (Apple), 200% zoom, focus visibility, and dynamic streaming/error announcements. Record browser/OS/assistive-technology versions and any defects.

### M03 — Translation completeness
- Select ID and EN, reload, and navigate every primary route.
- Exercise empty, loading, success, provider-error, upload-error, OAuth-pending, and tool-error states. Confirm interface-owned copy is translated, provider names/user content remain unchanged, and fallback is English.
- Record missing keys; do not treat a persisted locale selector as proof of full translation coverage.

### M04 — Real-provider compatibility
After the local Compose service is healthy, in PowerShell set a model already listed by `GET /v1/models` and opt in:
```powershell
$env:ROCKSOUL_SMOKE = "1"
$env:ROCKSOUL_SMOKE_MODEL = "your-existing-model-id"
node tests/rocksoul-provider-smoke.mjs
```
Set `ROCKSOUL_BASE_URL` and `G4F_API_KEY` only when needed. Set `ROCKSOUL_SMOKE_CANCEL=1` to run the optional client-abort probe. Never commit credentials or attach raw credential-bearing logs. Record provider/model and redacted result; an unavailable provider is blocked/skipped, not passed.

### M05 — Real document fixtures
- With the same g4f Python environment and optional extraction dependencies intended for deployment, test representative PDF, DOCX, ODT, EPUB, XLSX, and plain-text fixtures.
- Verify extracted text reaches the existing conversation request, temporary file buckets are removed, unsupported/empty documents produce a clear error, and no duplicate JavaScript extractor is introduced.
- Do not claim a format works solely because the mocked upload endpoint accepted it.

### M06 — Apps / Private legacy parity
- Compare the legacy Apps and Private entry points and any real nested assets/actions with the route inventory.
- Verify every retained action has an existing g4f handler; unsafe/missing app URLs remain informational. Check unknown nested HTML paths and nested static assets separately.
- Toggle `ROCKSOUL_UI_ENABLED=0`, restart, and verify legacy fallback. Preserve API, media, static, and version-pinned routes.

### M07 — Local Docker Compose operator smoke
From the repository root:
```powershell
docker compose up -d --build
docker compose ps
docker compose logs --tail 200 gpt4free
```
Wait until the service is healthy and open `http://localhost:8080`. Exercise chat, model discovery, upload, and restart. Use the README's named-volume backup/restore procedure on a disposable backup before relying on it. `docker compose down` preserves data; do not use `-v` unless intentionally deleting the volume. Coolify remains out of scope.

## Closure policy

Keep each GitHub issue open until its own acceptance gates have evidence. Exact-main CI proves only the automated jobs it actually ran. Live provider checks, real file fixtures, remote proxy behavior, assistive-technology review, and local Docker backup/restore must not be marked passed without their corresponding environment evidence.

## Explicitly out of scope

- Coolify deployment testing.
- A new ROCKSOUL API gateway, provider registry, model registry, or inference engine.
- Replacing/forking the g4f Python runtime.
- Requiring optional Arena, Mesh, WorkItem, WorkGraph, or operator Console modules for ordinary chat.
- Claiming production readiness from mocked browser tests alone.
- Enabling remote public exposure before privileged backend endpoints enforce server-side authorization.
