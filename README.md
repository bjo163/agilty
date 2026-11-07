# GPT4Free (g4f)

[![PyPI](https://img.shields.io/pypi/v/g4f)](https://pypi.org/project/g4f) [![Docker Hub](https://img.shields.io/badge/docker-hlohaus789%2Fg4f-blue)](https://hub.docker.com/r/hlohaus789/g4f) [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-red.svg)](https://www.gnu.org/licenses/gpl-3.0.txt) [![PyPI Downloads](https://static.pepy.tech/personalized-badge/g4f?period=total&units=INTERNATIONAL_SYSTEM&left_color=GREY&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/g4f) ![GitHub Repo stars](https://img.shields.io/github/stars/xtekky/gpt4free)

<p align="center">
  <!--img src="https://g4f.dev/docs/images/477107515-7f60c240-00fa-4c37-bf7f-ae5cc20906a1.png" alt="GPT4Free logo" height="200" /-->


  [<img alt="Community Day 2026" src="https://g4f.dev/community-day-2026/awards/Start.jpeg" />](https://g4f.dev/community-day-2026/awards/)

</p>

<p align="center">
  <span style="background: linear-gradient(45deg, #12c2e9, #c471ed, #f64f59); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
    <strong>Created by <a href="https://github.com/xtekky">@xtekky</a>,<br> maintained by <a href="https://github.com/hlohaus">@hlohaus</a></strong>
  </span>
</p>
<p align="center">
<span>Support the project on</span>
      <a href="https://github.com/sponsors/hlohaus" target="_blank" rel="noopener noreferrer">
        GitHub Sponsors
      </a>
      ❤️
</p>
<p align="center">
Live demo & docs: https://g4f.dev | Documentation: https://g4f.dev/docs
</p>

---

GPT4Free (g4f) is a community-driven project that aggregates multiple accessible providers and interfaces to make working with modern LLMs and media-generation models easier and more flexible. GPT4Free aims to offer multi-provider support, local GUI, OpenAI-compatible REST APIs, and convenient Python and JavaScript clients — all under a community-first license.

This README is a consolidated, improved, and complete guide to installing, running, and contributing to GPT4Free.

Table of contents
- [What’s included](#whats-included)
- [ROCKSOUL UI](#rocksoul-ui)
- [Quick links](#quick-links)
- [Requirements & compatibility](#requirements--compatibility)
- [Installation](#installation)
  - [Docker (recommended)](#docker-recommended)
  - [Slim Docker image](#slim-docker-image)
  - [Sandbox desktop (Docker)](#sandbox-desktop-docker)
  - [Windows (.exe)](#windows-exe)
  - [Python (pip / from source / partial installs)](#python-pip--from-source--partial-installs)
- [Running the app](#running-the-app)
  - [GUI (web client)](#gui-web-client)
  - [FastAPI / Inference API](#fastapi--inference-api)
  - [CLI](#cli)
  - [Optional provider login (desktop in container)](#optional-provider-login-desktop-in-container)
- [Using the Python client](#using-the-python-client)
  - [Synchronous text example](#synchronous-text-example)
  - [Image generation example](#image-generation-example)
  - [Async client example](#async-client-example)
- [Using GPT4Free.js (browser JS client)](#using-gpt4freejs-browser-js-client)
- [Providers & models (overview)](#providers--models-overview)
- [Local inference & media](#local-inference--media)
- [Configuration & customization](#configuration--customization)
- [Running on smartphone](#running-on-smartphone)
- [Inference API (OpenAI‑compatible)](#interference-api-openai-compatible)
- [Examples & common patterns](#examples--common-patterns)
- [Contributing](#contributing)
  - [How to create a new provider](#how-to-create-a-new-provider)
  - [How AI can help you write code](#how-ai-can-help-you-write-code)
- [Security, privacy & takedown policy](#security-privacy--takedown-policy)
- [Credits, contributors & attribution](#credits-contributors--attribution)
- [Powered-by highlights](#powered-by-highlights)
- [Changelog & releases](#changelog--releases)
- [Manifesto / Project principles](#manifesto--project-principles)
- [License](#license)
- [Contact & sponsorship](#contact--sponsorship)
- [Appendix: Quick commands & examples](#appendix-quick-commands--examples)

---

## What’s included
- Python client library and async client.
- Optional local web GUI.
- FastAPI-based OpenAI-compatible API (Inference API).
- Official browser JS client (g4f.dev distribution).
- Docker images (full and slim).
- Multi-provider adapters (LLMs, media providers, local inference backends).
- Tooling for image/audio/video generation and media persistence.
- Optional ROCKSOUL operator/experimental modules (Arena, Mesh, WorkItem, WorkGraph and evidence tooling); not required for ordinary chat.


## ROCKSOUL UI

**ROCKSOUL is the new web interface for the existing g4f Python runtime.** Its purpose is to replace the default g4f HTML experience with a modern, chat-first UI—not to create another LLM gateway, provider registry, model catalog, router, or execution engine.

The existing g4f Python runtime remains the source of truth for provider implementations, model discovery, routing, inference, streaming, tools, media, sessions, and the public API/Python SDK. ROCKSOUL owns presentation, interaction, navigation, accessibility, themes, and localization.

The repository also contains optional engineering/operator modules (Arena, Mesh, WorkItem, WorkGraph, verifier/evidence stores and diagnostics). These are not required for ordinary chat and do not define the ROCKSOUL product.


### Start ROCKSOUL locally with Docker Compose

From the repository root (Windows PowerShell, macOS, or Linux):

```bash
docker compose up -d --build
docker compose logs -f gpt4free
```

Open **http://localhost:8080** (the alternate mapped port is **http://localhost:1337**). Check readiness with `docker compose ps` and inspect startup output with `docker compose logs -f gpt4free`. The canonical Compose file builds this checkout, restarts the service unless stopped, and reports readiness through the local `/health/ready` endpoint, which does not depend on upstream provider availability. It persists g4f configuration, cookies, share snapshots, logs, and cache in the named `g4f-data` volume. By default, the host ports bind to `127.0.0.1` only; they are not published to the LAN. Stop the service with `docker compose down`. This preserves the volume; do not add `-v` unless you intend to delete persisted data.

**API authentication mode:** Compose explicitly defaults to `G4F_AUTH_MODE=optional` because its published ports bind to loopback for local development. Outside Compose, an unspecified auth mode defaults to `required` whenever g4f binds to a non-loopback host; a loopback bind defaults to `optional`. For any remote deployment, set `G4F_AUTH_MODE=required` explicitly and configure a strong `G4F_API_KEY` in the shell or a private `.env` file. Required mode fails closed with HTTP 503 when the key is missing and requires a valid API key or verified authenticated session on API routes (health probes remain public). Successful API-key authentication receives an opaque stable principal ID; the raw key is never used as the principal or logged. The single environment key is not a multi-tenant key registry and does not yet provide per-key scopes/rotation storage. Never commit the key or expose it in browser JavaScript. Keep the Python service private and use an authenticated reverse proxy that injects the key server-side; do not trust arbitrary forwarded identity headers. The gateway also applies process-local per-principal token-bucket rate limits (`G4F_RATE_LIMIT_PER_MINUTE`, default 120) and concurrent-request caps (`G4F_MAX_INFLIGHT_PER_PRINCIPAL`, default 4); streaming requests hold permits until completion or disconnect. These limits are per worker process, not distributed across multiple workers or replicas.

**Upload limits:** the Flask GUI file endpoint enforces a 25 MiB aggregate request limit by default and a 10-file per-request limit. Operators can set `G4F_MAX_UPLOAD_BYTES` (clamped to 1–256 MiB) and `G4F_MAX_UPLOAD_FILES` (clamped to 1–50). Oversized requests return HTTP 413. Document conversion runs in a separate spawned process with a 30-second default timeout, bounded output (1,000,000 characters), a 25-second CPU budget, and a 1.5 GiB address-space limit where POSIX resource limits are available. Configure `G4F_EXTRACTION_TIMEOUT_SECONDS` (3–120), `G4F_EXTRACTION_MAX_OUTPUT_CHARS` (1,000–5,000,000), `G4F_EXTRACTION_CPU_SECONDS` (2–120), `G4F_EXTRACTION_MAX_MEMORY_MB` (256–4,096; POSIX only), and `G4F_EXTRACTION_MAX_WORKERS` (1–4; default 2). Windows gets process isolation and timeout/output limits; a hard per-process memory cap is not currently enforced there. Image decompression/pixel hardening remains separate.

**Back up the persistent volume (PowerShell):**
```powershell
$volume = docker volume ls -q --filter "name=g4f-data" | Select-Object -First 1
docker compose stop gpt4free
docker run --rm -v "${volume}:/data" -v "${PWD}:/backup" alpine sh -c "tar -czf /backup/g4f-data-backup.tar.gz -C /data ."
docker compose start gpt4free
```

**Restore a backup (destructive to the current volume contents):**
```powershell
$volume = docker volume ls -q --filter "name=g4f-data" | Select-Object -First 1
docker compose stop gpt4free
docker run --rm -v "${volume}:/data" -v "${PWD}:/backup" alpine sh -c "tar -xzf /backup/g4f-data-backup.tar.gz -C /data"
docker compose start gpt4free
```


This starts the ROCKSOUL UI and existing g4f Python runtime together—there is no separate ROCKSOUL gateway. Provider availability still depends on the providers and credentials configured in g4f. Keep the service local until you have put all legacy API routes behind a trusted authenticated reverse proxy before remote exposure.

**Optional live-provider smoke (manual, credential-bearing):** after the local service is healthy, set `ROCKSOUL_SMOKE=1` and `ROCKSOUL_SMOKE_MODEL` to a model already returned by `/v1/models`, then run `node tests/rocksoul-provider-smoke.mjs`. Set `ROCKSOUL_BASE_URL` and `G4F_API_KEY` only when needed. Add `ROCKSOUL_SMOKE_CANCEL=1` to run the optional client-abort probe. The script redacts endpoint credentials and never prints the API key. It is opt-in and is not part of credential-free CI.

**UI replacement status:** ROCKSOUL is the unified shell for the primary live GUI pages: overview, chat, providers/details, status, stats, logs, agent tools, browser workspace, playground, apps/modules, and private utilities. It calls the existing g4f APIs; it does not add a gateway or inference runtime. Privileged WebMCP, diagnostic-log, usage, file-bucket, cookie/HAR upload, and shared-chat write endpoints allow loopback clients and explicitly trusted source CIDRs, or require a matching API key for other remote calls. Public shared-chat reads remain bearer-link based by design. Use a trusted reverse proxy for remote access and never expose the service directly. Chat supports media attachments through the existing conversation endpoint and document extraction through the existing g4f file-bucket/stream endpoints; supported document extraction depends on the installed Python file dependencies. Indonesian/English UI selection, keyboard skip navigation, visible focus, and an opt-in live-provider smoke harness have been added. Apps without a safe launch URL are informational rather than clickable. Compose includes health/restart policy and named-volume backup/restore instructions. Exact-main CI and live-provider checks are still required before production certification. Set `ROCKSOUL_UI_ENABLED=0` to roll back primary GUI pages to legacy handlers. Shared conversation links can be read by anyone who possesses them. Coolify deployment testing is intentionally out of scope. See [Product](docs/rocksoul-product.md), [Narrative](docs/rocksoul-narrative.md), [Blueprint](docs/rocksoul-blueprint.md), [GUI route inventory](docs/rocksoul-ui-route-inventory.md), [Finalization status](docs/rocksoul-ui-finalization.md), [Backlog](docs/rocksoul-todo.md), and [independent milestones](docs/rocksoul-next-milestones.md).

---
 
## Quick links
- Website & docs: https://g4f.dev | https://g4f.dev/docs  
- PyPI: https://pypi.org/project/g4f  
- Docker image: https://hub.docker.com/r/hlohaus789/g4f  
- Releases: https://github.com/xtekky/gpt4free/releases  
- Issues: https://github.com/xtekky/gpt4free/issues  
- Community: Telegram (https://telegram.me/g4f_channel) · Discord News (https://discord.gg/5E39JUWUFa) · Discord Support (https://discord.gg/qXA4Wf4Fsm)

---

## Related projects
- [g4f-go](g4f-go/README.md) – Self-contained Go launcher for g4f (downloads CPython + g4f on demand; includes the `g4f-go sandbox` launcher for Docker, Podman and udocker)
- [remote_desktop](projects/remote-desktop/) – WebRTC-based remote desktop host/viewer
- [sandbox-desktop](https://g4f.dev/docs/sandbox-desktop) – TigerVNC + Xfce + noVNC desktop in Docker with preinstalled coding agents ([menu/tool list](docker/sandbox-menu/README.md), [start script](bin/start-sandbox-desktop.sh), [Dockerfile](docker/Dockerfile-sandbox-desktop))

---

## Requirements & compatibility
- Python 3.10+ recommended.
- Google Chrome/Chromium for providers using browser automation.
- Docker for containerized deployment.
- Works on x86_64 and arm64 (slim image supports both).
- Some provider adapters may require platform-specific tooling (Chrome/Chromium, etc.). Check provider docs for details.

---

## Installation

### Docker (recommended)
1. Install Docker: https://docs.docker.com/get-docker/
2. Create persistent directories:
   - Example (Linux/macOS):
     ```bash
     mkdir -p ${PWD}/har_and_cookies ${PWD}/generated_media
     sudo chown -R 1200:1201 ${PWD}/har_and_cookies ${PWD}/generated_media
     ```
3. Pull image:
   ```bash
   docker pull hlohaus789/g4f
   ```
4. Run container:
   ```bash
   docker run -p 8080:8080 -p 7900:7900 \
     --shm-size="2g" \
     -v ${PWD}/har_and_cookies:/app/har_and_cookies \
     -v ${PWD}/generated_media:/app/generated_media \
     hlohaus789/g4f:latest
   ```
Notes:
- Port 8080 serves GUI/API; 7900 can expose a VNC-like desktop for provider logins (optional).
- Increase --shm-size for heavier browser automation tasks.

### Slim Docker image (x64 & arm64)
```bash
mkdir -p ${PWD}/har_and_cookies ${PWD}/generated_media
chown -R 1000:1000 ${PWD}/har_and_cookies ${PWD}/generated_media

docker run \
  -p 1337:8080 -p 8080:8080 \
  -v ${PWD}/har_and_cookies:/app/har_and_cookies \
  -v ${PWD}/generated_media:/app/generated_media \
  hlohaus789/g4f:latest-slim
```
Notes:
- The slim image can update the g4f package on startup and installs additional dependencies as needed.
- In this example, the Inference API is mapped to 1337.

### Sandbox desktop (Docker)
A full Xfce desktop (TigerVNC + noVNC) with the g4f API and a one-click
**one-click** menu for 100+ AI tools and providers — coding agents,
browsers, gateways, local runtimes and assistants. See
[docs/sandbox-desktop](https://g4f.dev/docs/sandbox-desktop) for the start script,
clipboard, scaling, app volume, user id, password and domain-routing options,
and [docker/sandbox-menu/README.md](docker/sandbox-menu/README.md) for the
menu, the tool list and the settings.

```bash
docker run -d --name g4f-sandbox-desktop \
  --cap-add NET_ADMIN \
  -p 127.0.0.1:8080:8080 -p 127.0.0.1:5900:5900 \
  --shm-size="2gb" \
  -v ${PWD}:/app/gpt4free \
  -v ${PWD}/sandbox-home/.config:/home/pn/.config \
  -v ${PWD}/sandbox-home/.local:/home/pn/.local \
  hlohaus789/g4f:latest-sandbox-desktop
```
- Desktop (browser): http://127.0.0.1:8080/desktop/ · API: http://127.0.0.1:8080/ · Direct VNC: `127.0.0.1:5900`
- The ports bind to `127.0.0.1` by default (localhost only, not every host
  interface). Set `SANDBOX_BIND_ADDR=0.0.0.0` to expose the desktop on the LAN;
  `bin/start-sandbox-desktop.sh --bind <addr>` does the same.
- The image starts an egress firewall (needs `--cap-add NET_ADMIN`): the
  sandbox can reach the public internet, but connections to private,
  link-local and reserved networks — the host LAN, other Docker networks and
  cloud metadata — are rejected. Loopback inside the container stays usable,
  so the g4f API, its `*.g4f.local` router and local gateways keep working.
  Replies to connections that come in from the host are allowed, so the
  published desktop/API ports stay reachable even though the host address is
  in a blocked range; the filter only stops the sandbox from starting such
  connections itself. Outbound file-sharing/sync protocols (SMB, NetBIOS,
  NFS, AFP, FTP/TFTP, rsync, iSCSI, rpcbind) and common crypto-mining pool
  ports are rejected too. Host-side services reached through
  `host.docker.internal`, `172.17.0.1` or the host's LAN address are blocked
  as well; run them inside the sandbox or set `SANDBOX_BLOCK_LOCAL_NETWORK=0`
  to disable the filter for a trusted setup. If the filter cannot be installed
  the sandbox still starts with a warning; set `SANDBOX_FIREWALL_STRICT=1` to
  make that fatal.
- `-v ${PWD}:/app/gpt4free` mounts your app into the sandbox at the path the
  image's editable g4f install points at, so the API serves your code and the
  agents can edit it. Mount at `/app/gpt4free`, not `/app`.
- `-v ${PWD}/sandbox-home/.config:/home/pn/.config` and `…/.local:/home/pn/.local`
  keep agent configs, credentials, caches and the sandbox settings across
  container restarts — without them every new container starts with an empty
  home and every tool asks for its login again. Do not mount over `/home/pn`
  itself: the embedded Python and g4f runtime live in `/home/pn/.g4f`.
- To give the agents a throwaway profile instead, point `HOME` at a mounted
  directory: `-v ${PWD}/agent-home:/home/pn/work` plus **Sandbox Settings** →
  `sandbox-cli settings --home /home/pn/work`.
- `bin/start-sandbox-desktop.sh` wraps the same run (and
  `docker/docker-compose.sandbox-desktop.yml`) with `--build`, `--pull`,
  `--port`, `--bind`, `--app-dir`, `--user-id`, `--api-key`,
  `--domain-suffix`, `--no-domain-router`, `shell`, `logs` and `stop`.
  `--api-key KEY` protects the desktop/API with a password (any username
  works in the browser login); see
  [docs/sandbox-desktop](https://g4f.dev/docs/sandbox-desktop).
- The sandbox user (`pn`) runs with uid/gid 1000 by default. On a host whose
  user has another id, build the image with
  `--build-arg G4F_USER_ID="$(id -u)"` (or run
  `bin/start-sandbox-desktop.sh --user-id "$(id -u)"`; it rebuilds when the
  existing image was built for a different id). Matching the id keeps the
  bind-mounted `sandbox-home` and files written under `/app/gpt4free` owned by
  your host user.

#### Sandbox launcher (`g4f-go sandbox`)

Download `g4f-go` from the release assets for Windows, Linux, macOS or Termux
(amd64/arm64). The `sandbox` subcommand requires only Docker, Podman or, on
Termux/Android, udocker; it does not embed the image and pulls it on demand:

```bash
g4f-go sandbox                    # small API-only sandbox (latest-slim)
g4f-go sandbox --desktop          # full desktop image, pulled on first use
g4f-go sandbox --desktop install chrome
g4f-go sandbox-cli list           # shorthand for `g4f-go sandbox --desktop cli`
g4f-go sandbox status
g4f-go sandbox down
```

The default API-only mode uses the multi-arch `latest-slim` image; `--desktop`
pulls `latest-sandbox-desktop` only when the desktop is requested. Tools are
installed on demand from the sandbox menu or with
`g4f-go sandbox --desktop install <tool>`. On Termux/Android the same command
uses udocker (installed with pip on first use) to run those images without
root; the native API-only backend is still available with `--backend termux`.
See [g4f-go](g4f-go/README.md) and the
[sandbox desktop documentation](https://g4f.dev/docs/sandbox-desktop).

### Python Installation (pip / from source / partial installs)

Prerequisites:
- Python 3.10+ (https://www.python.org/downloads/)
- Chrome/Chromium for some providers.

Install from PyPI (recommended):
```bash
pip install -U g4f[all]
```

Partial installs
- To install only specific functionality, use optional extras groups. See [docs/requirements](https://g4f.dev/docs/requirements) in the project docs.

Install from source:
```bash
git clone https://github.com/xtekky/gpt4free.git
cd gpt4free
pip install -r requirements.txt
pip install -e .
```

Notes:
- Some features require Chrome/Chromium or other tools; follow provider-specific docs.

---

## Running the app

### GUI (web client)

When GUI mode is enabled, the bundled ROCKSOUL workspace serves the primary GUI pages from the existing g4f Python GUI server. Set `ROCKSOUL_UI_ENABLED=0` to temporarily restore the legacy g4f page handlers. The UI calls same-origin g4f APIs; it does not start another runtime.
- Run via Python:
```python
from g4f.gui import run_gui
run_gui()
```
- Or via CLI:
```bash
python -m g4f.cli gui --port 8080 --debug
```
- Open: http://localhost:8080/chat/

### FastAPI / Inference API
- Start FastAPI server:
```bash
python -m g4f --port 8080 --debug
```
- If using slim docker mapping, Inference API may be available at `http://localhost:1337/v1`
- Swagger UI: `http://localhost:1337/docs`

### CLI
- Start GUI server:
```bash
python -m g4f.cli gui --port 8080 --debug
```

### MCP Server
GPT4Free now includes a Model Context Protocol (MCP) server that allows AI assistants like Claude to access web search, scraping, and image generation capabilities.

**Starting the MCP server (stdio mode):**
```bash
# Using g4f command
g4f mcp

# Or using Python module
python -m g4f.mcp
```

**Starting the MCP server (HTTP mode):**
```bash
# Start HTTP server on port 8765
g4f mcp --http --port 8765

# Custom host and port
g4f mcp --http --host 127.0.0.1 --port 3000
```

HTTP mode provides:
- `POST http://localhost:8765/mcp` - JSON-RPC endpoint
- `GET http://localhost:8765/health` - Health check

**Configuring with Claude Desktop:**

Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "gpt4free": {
      "command": "python",
      "args": ["-m", "g4f.mcp"]
    }
  }
}
```

**Available MCP Tools:**
- `web_search` - Search the web using DuckDuckGo
- `web_scrape` - Extract text content from web pages  
- `image_generation` - Generate images from text prompts
- `polli_publish_app` - Publish a built app from the workspace to
  `https://<name>.pollinations.app` with the Pollinations CLI

For detailed MCP documentation, see [g4f/mcp/README.md](g4f/mcp/README.md)

### Optional provider login (desktop within container)
- Accessible at:
  ```
  http://localhost:7900/?autoconnect=1&resize=scale&password=secret
  ```
- Useful for logging into web-based providers to obtain cookies/HAR files.

---

## Using the Python client

Install:
```bash
pip install -U g4f[all]
```

Synchronous text example:
```python
from g4f.client import Client

client = Client()
response = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Hello, how are you?"}],
    web_search=False
)
print(response.choices[0].message.content)
```
Expected:
```
Hello! How can I assist you today?
```

Image generation example:
```python
from g4f.client import Client

client = Client()
response = client.images.generate(
    model="flux",
    prompt="a white siamese cat",
    response_format="url"
)
print(f"Generated image URL: {response.data[0].url}")
```

Async client example:
```python
from g4f.client import AsyncClient
import asyncio

async def main():
    client = AsyncClient()
    response = await client.chat.completions.create(
        model="auto",
        messages=[{"role": "user", "content": "Explain quantum computing briefly"}],
    )
    print(response.choices[0].message.content)

asyncio.run(main())
```

Notes:
- See the full API reference for streaming, tool-calling patterns, and advanced options: https://g4f.dev/docs/client

---

## Using GPT4Free.js (browser JS client)
Use the official JS client in the browser—no backend required.

Example:
```html
<script type="module">
  import Client from 'https://g4f.dev/dist/js/client.js';

  const client = new Client();
  const result = await client.chat.completions.create({
      model: 'auto',  // Or "glm-5.3", "kimi-k3", etc.
      messages: [{ role: 'user', content: 'Explain quantum computing' }]
  });
  console.log(result.choices[0].message.content);
</script>
```

Notes:
- The JS client is distributed via the g4f.dev CDN for easy usage. Review CORS considerations and usage limits.

---

## Providers & models (overview)
- GPT4Free integrates many providers including (but not limited to) OpenAI-compatible endpoints, PerplexityLabs, Gemini, MetaAI, Pollinations (media), and local inference backends.
- Model availability and behavior depend on provider capabilities. See the providers doc for current, supported provider/model lists: https://g4f.dev/docs/providers-and-models

Provider requirements may include:
- API keys or tokens (for authenticated providers)
- Browser cookies / HAR files for providers scraped via browser automation
- Chrome/Chromium or headless browser tooling
- Local model binaries and runtime (for local inference)

---

## Local inference & media
- GPT4Free supports local inference backends. See [docs/local](https://g4f.dev/docs/local) for supported runtimes and hardware guidance.
- Media generation (image, audio, video) is supported through providers (e.g., Pollinations). See [docs/media](https://g4f.dev/docs/media) for formats, options, and sample usage.

---

## Configuration & customization
- Configure via environment variables, CLI flags, or config files. See [docs/config](https://g4f.dev/docs/config).
- To reduce install size, use partial requirement groups. See [docs/requirements](https://g4f.dev/docs/requirements).
- Provider selection: learn how to set defaults and override per-request at [docs/selecting_a_provider](https://g4f.dev/docs/selecting_a_provider).
- Persistence: HAR files, cookies, and generated media persist in mapped directories (e.g., har_and_cookies, generated_media).

---

## Running on smartphone
- The web GUI is responsive and can be accessed from a phone by visiting your host IP:8080 or via a tunnel. See [docs/guides/phone](https://g4f.dev/docs/guides/phone).

---

## Inference API (OpenAI‑compatible)
- The Inference API enables OpenAI-like workflows routed through GPT4Free provider selection.
- Docs: [docs/interference-api](https://g4f.dev/docs/interference-api)
- Default endpoint (example slim docker): `http://localhost:1337/v1`
- Swagger UI: `http://localhost:1337/docs`

---

## Examples & common patterns
- Streaming completions, stopping criteria, system messages, and tool-calling patterns are documented in:
  - [docs/client](https://g4f.dev/docs/client)
  - [docs/async_client](https://g4f.dev/docs/async_client)
  - [docs/requests](https://g4f.dev/docs/requests)
- Integrations (LangChain, PydanticAI): [docs/pydantic_ai](https://g4f.dev/docs/pydantic_ai)
- Legacy examples: [docs/legacy](https://g4f.dev/docs/legacy)

---

## Contributing
Contributions are welcome — new providers, features, docs, and fixes are appreciated.

How to contribute:
1. Fork the repository.
2. Create a branch for your change.
3. Run tests and linters.
4. Open a Pull Request with a clear description and tests/examples if applicable.

Repository: https://github.com/xtekky/gpt4free

### How to create a new provider
- Read the guide: [docs/guides/create_provider](https://g4f.dev/docs/guides/create_provider)
- Typical steps:
  - Implement a provider adapter in `g4f/Provider/`
  - Add configuration and dependency notes
  - Include tests and usage examples
  - Respect third‑party code licenses and attribute appropriately

### How AI can help you write code
- See: [docs/guides/help_me](https://g4f.dev/docs/guides/help_me) for prompt templates and workflows to accelerate development.
- Automatic development loop: [docs/dev-pipeline](https://g4f.dev/docs/dev-pipeline) explains `bin/dev-pipeline`, which reads tasks from `AGENTS.md` and implements them with working free models from pi-freeflow.

---

## Security, privacy & takedown policy
- Do not store or share sensitive credentials. Use per-provider recommended security practices.
- Conversations are stored locally on your device by default; server/cloud synchronization (Secret Storage) is strictly opt-in and client-side encrypted.
- If your site appears in the project’s links and you want it removed, send proof of ownership to https://g4f.dev/community and it will be removed promptly.
- For production, secure the server with HTTPS, authentication, and firewall rules. Limit access to provider credentials and cookie/HAR storage.

---

## Credits, contributors & attribution
- Core creators: [@xtekky](https://github.com/xtekky) (original), maintained by [@hlohaus](https://github.com/hlohaus).
- Full contributor graph: https://github.com/xtekky/gpt4free/graphs/contributors

Many more contributors are acknowledged in the repository.

---

## Powered-by highlights
- Pollinations AI — generative media: https://github.com/pollinations/pollinations
- MoneyPrinter V2 — example project using GPT4Free: https://github.com/FujiwaraChoki/MoneyPrinterV2
- For a full list of projects and sites using GPT4Free, see: [docs/powered-by](https://g4f.dev/docs/powered-by)

---

## Changelog & releases
- Releases and full changelog: https://github.com/xtekky/gpt4free/releases
- Subscribe to Discord/Telegram for announcements.

---

## Manifesto / Project principles
GPT4Free is guided by community principles:
1. Open access to AI tooling and models.
2. Collaboration across providers and projects.
3. Opposition to monopolistic, closed systems that restrict creativity.
4. Community-centered development and broad access to AI technologies.
5. Promote innovation, creativity, and accessibility.

https://g4f.dev/manifesto

---

## License
This program is licensed under the GNU General Public License v3.0 (GPLv3). See the full license: https://www.gnu.org/licenses/gpl-3.0.txt

Summary:
- You may redistribute and/or modify under the terms of GPLv3.
- The program is provided WITHOUT ANY WARRANTY.

Copyright notice
```
xtekky/gpt4free: Copyright (C) 2025 xtekky

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
```

---

## Contact & sponsorship
- Maintainers: https://github.com/hlohaus
- Community & contact: https://g4f.dev/community
- Sponsorship: https://github.com/sponsors/hlohaus  
- Issues & feature requests: https://github.com/xtekky/gpt4free/issues  

---

## Appendix: Quick commands & examples

Install g4f-go (launcher):
```bash
curl -fsSL https://raw.githubusercontent.com/xtekky/gpt4free/main/bin/install.sh | bash
```

Install (pip):
```bash
pip install -U g4f[all]
```

Run GUI (Python):
```bash
python -m g4f.cli gui --port 8080 --debug
# or
python -c "from g4f.gui import run_gui; run_gui()"
```

Docker (full):
```bash
docker pull hlohaus789/g4f
docker run -p 8080:8080 -p 7900:7900 \
  --shm-size="2g" \
  -v ${PWD}/har_and_cookies:/app/har_and_cookies \
  -v ${PWD}/generated_media:/app/generated_media \
  hlohaus789/g4f:latest
```

Docker (slim):
```bash
docker run -p 1337:8080 -p 8080:8080 \
  -v ${PWD}/har_and_cookies:/app/har_and_cookies \
  -v ${PWD}/generated_media:/app/generated_media \
  hlohaus789/g4f:latest-slim
```

Python usage patterns:
- `client.chat.completions.create(...)`
- `client.images.generate(...)`
- Async variants via `AsyncClient`

Docs & deeper reading
- Full docs: https://g4f.dev/docs  
- Client API docs: https://g4f.dev/docs/client  
- Async client docs: https://g4f.dev/docs/async_client  
- Provider guides: https://g4f.dev/docs/providers  
- Local inference: https://g4f.dev/docs/local

---

Thank you for using and contributing to GPT4Free — together we make powerful AI tooling accessible, flexible, and community-driven.
