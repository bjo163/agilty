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
    app = Flask(__name__)
    with app.test_request_context("/", environ_base={"REMOTE_ADDR": "203.0.113.10"}):
        assert not _privileged_request_allowed()


def test_privileged_gui_guard_requires_matching_remote_api_key(monkeypatch):
    from g4f.config import AppConfig
    from g4f.gui.server.backend_api import _privileged_request_allowed

    monkeypatch.setattr(AppConfig, "g4f_api_key", "test-secret")
    monkeypatch.setenv("G4F_API_KEY", "test-secret")
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
