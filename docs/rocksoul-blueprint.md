# ROCKSOUL — Product Blueprint

> **Replace the default g4f HTML interface. Preserve the g4f Python runtime.**

## 1. Executive direction

ROCKSOUL is the UI/UX replacement and product identity for g4f. It is a chat-first web interface over the existing g4f Python runtime and API.

The project is not building a second gateway, provider system, model registry, routing engine, execution engine, or backend control plane.

## 2. Source-of-truth architecture

```text
User
 │
 ▼
ROCKSOUL UI (frontend bundle)
 Chat · History · Model picker · Attachments · Settings · Diagnostics
 │
 │ existing g4f HTTP/API contracts
 ▼
g4f Python runtime
 Provider registry · Model mapping · Routing · Execution · Streaming
 Tools · Media · Sessions · Cookies · Python SDK
 │
 ▼
Existing provider implementations / local inference backends
```

The ROCKSOUL UI is a presentation client. The Python runtime remains the sole authority for provider discovery, model capability, provider authentication, execution, routing, retries, streaming, tool calls and media generation.

## 3. Responsibility boundaries

### g4f Python runtime — unchanged authority

- Provider implementations and provider-specific transports.
- Provider/model discovery and capability metadata.
- Request validation and execution.
- Existing model/provider selection and routing behavior.
- Streaming, cancellation/disconnect behavior where supported.
- Tool calling, media generation, file handling and sessions.
- Python SDK and public API compatibility.

### ROCKSOUL UI — new product surface

- Chat-first interaction and conversation navigation.
- Model/provider selector backed by runtime metadata.
- Rendering of streaming text, tool activity, errors and supported media.
- Attachments and multimodal composition where g4f supports them.
- Initial browser-local conversation history; server-backed session parity is a later migration task.
- Settings and provider login entry points using existing routes.
- Theme, localization, responsive behavior, keyboard access and accessibility.
- Optional diagnostics links without duplicating runtime state.

### Optional operator utilities

Existing Arena, Mesh, WorkItem, WorkGraph, verifier/evidence and operator-console modules are optional engineering/operator utilities. They are not part of the minimum chat architecture. They must remain isolated and must not gate startup or ordinary inference.

## 4. UI route integration

The existing GUI server is in g4f/gui. Its Website route registry owns /, /chat/, provider/status/settings and related UI routes. Its renderer currently serves local distribution files when available and otherwise retrieves the upstream GUI assets.

The replacement should be mounted through this existing GUI serving boundary. Do not create a second API service to serve chat. Keep existing backend routes and session behavior available to the new frontend.

Target behavior:

- / and /chat/ resolve to the ROCKSOUL app shell when the ROCKSOUL bundle is installed.
- Existing API routes remain unchanged.
- Static assets are served locally with safe path resolution, content types, cache policy and versioning.
- Deep links and browser refreshes resolve to the app shell only for owned UI paths.
- Provider login, status, logs and other existing backend routes remain reachable until their UI replacements are certified.
- A configuration switch permits rollback to the legacy GUI during migration.

## 5. Primary UX information architecture

1. **Chat** — conversation-first workspace, streaming responses and composer.
2. **History** — previous conversations and session continuity.
3. **Models** — runtime-backed model/provider selection and capability hints.
4. **Tools & media** — only the tools and modalities supported by the selected runtime path.
5. **Settings** — appearance, locale and existing runtime preferences.
6. **Providers** — provider details, authentication entry points and availability information.
7. **Diagnostics** — status, logs and request details for troubleshooting; secondary to chat.

Avoid a mandatory operator cockpit, WorkItem workflow, WorkGraph builder, Arena leaderboard or Mesh dashboard in the primary navigation.

## 6. Frontend integration contract

- Discover models/providers through existing g4f routes or API responses.
- Submit inference through existing g4f chat/API interfaces.
- Preserve current request fields and response shapes.
- Consume streaming responses incrementally; do not buffer them in a Next.js route handler.
- Forward cancellation when the browser aborts a request and the backend supports disconnect handling.
- Keep authentication/session cookies same-origin where possible.
- Never send provider credentials or server-side secrets to client code.
- Keep UI capability flags derived from backend metadata, not a duplicated static registry.
- Do not introduce a second retry/fallback policy in JavaScript.

## 7. Design direction

The interface should be premium, expressive and recognizable while remaining usable:

- Distinct ROCKSOUL identity; bold typography and purposeful visual contrast.
- Dark and light themes.
- Desktop-first workspace that adapts cleanly to mobile.
- Conversation-first hierarchy and low-friction composer.
- Clear streaming, queued, cancelled, failed and completed states.
- Keyboard shortcuts and accessible focus/contrast.
- Motion is restrained and respects reduced-motion preferences.
- Avoid an infrastructure-dashboard aesthetic in the main chat experience.

## 8. Deployment

Preferred deployment is one g4f Python application serving its API and the built ROCKSOUL frontend. Docker Compose/Coolify should remain simple: one runtime service, persistent g4f data/config volumes as required, and the UI assets bundled or mounted into the GUI distribution path.

Do not require a separate ROCKSOUL API container for chat. Optional operator tooling may be deployed separately only when explicitly needed.

## 9. Migration phases and gates

- **R0 — Scope reset:** product docs and backlog consistently state UI-only.
- **R1 — Route and capability inventory:** map every existing HTML route to its backend endpoints, cookies, session behavior and dependencies.
- **R2 — App shell:** build the ROCKSOUL UI and integrate it with the existing GUI server.
- **R3 — Chat parity:** streaming, history, model/provider selection, attachments and error states.
- **R4 — Secondary parity:** settings, providers, login, status, logs and supported tools.
- **R5 — Default cutover:** / and /chat/ serve ROCKSOUL; legacy rollback remains available.
- **R6 — Cleanup and certification:** remove legacy assets only after parity, compatibility and deployment tests pass.

Do not mark R2–R6 complete merely because a separate Next.js operator console builds.

## 10. Acceptance criteria

- No duplicate inference/runtime service is required.
- Existing g4f Python SDK and API tests remain green.
- UI uses live runtime model/provider metadata.
- Streaming is incremental and cancellation-safe to the extent supported by g4f.
- Conversation history behavior is explicit and tested; server-backed session continuity and supported uploads are certified before being claimed.
- / and /chat/ use ROCKSOUL by default after cutover.
- Legacy routes remain available until individually migrated.
- Docker Compose/Coolify deploys the same g4f runtime with the UI assets.
- Documentation clearly distinguishes implemented, in-progress and planned parity.

## 11. Optional modules and scope hygiene

The repository may retain experimental Arena, Mesh, WorkItem, WorkGraph and evidence modules. They must be described as optional and experimental/advanced, never as the ROCKSOUL product core. No ordinary chat path should require their API, database, authentication secrets or services.
