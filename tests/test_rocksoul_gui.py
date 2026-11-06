import os

from flask import Flask

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
    assert response.headers.get("Cache-Control") == "public, max-age=31536000, immutable"
