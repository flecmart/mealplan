import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cookidoo_api import CookidooAuthException, CookidooConfigException

import application.cookidoo_celery_tasks as tasks


def _make_cookidoo_client():
    """A mock Cookidoo client with the methods _authenticated_cookidoo uses."""
    client = MagicMock()
    client.load_cookies = MagicMock()
    client.save_cookies = MagicMock()
    client.get_user_info = AsyncMock()
    client.login = AsyncMock()
    return client


async def _authenticate(client):
    """Await tasks._authenticated_cookidoo with Cookidoo + localization mocked out."""
    fake_localization = AsyncMock(return_value=[{"country_code": "de"}])
    with patch.object(tasks, "Cookidoo", return_value=client), \
         patch.object(tasks, "get_localization_options", fake_localization):
        return await tasks._authenticated_cookidoo(session=MagicMock())


# --- _authenticated_cookidoo: validate-then-relogin fallback -----------------

@pytest.mark.asyncio
async def test_valid_cookies_reuse_session_without_relogin():
    client = _make_cookidoo_client()  # load_cookies + get_user_info both succeed

    result = await _authenticate(client)

    assert result is client
    client.load_cookies.assert_called_once()
    client.get_user_info.assert_awaited_once()
    client.login.assert_not_awaited()
    client.save_cookies.assert_not_called()


@pytest.mark.asyncio
async def test_expired_cookies_trigger_relogin():
    client = _make_cookidoo_client()
    # Loaded cookies are stale: the validation call fails with an auth error.
    client.get_user_info.side_effect = CookidooAuthException("401")

    await _authenticate(client)

    client.get_user_info.assert_awaited_once()
    client.login.assert_awaited_once()
    client.save_cookies.assert_called_once()


@pytest.mark.asyncio
async def test_missing_cookie_file_triggers_relogin():
    client = _make_cookidoo_client()
    # No cookie file yet (first run): load_cookies raises before validation.
    client.load_cookies.side_effect = FileNotFoundError()

    await _authenticate(client)

    client.get_user_info.assert_not_awaited()
    client.login.assert_awaited_once()
    client.save_cookies.assert_called_once()


@pytest.mark.asyncio
async def test_unparseable_cookie_file_triggers_relogin():
    client = _make_cookidoo_client()
    # A CookidooException subclass raised by load_cookies must also fall back.
    client.load_cookies.side_effect = CookidooConfigException("bad cookie file")

    await _authenticate(client)

    client.login.assert_awaited_once()
    client.save_cookies.assert_called_once()


# --- task retry configuration -------------------------------------------------

@pytest.mark.parametrize(
    "task",
    [tasks.add_recipe_to_cookidoo_calendar, tasks.remove_recipe_from_cookidoo_calendar],
)
def test_task_retry_configuration(task):
    assert task.max_retries == 3
    assert task.retry_backoff is True
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
            task.on_failure(exc, "task-id", (), {}, None)

    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error_records, "expected an error log record"
    assert "failed permanently" in caplog.text
    # exc_info must be attached so the traceback is emitted.
    assert error_records[0].exc_info is not None
