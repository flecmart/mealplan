import html
import io
import json
import os
import re
import time
import urllib.request
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from itsdangerous import TimestampSigner
from application import create_app  # Assuming your Flask app factory is here
from application import helper_functs
from application.models import Recipe


def _dev_server_reachable(url, timeout=2):
    """Return True if an HTTP server answers at ``url`` within ``timeout`` seconds."""
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def app():
    """Create and configure a test Flask application.

    Session-scoped on purpose: routes are registered via ``@current_app.route``
    when ``application.routes`` is first imported, which only happens once per
    process. A fresh ``create_app()`` per test would therefore have no routes
    registered on it, so we build the app once and share it.
    """
    app = create_app()  # Initialize your Flask app
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    # You might need to configure other settings for testing
    with app.app_context():
        yield app

@pytest.fixture
def client(app):
    """A test client for the Flask application."""
    return app.test_client()

@pytest.fixture
def csrf_client(app):
    app.config['WTF_CSRF_ENABLED'] = True
    with app.app_context():
        yield app.test_client()
    app.config['WTF_CSRF_ENABLED'] = False

@pytest.mark.skipif(os.getenv("CI") == "true",
                    reason="integration test needs Chromium + DB; skipped in CI")
def test_screenshot_week_generates_image(client, app):
    """Test that the /week route generates and saves the week.png image.

    INTEGRATION TEST — PREREQUISITE: a running Flask dev server.
    The /week handler launches headless Chromium and navigates to BASE_URL
    (default http://localhost:5000/), so it needs the dev server (and its DB) up
    and serving the calendar page. It does NOT screenshot this test client.

    To run locally, start the stack first, e.g.:
        docker compose -f docker-compose.dev.yml up app
    then run pytest with CI unset. If the server is not reachable the test skips
    with an explanatory message (rather than a confusing assertion failure).
    """
    base_url = os.environ.get("BASE_URL", "http://localhost:5000/")
    if not _dev_server_reachable(base_url):
        pytest.skip(
            f"Flask dev server not reachable at {base_url}. "
            "Did you forget to start it? e.g. `docker compose -f docker-compose.dev.yml up app` "
            "(see this test's docstring)."
        )

    # Define the expected path of the saved image
    expected_image_path = '/home/mealplan/application/static/week.png'

    # Ensure the image doesn't exist before the test
    if os.path.exists(expected_image_path):
        os.remove(expected_image_path)

    # Call the /week route
    try:
        response = client.get('/week')
    except:
        pass # ignore that the redirect won't work in devcontainer 

    # Assert that the image file now exists
    assert os.path.exists(expected_image_path)

    # Optionally, you can check the file size or other properties
    file_size = os.path.getsize(expected_image_path)
    assert file_size > 0

    # Clean up the image file after the test
    os.remove(expected_image_path)


# --- internal cookidoo sync-status endpoint (DB mocked, no live DB needed) ----

def test_internal_sync_status_marks_recipe_stale(csrf_client):
    recipe = MagicMock()
    with patch("application.routes.Recipe") as R, patch("application.routes.db") as db_mock:
        R.query.filter_by.return_value.first.return_value = recipe
        resp = csrf_client.post("/internal/cookidoo-sync-status",
                           json={"cookidoo_id": "r801516", "stale": True})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True and body["matched"] is True
    assert recipe.cookidoo_sync_error is True
    db_mock.session.commit.assert_called_once()


def test_internal_sync_status_clears_flag(client):
    recipe = MagicMock()
    with patch("application.routes.Recipe") as R, patch("application.routes.db"):
        R.query.filter_by.return_value.first.return_value = recipe
        resp = client.post("/internal/cookidoo-sync-status",
                           json={"cookidoo_id": "r801516", "stale": False})

    assert resp.status_code == 200
    assert recipe.cookidoo_sync_error is False


def test_internal_sync_status_unknown_id_is_noop(client):
    with patch("application.routes.Recipe") as R, patch("application.routes.db") as db_mock:
        R.query.filter_by.return_value.first.return_value = None
        resp = client.post("/internal/cookidoo-sync-status",
                           json={"cookidoo_id": "rX", "stale": True})

    assert resp.status_code == 200
    assert resp.get_json()["matched"] is False
    db_mock.session.commit.assert_not_called()


def test_internal_sync_status_missing_id_returns_400(client):
    resp = client.post("/internal/cookidoo-sync-status", json={"stale": True})
    assert resp.status_code == 400


def test_internal_sync_status_rejects_form_post(csrf_client):
    with patch("application.routes.Recipe"), patch("application.routes.db") as db_mock:
        resp = csrf_client.post("/internal/cookidoo-sync-status",
                                data={"cookidoo_id": "r801516", "stale": "true"})

    assert resp.status_code == 415
    db_mock.session.commit.assert_not_called()


# --- editing the cookidoo id via the edit-recipe form (DB mocked) ------------

def _edit_recipe(client, cookidoo_value, icon="pasta.png"):
    with patch("application.routes.database.update_instance") as update_instance, \
         patch("application.routes.Recipe") as R:
        R.query.filter_by.return_value.first.return_value = None  # no name clash
        client.post("/edit-recipe", data={
            "id": "1", "name": "Testrezept", "time": "20",
            "ingredients": "Mehl\nZucker", "instructions": "verrühren",
            "icon": icon,
            "cookidoo_recipe_id": cookidoo_value,
            "image": (io.BytesIO(b""), ""),
        }, content_type="multipart/form-data")
    return update_instance


def test_edit_recipe_extracts_id_from_url_and_clears_flag(client):
    update_instance = _edit_recipe(
        client, "https://cookidoo.de/recipes/recipe/de-DE/r801516")

    kwargs = update_instance.call_args.kwargs
    assert kwargs["cookidoo_recipe_id"] == "r801516"
    assert kwargs["cookidoo_sync_error"] is False


def test_edit_recipe_keeps_bare_id(client):
    update_instance = _edit_recipe(client, "r801516")
    assert update_instance.call_args.kwargs["cookidoo_recipe_id"] == "r801516"


def test_edit_recipe_empty_cookidoo_clears_id(client):
    update_instance = _edit_recipe(client, "")
    assert update_instance.call_args.kwargs["cookidoo_recipe_id"] is None


@pytest.fixture
def secret_file_url(tmp_path):
    secret = tmp_path / "secret"
    secret.write_bytes(b"TOP-SECRET")
    return f"{secret.as_uri()}#https://example.com/"


def _saved_images(add_instance):
    return [c.kwargs.get("image") for c in add_instance.call_args_list]


def test_import_recipe_refuses_file_image_url(client, secret_file_url):
    scraped = helper_functs.RecipeCache(
        name="Rezept", time=20, ingredients="Ei", instructions="kochen",
        icon="egg.png", image_url=secret_file_url, cookidoo_id=None)
    with patch("application.routes.helper_functs.scrape_recipe", return_value=scraped), \
         patch("application.routes.database.add_instance") as add_instance:
        client.post("/import-recipe", data={"link": "https://example.com/r", "icon": "egg.png"})

    assert b"TOP-SECRET" not in _saved_images(add_instance)


def test_import_cookidoo_instructions_refuses_file_image_url(client, secret_file_url):
    with client.session_transaction() as session:
        session["import_recipe_cache"] = {
            "name": "Rezept", "time": 20, "ingredients": "Ei", "instructions": "",
            "icon": "egg.png", "image_url": secret_file_url, "cookidoo_id": None,
        }
    with patch("application.routes.database.add_instance") as add_instance:
        resp = client.post("/import-cookidoo-instructions", data={"instructions": "kochen"})

    assert resp.status_code == 302
    assert b"TOP-SECRET" not in _saved_images(add_instance)


XSS_ICON = 'x"onerror="alert(1)'


def _add_recipe(client, icon):
    with patch("application.routes.database.add_instance") as add_instance, \
         patch("application.routes.Recipe") as R:
        R.query.filter_by.return_value.first.return_value = None
        client.post("/add-recipe", data={
            "name": "Testrezept", "time": "20",
            "ingredients": "Mehl", "instructions": "verrühren",
            "icon": icon,
            "image": (io.BytesIO(b""), ""),
        }, content_type="multipart/form-data")
    return add_instance


def test_add_recipe_rejects_unknown_icon(client):
    assert not _add_recipe(client, XSS_ICON).called


def test_add_recipe_accepts_known_icon(client):
    assert _add_recipe(client, "pasta.png").call_args.kwargs["icon"] == "pasta.png"


def test_add_recipe_defaults_empty_icon(client):
    assert _add_recipe(client, "").call_args.kwargs["icon"] == "defaultIcon.png"


def test_edit_recipe_without_icon_keeps_current_icon(client):
    assert "icon" not in _edit_recipe(client, "", icon="").call_args.kwargs


def test_edit_recipe_rejects_unknown_icon(client):
    assert not _edit_recipe(client, "", icon=XSS_ICON).called


def test_recipe_page_passes_stored_icon_to_js_as_string_literal(client):
    stored_icon = "');alert(1)//"
    page = _recipe_page(client, icon=stored_icon)

    handler = re.search(r"""onclick=(["'])setPreselectedIcon\((.*?)\)\1""", page)
    assert json.loads(html.unescape(handler.group(2))) == stored_icon


def test_import_recipe_rejects_unknown_icon(client):
    with patch("application.routes.helper_functs.scrape_recipe") as scrape_recipe:
        client.post("/import-recipe", data={"link": "https://example.com/r", "icon": XSS_ICON})

    assert not scrape_recipe.called


def _calendar_page(client):
    with patch("application.routes.database.query_all", return_value=[]):
        return client.get("/").get_data(as_text=True)


def _recipe_page(client, icon="egg.png"):
    recipe = Recipe(name="Rezept", ingredients="Ei", instructions="kochen", time=20,
                    icon=icon, image=None, cookidoo_recipe_id=None)
    recipe.id = 1
    with patch("application.routes.Recipe") as R:
        R.query.filter_by.return_value.first.return_value = recipe
        return client.get("/recipe/1").get_data(as_text=True)


def _meta_csrf_token(page):
    return re.search(r'<meta name="csrf-token" content="([^"]+)"', page).group(1)


def _form_csrf_token(page):
    return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)


def _delete_recipe(client, **kwargs):
    with patch("application.routes.Event"), patch("application.routes.Recipe"), \
         patch("application.routes.db") as db_mock:
        resp = client.post("/delete-recipe", **kwargs)
    return resp, db_mock.session.commit.called


def test_form_post_without_csrf_token_returns_to_page_with_message(csrf_client):
    resp, committed = _delete_recipe(
        csrf_client, data={"id": "1"}, headers={"Referer": "http://localhost/recipe/1"})

    assert not committed
    assert resp.status_code == 302
    assert resp.headers["Location"] == "http://localhost/recipe/1"
    with csrf_client.session_transaction() as session:
        assert session["_flashes"]


def test_form_post_without_csrf_token_never_redirects_off_site(csrf_client):
    resp, _ = _delete_recipe(
        csrf_client, data={"id": "1"}, headers={"Referer": "https://evil.example/"})

    assert resp.headers["Location"] == "/full-calendar"


def test_ajax_post_without_csrf_token_tells_page_to_reload(csrf_client):
    resp, committed = _delete_recipe(
        csrf_client, data={"id": "1"}, headers={"X-Requested-With": "XMLHttpRequest"})

    assert not committed
    assert resp.status_code == 400
    assert resp.get_json() == {"success": False, "error": "csrf"}


@pytest.mark.parametrize("render", [_calendar_page, _recipe_page])
def test_every_post_form_carries_csrf_token(csrf_client, render):
    forms = re.findall(r'<form[^>]*method="post".*?</form>', render(csrf_client), re.S)

    assert forms
    for form in forms:
        assert 'name="csrf_token"' in form


def test_form_post_with_page_csrf_token_is_accepted(csrf_client):
    token = _form_csrf_token(_calendar_page(csrf_client))

    _, committed = _delete_recipe(csrf_client, data={"id": "1", "csrf_token": token})

    assert committed


def test_session_cookie_survives_browser_restart(client):
    with patch("application.routes.database.query_all", return_value=[]):
        resp = client.get("/")

    assert "Expires=" in resp.headers["Set-Cookie"]


def test_csrf_token_from_long_open_tab_is_still_accepted(csrf_client):
    token = _form_csrf_token(_calendar_page(csrf_client))
    a_day_later = int(time.time()) + 24 * 3600

    with patch.object(TimestampSigner, "get_timestamp", return_value=a_day_later):
        _, committed = _delete_recipe(csrf_client, data={"id": "1", "csrf_token": token})

    assert committed


def test_ajax_post_with_meta_csrf_token_header_is_accepted(csrf_client):
    token = _meta_csrf_token(_calendar_page(csrf_client))

    _, committed = _delete_recipe(csrf_client, data={"id": "1"}, headers={"X-CSRFToken": token})

    assert committed


def test_purge_rejects_get(client):
    assert client.get("/purge").status_code == 405


def test_purge_rejects_form_post(csrf_client):
    with patch("application.routes.Event") as E, patch("application.routes.db"):
        resp = csrf_client.post("/purge", data={"before": "2026-01-01"})

    assert resp.status_code == 415
    E.query.filter.assert_not_called()


def test_purge_accepts_json_without_csrf_token(csrf_client):
    with patch("application.routes.Event") as E, patch("application.routes.db") as db_mock:
        E.date.__le__.return_value = "before-clause"
        resp = csrf_client.post("/purge", json={"before": "2026-01-01"})

    assert resp.status_code == 200
    E.date.__le__.assert_called_once_with("2026-01-01")
    E.query.filter.assert_called_once_with("before-clause")
    db_mock.session.commit.assert_called_once()