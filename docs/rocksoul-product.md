# ROCKSOUL Product

## Product identity

**ROCKSOUL is the user interface and visual identity for g4f.**

ROCKSOUL replaces the default g4f HTML/web interface with a modern, cohesive experience while continuing to use the existing g4f Python runtime, API routes, SDKs, provider implementations, model registry, routing, streaming, tools, and configuration.

ROCKSOUL is not a second LLM runtime, provider aggregator, gateway, router, orchestration engine, or backend control plane.

## Product promise

**One proven Python runtime. One coherent interface. No duplicated execution stack.**

Users should be able to use familiar g4f capabilities through a polished ROCKSOUL experience without learning a second API or maintaining a second set of provider integrations.

## Responsibility boundary

| Layer | Authority |
|---|---|
| g4f Python runtime | Provider adapters, model/provider discovery, model selection, request execution, retries supported by g4f, streaming, tools, media, sessions and persistence |
| g4f API and Python SDK | Public programmatic interfaces and compatibility contracts |
| ROCKSOUL UI | Chat experience, navigation, settings, model/provider selection presentation, history presentation, responsive design, accessibility and visual identity |
| Optional operator/developer tools | Diagnostics and advanced administration; never required for ordinary chat |

The UI calls existing g4f interfaces. It must not reimplement provider transport, maintain a competing model catalog, make independent routing decisions, or proxy around the runtime's established request lifecycle.

## Primary user experience

ROCKSOUL is the replacement for the default g4f web client. Its primary product surface is an AI workspace:

- Multi-conversation chat with streaming responses.
- Model and provider selection sourced from the live g4f runtime.
- Existing g4f capabilities exposed progressively: attachments, vision, tools, media and other supported modalities.
- Initial UI history is browser-local; server-backed g4f conversation/session parity remains a migration task.
- Provider/model information and diagnostics presented without duplicating backend state.
- Responsive desktop and mobile layouts.
- Dark and light themes, keyboard navigation, accessible controls and clear loading/error states.
- Indonesian and English UI foundations, with locale selection that does not alter runtime behavior.

The UI must accurately reflect runtime capability. It must not advertise unsupported models, tools, modalities, or provider health.

## Non-goals

- Building another OpenAI-compatible gateway.
- Creating a second provider registry or model catalog.
- Replacing or forking g4f's Python execution engine.
- Reimplementing retry, fallback, routing, provider authentication, streaming, or tool execution in the frontend.
- Making WorkItem or WorkGraph mandatory for ordinary chat.
- Treating Arena, Mesh, WorkItem, WorkGraph, verifier stores, or operator APIs as the core user-facing product.
- Claiming AGI, autonomous execution, or certification from the presence of advanced modules.

## Integration rules

1. Preserve existing g4f API paths and payload contracts.
2. Use the existing g4f backend for every inference request.
3. Use runtime-provided model/provider metadata; do not hardcode a parallel catalog.
4. Keep secrets and provider credentials on the server/runtime side.
5. Stream directly from the existing g4f streaming contract; do not buffer a stream unnecessarily.
6. Preserve cancellation and disconnect semantics supported by the backend.
7. Keep optional diagnostic/admin surfaces separate from the main chat flow.
8. The default root/chat experience must use the ROCKSOUL UI when the UI bundle is installed; a documented development/fallback path may remain available.

## Migration strategy

- **Phase 0 — Boundary reset:** update product docs, backlog, deployment guidance and naming so UI-only ownership is unambiguous.
- **Phase 1 — UI parity audit:** inventory every current g4f HTML route and its backing API/session behavior. Record route parity and unsupported UI-only behavior.
- **Phase 2 — ROCKSOUL shell:** implement the new frontend shell and mount it into the existing g4f GUI serving path. Do not introduce a separate inference backend.
- **Phase 3 — Chat parity:** implement conversations, streaming, model/provider selection, attachments and session/history compatibility.
- **Phase 4 — Secondary screens:** port providers, settings, status, logs and playground surfaces selectively; preserve existing endpoints.
- **Phase 5 — Cutover:** make ROCKSOUL the default / and /chat/ experience, retain an explicit rollback/fallback switch, and verify all existing API/SDK contracts.
- **Phase 6 — Cleanup:** remove obsolete HTML assets only after route parity and regression gates pass.

## Acceptance gates

ROCKSOUL is not considered the completed HTML replacement until:

- / and /chat/ serve the ROCKSOUL frontend by default.
- Existing g4f inference API and Python SDK behavior remain unchanged.
- Non-streaming and streaming chat work through the existing runtime.
- Model/provider lists are obtained from the runtime.
- Conversation/session continuity and supported attachments work.
- Existing provider login/cookie flows remain reachable where needed.
- Mobile, desktop, dark/light and accessibility smoke tests pass.
- The legacy UI remains recoverable until the cutover is certified.
- Docker/Coolify deployment runs the same g4f Python service and serves the ROCKSOUL UI without requiring a second inference/control-plane service.

## Optional advanced modules

This repository contains optional ROCKSOUL experiments and operator modules (Arena, Mesh, WorkItem, WorkGraph, verifier/evidence stores and diagnostics). They are not the product's core identity and must not be prerequisites for the normal chat UI. Keep them isolated, accurately documented, and independently removable without breaking g4f runtime or ROCKSOUL chat.

## Product decision filter

A proposed feature belongs in ROCKSOUL UI only if it improves the user's interaction with existing g4f capabilities. If it changes provider execution, routing authority, model state, or public API behavior, it belongs to g4f runtime/API and must not be duplicated in the frontend.
