import pytest
from flask import Flask
from werkzeug.exceptions import NotFound

from g4f.gui.server.website import Website


def _website():
    return Website(Flask(__name__))


def _body(response):
    # Flask send_file responses use direct passthrough outside the test client.
    response.direct_passthrough = False
    return response.get_data()


def test_root_serves_bundled_rocksoul_ui_by_default(monkeypatch):
    monkeypatch.delenv("ROCKSOUL_UI_ENABLED", raising=False)
    website = _website()

    with website.app.test_request_context("/"):
        response = website._index()

    assert response.status_code == 200
    assert response.headers.get("X-ROCKSOUL-UI") == "1"
    assert b"ROCKSOUL" in _body(response)


def test_chat_route_serves_same_rocksoul_app_shell(monkeypatch):
    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "true")
    website = _website()

    with website.app.test_request_context("/chat/"):
        response = website._chat()

    assert response.status_code == 200
    assert response.headers.get("X-ROCKSOUL-UI") == "1"
    assert b'id="composer"' in _body(response)


def test_legacy_gui_fallback_can_be_selected(monkeypatch):
    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "0")
    website = _website()

    assert website._rocksoul_enabled() is False


def test_rocksoul_assets_are_served_from_bundled_directory(monkeypatch):
    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "1")
    website = _website()

    with website.app.test_request_context("/rocksoul-assets/app.css"):
        response = website._rocksoul_asset("app.css")

    assert response.status_code == 200
    assert b".app-shell" in _body(response)
    assert response.headers.get("Cache-Control") == "public, max-age=0, must-revalidate"


def test_all_bundled_assets_are_present_and_served(monkeypatch):
    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "1")
    website = _website()

    for filename, marker in (
        ("index.html", b"ROCKSOUL"),
        ("app.js", b"AbortController"),
        ("app.css", b".app-shell"),
        ("locale.js", b"rocksoul-locale"),
    ):
        with website.app.test_request_context(f"/rocksoul-assets/{filename}"):
            response = website._rocksoul_asset(filename)
        assert response.status_code == 200
        assert marker in _body(response)


def test_asset_handler_rejects_parent_traversal():
    website = _website()

    with website.app.test_request_context("/rocksoul-assets/../server/website.py"):
        with pytest.raises(NotFound):
            website._rocksoul_asset("../server/website.py")


def test_legacy_root_handler_is_used_when_ui_is_disabled(monkeypatch):
    import g4f.gui.server.website as website_module

    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "0")
    monkeypatch.setattr(website_module, "render", lambda filename: f"legacy:{filename}")
    website = _website()

    with website.app.test_request_context("/"):
        response = website._index()

    assert response == "legacy:home"


def test_legacy_chat_handler_is_used_when_ui_is_disabled(monkeypatch):
    import g4f.gui.server.website as website_module

    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "0")
    monkeypatch.setattr(website_module, "render", lambda filename: f"legacy:{filename}")
    website = _website()

    with website.app.test_request_context("/chat/"):
        response = website._chat()

    assert response == "legacy:chat/index"



def test_all_primary_gui_pages_use_the_rocksoul_shell(monkeypatch):
    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "1")
    website = _website()
    handlers = (
        (website._agent, "/agent/"),
        (website._browser, "/browser/"),
        (website._logs, "/logs/"),
        (website._status, "/status/"),
        (website._stats, "/stats/"),
        (website._providers, "/providers/"),
        (lambda: website._provider_detail("ExampleProvider"), "/providers/ExampleProvider"),
        (website._private, "/private/"),
        (website._apps, "/apps/"),
        (website._playground, "/playground/"),
        (lambda: website._index("stats"), "/stats.html"),
        (lambda: website._index("providers"), "/providers.html"),
    )

    for handler, path in handlers:
        with website.app.test_request_context(path):
            response = handler()
        assert response.status_code == 200, path
        assert response.headers.get("X-ROCKSOUL-UI") == "1", path


def test_rocksoul_route_inventory_keeps_non_ui_assets_and_apis(monkeypatch):
    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "1")
    website = _website()

    assert "/rocksoul-assets/<path:filename>" in website.routes
    assert "/dist/<path:name>" in website.routes
    assert "/media/" in website.routes
    assert "/v<version>/<path:filename>" in website.routes
    assert "/meta" in website.routes
    assert "/sitemap.xml" in website.routes


def test_rocksoul_page_migration_preserves_nested_static_assets(monkeypatch):
    import g4f.gui.server.website as website_module

    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "1")
    monkeypatch.setattr(website_module, "render", lambda filename: f"legacy-asset:{filename}")
    website = _website()

    with website.app.test_request_context("/chat/app.js"):
        assert website._chat("app.js") == "legacy-asset:chat/app.js"
    with website.app.test_request_context("/apps/bundle.css"):
        assert website._apps("bundle.css") == "legacy-asset:apps/bundle.css"
    with website.app.test_request_context("/private/private.js"):
        assert website._private("private.js") == "legacy-asset:private/private.js"


def test_migrated_diagnostic_pages_keep_legacy_rollback(monkeypatch):
    import g4f.gui.server.website as website_module

    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "0")
    monkeypatch.setattr(website_module, "render", lambda filename: f"legacy:{filename}")
    website = _website()
    handlers = (
        (website._agent, "/agent/", "legacy:agent"),
        (website._browser, "/browser/", "legacy:browser"),
        (website._logs, "/logs/", "legacy:logs"),
        (website._status, "/status/", "legacy:status"),
        (website._stats, "/stats/", "legacy:stats"),
        (website._private, "/private/", "legacy:private/index"),
        (website._apps, "/apps/", "legacy:apps/index.html"),
        (website._chat, "/chat/", "legacy:chat/index"),
    )
    for handler, path, expected in handlers:
        with website.app.test_request_context(path):
            assert handler() == expected, path

def test_ui_assets_include_stream_cancellation_and_sse_flush():
    from pathlib import Path

    asset_dir = Path(__file__).parents[1] / "g4f" / "gui" / "rocksoul"
    script = (asset_dir / "app.js").read_text(encoding="utf-8")
    markup = (asset_dir / "index.html").read_text(encoding="utf-8")
    styles = (asset_dir / "app.css").read_text(encoding="utf-8")

    assert "new AbortController()" in script
    assert 'if(buffer.trim())consumeLine(buffer.trim())' in script
    assert "const readStorage=" in script
    assert "const writeStorage=" in script
    assert "Local history storage unavailable" in script
    assert 'id="stop"' in markup
    assert 'id="new-chat"' in markup
    assert ".stop-button" in styles
    assert "message-action-copy" in script
    assert "message-action-edit" in script
    assert "message-action-delete" in script
    assert "message-action-regenerate" in script
    assert 'id="export-md"' in markup
    assert 'id="export-json"' in markup
    assert 'id="history-search"' in markup
    assert 'id="clear-history"' in markup
    assert "history-mini-action" in script
    assert "function renderHistory()" in script
    assert "function exportConversation" in script
    assert "function safeMediaSrc" in script
    assert 'key.value=""' not in script


def _registered_website():
    website = _website()
    for index, (route, config) in enumerate(website.routes.items()):
        website.app.add_url_rule(
            route,
            endpoint=f"rocksoul_test_{index}",
            view_func=config["function"],
            methods=config["methods"],
        )
    return website.app.test_client()


def test_registered_flask_routes_serve_rocksoul_for_primary_pages(monkeypatch):
    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "1")
    client = _registered_website()
    paths = (
        "/", "/home.html", "/index.html", "/chat/", "/chat/index.html",
        "/providers", "/providers/", "/providers.html", "/providers/ExampleProvider",
        "/status", "/status/", "/stats", "/stats/", "/logs", "/logs/",
        "/agent", "/agent/", "/browser", "/browser/", "/playground/",
        "/playground/anything", "/apps/", "/apps/nested/page",
        "/private/", "/private/nested/page",
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers.get("X-ROCKSOUL-UI") == "1", path


def test_registered_flask_routes_preserve_legacy_fallback(monkeypatch):
    import g4f.gui.server.website as website_module

    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "0")
    monkeypatch.setattr(website_module, "render", lambda filename: f"legacy:{filename}")
    client = _registered_website()
    cases = {
        "/": "legacy:home",
        "/chat/": "legacy:chat/index",
        "/status/": "legacy:status",
        "/stats/": "legacy:stats",
        "/logs/": "legacy:logs",
        "/agent/": "legacy:agent",
        "/browser/": "legacy:browser",
        "/apps/": "legacy:apps/index.html",
        "/private/": "legacy:private/index",
    }
    for path, expected in cases.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.get_data(as_text=True) == expected, path


def test_registered_provider_catalog_uses_legacy_template_when_disabled(monkeypatch):
    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "0")
    website = _website()
    monkeypatch.setattr(website, "_get_providers", lambda: [])
    for index, (route, config) in enumerate(website.routes.items()):
        website.app.add_url_rule(
            route,
            endpoint=f"provider_legacy_test_{index}",
            view_func=config["function"],
            methods=config["methods"],
        )
    response = website.app.test_client().get("/providers/")
    assert response.status_code == 200
    assert response.headers.get("X-ROCKSOUL-UI") is None
    assert b"Providers" in _body(response)


def test_canonical_compose_binds_gui_and_api_ports_to_loopback():
    from pathlib import Path

    compose = (Path(__file__).parents[1] / "docker-compose.yml").read_text(encoding="utf-8")
    assert "127.0.0.1:8080:8080" in compose
    assert "127.0.0.1:1337:8080" in compose
    assert "127.0.0.1:7900:7900" in compose
    assert "\n      - '8080:8080'" not in compose
    assert "\n      - '1337:8080'" not in compose



def test_privileged_gui_guard_allows_loopback_without_api_key(monkeypatch):
    from g4f.config import AppConfig
    from g4f.gui.server.backend_api import _privileged_request_allowed

    monkeypatch.setattr(AppConfig, "g4f_api_key", None)
    app = Flask(__name__)
    with app.test_request_context("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
        assert _privileged_request_allowed()


def test_privileged_gui_guard_rejects_remote_without_api_key(monkeypatch):
    from g4f.config import AppConfig
    from g4f.gui.server.backend_api import _privileged_request_allowed

    monkeypatch.setattr(AppConfig, "g4f_api_key", None)
    monkeypatch.delenv("G4F_API_KEY", raising=False)
    monkeypatch.delenv("G4F_GUI_TRUSTED_IPS", raising=False)
    app = Flask(__name__)
    with app.test_request_context("/", environ_base={"REMOTE_ADDR": "203.0.113.10"}):
        assert not _privileged_request_allowed()


def test_privileged_gui_guard_requires_matching_remote_api_key(monkeypatch):
    from g4f.config import AppConfig
    from g4f.gui.server.backend_api import _privileged_request_allowed

    monkeypatch.setattr(AppConfig, "g4f_api_key", "test-secret")
    monkeypatch.setenv("G4F_API_KEY", "test-secret")
    monkeypatch.delenv("G4F_GUI_TRUSTED_IPS", raising=False)
    app = Flask(__name__)
    with app.test_request_context(
        "/", environ_base={"REMOTE_ADDR": "203.0.113.10"},
        headers={"x-api-key": "wrong-secret"},
    ):
        assert not _privileged_request_allowed()
    with app.test_request_context(
        "/", environ_base={"REMOTE_ADDR": "203.0.113.10"},
        headers={"Authorization": "Bearer test-secret"},
    ):
        assert _privileged_request_allowed()



def test_rocksoul_accessibility_landmarks_and_keyboard_styles():
    from pathlib import Path

    asset_dir = Path(__file__).parents[1] / "g4f" / "gui" / "rocksoul"
    markup = (asset_dir / "index.html").read_text(encoding="utf-8")
    styles = (asset_dir / "app.css").read_text(encoding="utf-8")
    script = (asset_dir / "app.js").read_text(encoding="utf-8")

    assert 'class="skip-link" href="#main-content"' in markup
    assert 'id="main-content" tabindex="-1"' in markup
    assert 'aria-label="ROCKSOUL workspace sidebar"' in markup
    assert 'aria-label="Conversation" aria-live="polite"' in markup
    assert ":focus-visible" in styles
    assert "prefers-reduced-motion:reduce" in styles
    assert 'setAttribute("aria-current","page")' in script


def test_rocksoul_locale_catalog_supports_indonesian_and_english():
    from pathlib import Path

    asset_dir = Path(__file__).parents[1] / "g4f" / "gui" / "rocksoul"
    markup = (asset_dir / "index.html").read_text(encoding="utf-8")
    locale = (asset_dir / "locale.js").read_text(encoding="utf-8")

    assert 'src="/rocksoul-assets/locale.js" defer' in markup
    assert 'id="locale-select"' in locale
    assert '"id"' in locale and '"en"' in locale
    assert "Ringkasan" in locale
    assert "safeWrite(locale)" in locale
    assert "rocksoul-locale" in locale


def test_rocksoul_document_upload_uses_existing_g4f_file_api():
    from pathlib import Path

    asset_dir = Path(__file__).parents[1] / "g4f" / "gui" / "rocksoul"
    script = (asset_dir / "app.js").read_text(encoding="utf-8")
    markup = (asset_dir / "index.html").read_text(encoding="utf-8")

    assert "extractDocumentText" in script
    assert "/backend-api/v2/files/" in script
    assert "Document context:" in script
    assert "documentExtensions" in script
    assert ".pdf" in markup and ".docx" in markup and ".xlsx" in markup
    assert 'method:"DELETE"' in script


def test_opt_in_provider_smoke_harness_is_credential_safe():
    from pathlib import Path

    script = (Path(__file__).parents[1] / "tests" / "rocksoul-provider-smoke.mjs").read_text(encoding="utf-8")

    assert 'process.env.ROCKSOUL_SMOKE !== "1"' in script
    assert "ROCKSOUL_SMOKE_MODEL" in script
    assert "model_discovery" in script
    assert "non_streaming" in script
    assert "streaming" in script
    assert "process.env.G4F_API_KEY" in script
    assert "process.stdout.write(JSON.stringify(report" in script
    assert "console.log(apiKey)" not in script



def test_rocksoul_apps_page_does_not_advertise_unsafe_or_missing_launch_urls():
    from pathlib import Path

    script = (Path(__file__).parents[1] / "g4f" / "gui" / "rocksoul" / "app.js").read_text(encoding="utf-8")
    assert 'const destination=safeHref(app.url||app.homepage||"")' in script
    assert 'if(destination!=="#")target.append(card' in script
    assert "NO LAUNCH URL" in script
    assert "This extension is registered, but the runtime did not provide a safe launch URL." in script


def test_canonical_compose_has_healthcheck_restart_and_api_key_configuration():
    from pathlib import Path

    compose = (Path(__file__).parents[1] / "docker-compose.yml").read_text(encoding="utf-8")
    assert "restart: unless-stopped" in compose
    assert "init: true" in compose
    assert "healthcheck:" in compose
    assert "/backend-api/v2/status" in compose
    assert "G4F_API_KEY=${G4F_API_KEY:-}" in compose
    assert "G4F_GUI_TRUSTED_IPS=" in compose
    assert "g4f-data:/data/g4f" in compose



def test_privileged_gui_guard_accepts_explicit_trusted_network(monkeypatch):
    from g4f.config import AppConfig
    from g4f.gui.server.backend_api import _privileged_request_allowed

    monkeypatch.setattr(AppConfig, "g4f_api_key", None)
    monkeypatch.delenv("G4F_API_KEY", raising=False)
    monkeypatch.setenv("G4F_GUI_TRUSTED_IPS", "172.16.0.0/12,192.168.65.1/32")
    app = Flask(__name__)
    with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.65.1"}):
        assert _privileged_request_allowed()



def test_privileged_backend_route_families_invoke_the_shared_guard():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "g4f" / "gui" / "server" / "backend_api.py").read_text(encoding="utf-8")
    for marker in (
        "async def handle_webmcp_tools():",
        "def handle_log():",
        "def add_usage():",
        "def get_usage(date: str):",
        "def get_stats():",
        "def stream_files(bucket_id: str, event_stream=True):",
        "def manage_files(bucket_id: str, event_stream=False):",
        "def upload_files(bucket_id: str):",
        "def upload_cookies():",
        "def upload_chat(share_id: str) -> dict:",
    ):
        start = source.find(marker)
        assert start >= 0, marker
        guard = source.find("if not _privileged_request_allowed():", start, start + 700)
        assert guard >= 0, marker



def _registered_backend_guard_client(monkeypatch):
    from types import SimpleNamespace
    import g4f.gui.server.backend_api as backend_module

    class FakeMCPServer:
        def get_tool_list(self):
            return [{"name": "safe_test_tool"}]

        async def handle_request(self, request):
            return SimpleNamespace(error=None, result={"ok": True})

    monkeypatch.setattr(backend_module, "Client", lambda: object())
    monkeypatch.setattr(backend_module, "_get_webmcp_server", lambda: FakeMCPServer())
    monkeypatch.setattr(backend_module, "has_crypto", False)
    app = Flask("rocksoul-backend-guard-test")
    backend_module.Backend_Api(app)
    return app.test_client()


def test_registered_privileged_backend_routes_reject_untrusted_remote_calls(monkeypatch):
    from g4f.config import AppConfig

    monkeypatch.setattr(AppConfig, "g4f_api_key", None)
    monkeypatch.delenv("G4F_API_KEY", raising=False)
    monkeypatch.delenv("G4F_GUI_TRUSTED_IPS", raising=False)
    client = _registered_backend_guard_client(monkeypatch)
    remote = {"REMOTE_ADDR": "203.0.113.10"}

    cases = (
        ("GET", "/backend-api/v2/webmcp/tools"),
        ("GET", "/backend-api/v2/log"),
        ("POST", "/backend-api/v2/upload_cookies"),
        ("POST", "/backend-api/v2/files/guard-test"),
        ("POST", "/backend-api/v2/chat/guard-test"),
    )
    for method, path in cases:
        response = client.open(path, method=method, json={}, environ_base=remote)
        assert response.status_code == 403, (method, path, response.get_data(as_text=True))


def test_registered_privileged_backend_routes_allow_loopback_and_valid_key(monkeypatch):
    from g4f.config import AppConfig

    monkeypatch.setattr(AppConfig, "g4f_api_key", "route-test-secret")
    monkeypatch.setenv("G4F_API_KEY", "route-test-secret")
    monkeypatch.delenv("G4F_GUI_TRUSTED_IPS", raising=False)
    client = _registered_backend_guard_client(monkeypatch)

    local = client.get("/backend-api/v2/webmcp/tools", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert local.status_code == 200
    assert local.get_json()["tools"][0]["name"] == "safe_test_tool"

    remote = client.get(
        "/backend-api/v2/webmcp/tools",
        headers={"x-api-key": "route-test-secret"},
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
    )
    assert remote.status_code == 200
