# ROCKSOUL UI and Optional Operator Console

ROCKSOUL's primary product is the replacement web interface for the existing g4f Python runtime. The runtime remains the sole authority for provider/model discovery, inference, streaming, tools, media, sessions and public API behavior.

This directory currently contains a **legacy/experimental operator console**, not the final ROCKSOUL chat UI. It visualizes optional ROCKSOUL diagnostics and engineering modules. It must not be treated as the primary user experience or as a required service for ordinary g4f chat.

## Product boundary

- Primary product: ROCKSOUL chat-first UI served by the existing g4f GUI application.
- Runtime: existing g4f Python service and APIs.
- This console: optional operator/developer tooling only.
- Not allowed: a second inference runtime, second provider registry, second model catalog, or mandatory control-plane service.

## Current console capabilities

The existing console contains diagnostic/operator surfaces for provider state, routing explanations, traces, Mesh, Arena, WorkItems, WorkGraph and evidence. These modules are optional and do not define the ROCKSOUL product.

## Migration status

The console has **not** yet been certified as the replacement for the built-in g4f HTML UI. The required replacement work is tracked in docs/rocksoul-blueprint.md and docs/rocksoul-todo.md:

1. Inventory current g4f GUI routes and API/session behavior.
2. Build the ROCKSOUL chat-first frontend.
3. Mount its built assets through g4f/gui/server/website.py.
4. Preserve existing g4f API, SDK, provider login, history and streaming behavior.
5. Cut over / and /chat/ only after parity tests pass.
6. Retain legacy UI rollback until certification.

Do not deploy this operator console as a prerequisite for chat. The existing docker-compose.rocksoul.yml is an optional operator-stack deployment, not the canonical deployment for the UI-only product.

## Development checks for this optional console

```bash
npm install
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

Passing these checks validates only this operator console; it does not certify g4f GUI replacement or runtime compatibility.
