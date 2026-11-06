import pytest
from flask import Flask
from werkzeug.exceptions import NotFound

from g4f.gui.server.website import Website


def _website():
    return Website(Flask(__name__))


def test_root_serves_bundled_rocksoul_ui_by_default(monkeypatch):
    monkeypatch.delenv("ROCKSOUL_UI_ENABLED", raising=False)
    website = _website()

    with website.app.test_request_context("/"):
        response = website._index()

    assert response.status_code == 200
    assert response.headers.get("X-ROCKSOUL-UI") == "1"
    assert b"ROCKSOUL" in response.get_data()


def test_chat_route_serves_same_rocksoul_app_shell(monkeypatch):
    monkeypatch.setenv("ROCKSOUL_UI_ENABLED", "true")
    website = _website()

    with website.app.test_request_context("/chat/"):
        response = website._chat()

    assert response.status_code == 200
    assert response.headers.get("X-ROCKSOUL-UI") == "1"
    assert b'id="composer"' in response.get_data()


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
    assert b".app-shell" in response.get_data()
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
        assert marker in response.get_data()


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


def test_ui_assets_include_stream_cancellation_and_sse_flush():
    from pathlib import Path

    asset_dir = Path(__file__).parents[1] / "g4f" / "gui" / "rocksoul"
    script = (asset_dir / "app.js").read_text(encoding="utf-8")
    markup = (asset_dir / "index.html").read_text(encoding="utf-8")
    styles = (asset_dir / "app.css").read_text(encoding="utf-8")

    assert "new AbortController()" in script
    assert 'if(buffer.trim())consumeLine(buffer.trim())' in script
    assert 'id="stop"' in markup
    assert ".stop-button" in styles
