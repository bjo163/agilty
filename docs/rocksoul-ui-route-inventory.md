# ROCKSOUL UI — g4f GUI Route Inventory

This is the route-level handoff for replacing the built-in HTML UI without changing the Python runtime or API.

## GUI serving boundary

The current Flask GUI is assembled by g4f/gui/__init__.py and g4f/gui/server/website.py, then mounted by the existing FastAPI application when GUI mode is enabled.

The bundled ROCKSOUL assets live in g4f/gui/rocksoul and are included in package data.

| Route | Current behavior after UI mount | Notes |
|---|---|---|
| / | ROCKSOUL app shell by default | Set ROCKSOUL_UI_ENABLED=0 to fall back to legacy g4f home HTML |
| /chat/ | ROCKSOUL app shell by default | Same fallback switch |
| /rocksoul-assets/<path> | Bundled CSS/JS assets | Static files served from the package asset directory |
| /providers/, /providers/<name> | Existing g4f provider pages | Kept available during migration |
| /status/, /stats/, /logs/ | Existing g4f diagnostics pages | Kept available during migration |
| /agent, /browser | Existing g4f pages | Kept available during migration |
| /playground/, /apps/ | Existing g4f pages | Kept available during migration |
| /private/ | Existing g4f private page | Kept available during migration |
| /v<version>/* | Existing version-pinned GUI snapshots | Not rewritten by the initial ROCKSOUL mount |
| /<filename>.html | Existing legacy content pages | Kept available during migration |
| /media/, /dist/* | Existing media/static paths | Existing behavior preserved |

The g4f FastAPI routes, including the OpenAI-compatible inference API, are registered by the existing API application. The ROCKSOUL browser client calls /v1/models and /v1/chat/completions on the same origin. It does not create another inference service.

## Initial UI capability

The first bundled shell provides:

- Chat-first responsive layout with desktop sidebar and mobile navigation.
- Runtime model list populated from GET /v1/models.
- Streaming text generation through POST /v1/chat/completions.
- Browser-local conversation list and message history.
- Dark/light theme preference.
- Basic request errors and runtime status links.

This is an initial UI cut, not full legacy GUI parity. Browser-local history is not server-side g4f conversation persistence. Attachments, provider login management, rich tool/media rendering, settings parity, localization, and full accessibility review remain open.

## Rollback

Set ROCKSOUL_UI_ENABLED=0 in the g4f process environment and restart the process. The original g4f home and chat HTML handlers are used again. The new asset route remains inert unless requested directly.

## Verification requirements

- Test root and chat route selection with ROCKSOUL enabled and disabled.
- Test static asset serving and package/wheel inclusion.
- Run existing g4f GUI/API tests.
- Exercise real /v1/models and /v1/chat/completions requests with at least one provider.
- Verify incremental SSE output, provider errors, browser disconnects and reloads.
- Verify deployment from an installed wheel and from the repository Docker image.
