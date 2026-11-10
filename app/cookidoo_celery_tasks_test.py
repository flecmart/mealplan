import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import aiohttp
import pytest
from cookidoo_api import Cookidoo, CookidooAuthException, CookidooConfigException

import application.cookidoo_celery_tasks as tasks


def _make_cookidoo_client():
    """A mock that only has the methods the real Cookidoo class has.

    autospec makes calls to non-existent methods fail (e.g. the removed
    load_cookies/save_cookies), so tests catch library API changes instead
    of hiding them like a plain MagicMock would.
    """
    return create_autospec(Cookidoo, instance=True)


async def _authenticate(client):
    """Await tasks._authenticated_cookidoo with Cookidoo + localization mocked out."""
    fake_localization = AsyncMock(return_value=[{"country_code": "de"}])
    with patch.object(tasks, "Cookidoo", return_value=client), \
         patch.object(tasks, "get_localization_options", fake_localization):
        return await tasks._authenticated_cookidoo(session=MagicMock())


# --- library API contract ---------------------------------------------------

@pytest.mark.parametrize(
    "method",
    ["load_token", "save_token", "login", "get_user_info",
     "add_recipes_to_calendar", "remove_recipe_from_calendar"],
)
def test_cookidoo_api_provides_methods_we_use(method):
    # Fails loudly if a cookidoo-api upgrade renames or removes a method we call.
    assert hasattr(Cookidoo, method), f"cookidoo-api no longer provides Cookidoo.{method}"


# --- _authenticated_cookidoo: validate-then-relogin fallback -----------------

@pytest.mark.asyncio
async def test_valid_token_reuses_session_without_relogin():
    client = _make_cookidoo_client()  # load_token + get_user_info both succeed

    result = await _authenticate(client)

    assert result is client
    client.load_token.assert_called_once()
    client.get_user_info.assert_awaited_once()
    client.login.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejected_token_triggers_relogin():
    client = _make_cookidoo_client()
    # Stored tokens are no longer accepted: the validation call fails with an auth error.
    client.get_user_info.side_effect = CookidooAuthException("401")

    await _authenticate(client)

    client.get_user_info.assert_awaited_once()
    client.login.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_token_file_triggers_relogin():
    client = _make_cookidoo_client()
    # No token file yet (first run / new container): load_token raises before validation.
    client.load_token.side_effect = FileNotFoundError()

    await _authenticate(client)

    client.get_user_info.assert_not_awaited()
    client.login.assert_awaited_once()


@pytest.mark.asyncio
async def test_corrupt_token_file_triggers_relogin():
    client = _make_cookidoo_client()
    # Unparseable file content (e.g. truncated JSON raises a ValueError subclass).
    client.load_token.side_effect = ValueError("bad token file")

    await _authenticate(client)

    client.login.assert_awaited_once()


@pytest.mark.asyncio
async def test_cookidoo_exception_on_load_triggers_relogin():
    client = _make_cookidoo_client()
    # A CookidooException subclass raised by load_token must also fall back.
    client.load_token.side_effect = CookidooConfigException("bad token file")

    await _authenticate(client)

    client.login.assert_awaited_once()


# --- tasks persist the (possibly refreshed) token -----------------------------

@pytest.mark.parametrize(
    "task, api_method",
    [
        (tasks.add_recipe_to_cookidoo_calendar, "add_recipes_to_calendar"),
        (tasks.remove_recipe_from_cookidoo_calendar, "remove_recipe_from_calendar"),
    ],
)
def test_task_calls_api_and_saves_token(task, api_method):
    client = _make_cookidoo_client()
    with patch.object(tasks, "_authenticated_cookidoo", AsyncMock(return_value=client)):
        task.run("r801516", "2026-07-15")

    getattr(client, api_method).assert_awaited_once()
    # The library may refresh/rotate tokens during the request, so the token
    # must be written back after every task, not only after a fresh login.
    client.save_token.assert_called_once()


# --- task retry configuration -------------------------------------------------

@pytest.mark.parametrize(
    "task",
    [tasks.add_recipe_to_cookidoo_calendar, tasks.remove_recipe_from_cookidoo_calendar],
)
def test_task_retry_configuration(task):
    assert task.max_retries == 5
    # Retries must span minutes, not seconds, so short outages don't become
    # permanent failures (~30s, 60s, 120s, 240s, 480s, capped at 900s).
    assert task.retry_backoff == 30
    assert task.retry_backoff_max == 900
    assert task.retry_jitter is True
    # autoretry_for is what actually engages retry_backoff (via Celery's
    # autoretry wrapper); without it, max_retries/backoff are inert.
    assert task.autoretry_for == (Exception,)
    assert hasattr(task, "_orig_run"), "autoretry wrapper should be installed"


# --- CookidooTask logging hooks ----------------------------------------------

def test_on_retry_logs_warning(caplog):
    task = tasks.add_recipe_to_cookidoo_calendar
    with caplog.at_level(logging.WARNING, logger="application.cookidoo_celery_tasks"):
        task.on_retry(RuntimeError("boom"), "task-id", (), {}, None)

    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert "Retrying" in caplog.text
    assert "boom" in caplog.text


def test_on_failure_logs_error_with_traceback(caplog):
    task = tasks.add_recipe_to_cookidoo_calendar
    try:
        raise RuntimeError("permanent failure")
    except RuntimeError as exc:
        with caplog.at_level(logging.ERROR, logger="application.cookidoo_celery_tasks"):
            with patch.object(tasks, "_report_sync_status"):
                task.on_failure(exc, "task-id", ("r123",), {}, None)

    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error_records, "expected an error log record"
    assert "failed permanently" in caplog.text
    # exc_info must be attached so the traceback is emitted.
    assert error_records[0].exc_info is not None


def test_on_failure_log_includes_exception_type(caplog):
    # The type name is logged so we can identify what a genuinely invalid
    # recipe id raises and refine the stale detection later.
    task = tasks.add_recipe_to_cookidoo_calendar
    with caplog.at_level(logging.ERROR, logger="application.cookidoo_celery_tasks"):
        with patch.object(tasks, "_report_sync_status"):
            task.on_failure(ValueError("bad id"), "task-id", ("r0",), {}, None)

    assert "ValueError" in caplog.text


# --- stale-link reporting: add task ------------------------------------------

def test_add_task_failure_reports_recipe_stale():
    task = tasks.add_recipe_to_cookidoo_calendar
    with patch.object(tasks, "_report_sync_status") as report:
        task.on_failure(RuntimeError("boom"), "task-id", ("r801516", "2026-07-15"), {}, None)
    report.assert_called_once_with("r801516", True)


def test_add_task_success_clears_recipe_stale():
    task = tasks.add_recipe_to_cookidoo_calendar
    with patch.object(tasks, "_report_sync_status") as report:
        task.on_success(None, "task-id", ("r801516", "2026-07-15"), {})
    report.assert_called_once_with("r801516", False)


@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("recipe not found"),
        CookidooAuthException("login failed"),
        aiohttp.ClientConnectionError("connection reset"),
        asyncio.TimeoutError(),
        AttributeError("'Cookidoo' object has no attribute 'load_cookies'"),
    ],
    ids=["recipe", "auth", "client-error", "timeout", "attribute-error"],
)
def test_add_task_failure_reports_sync_error_for_any_cause(exc):
    # Every permanent add failure means the meal isn't in Cookidoo,
    # so the UI must show it regardless of the cause.
    task = tasks.add_recipe_to_cookidoo_calendar
    with patch.object(tasks, "_report_sync_status") as report:
        task.on_failure(exc, "task-id", ("r801516", "2026-07-15"), {}, None)
    report.assert_called_once_with("r801516", True)


# --- stale-link reporting: remove task ---------------------------------------

def test_remove_task_failure_never_reports_stale():
    # Removing a recipe that isn't on the Cookidoo calendar fails too;
    # that says nothing about whether the link is valid.
    task = tasks.remove_recipe_from_cookidoo_calendar
    with patch.object(tasks, "_report_sync_status") as report:
        task.on_failure(RuntimeError("not on calendar"), "task-id", ("r801516", "2026-07-15"), {}, None)
    report.assert_not_called()


def test_remove_task_success_does_not_touch_stale_flag():
    task = tasks.remove_recipe_from_cookidoo_calendar
    with patch.object(tasks, "_report_sync_status") as report:
        task.on_success(None, "task-id", ("r801516", "2026-07-15"), {})
    report.assert_not_called()


# --- _report_sync_status ------------------------------------------------------

def test_report_sync_status_posts_expected_payload():
    with patch("urllib.request.urlopen") as urlopen:
        tasks._report_sync_status("r801516", True)

    urlopen.assert_called_once()
    req = urlopen.call_args.args[0]
    assert req.full_url.endswith("/internal/cookidoo-sync-status")
    assert req.method == "POST"
    body = json.loads(req.data.decode())
    assert body == {"cookidoo_id": "r801516", "stale": True}


def test_report_sync_status_swallows_errors(caplog):
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        with caplog.at_level(logging.WARNING, logger="application.cookidoo_celery_tasks"):
            # must not raise
            tasks._report_sync_status("r801516", True)
    assert "Could not report cookidoo sync status" in caplog.text


def test_report_sync_status_noop_without_id():
    with patch("urllib.request.urlopen") as urlopen:
        tasks._report_sync_status(None, True)
        tasks._report_sync_status("", False)
    urlopen.assert_not_called()
