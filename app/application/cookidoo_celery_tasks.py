from celery import Celery
import asyncio
import aiohttp
import json
import logging
import os
import urllib.request
from cookidoo_api import Cookidoo, CookidooConfig, CookidooException
from cookidoo_api.helpers import get_localization_options
from datetime import datetime

logger = logging.getLogger(__name__)

celery_app = Celery('tasks', broker='redis://redis:6379/0', backend='redis://redis:6379/0')
celery_app.conf.broker_connection_retry_on_startup = True

# Base URL of the main app, which owns the DB. The worker has no DB access and
# reports stale/recovered cookidoo links to it over HTTP (see _report_sync_status).
# Same BASE_URL the app uses for screenshots.
__base_url = os.environ.get('BASE_URL', 'http://localhost:5000')


def _report_sync_status(cookidoo_id, stale):
    """Tell the main app to flag/unflag a recipe's cookidoo link as stale.

    Best-effort: any error here (app down, network) is logged and swallowed so
    it never turns a successful/failed sync into a task crash.
    """
    if not cookidoo_id:
        return
    url = f"{__base_url.rstrip('/')}/internal/cookidoo-sync-status"
    data = json.dumps({"cookidoo_id": cookidoo_id, "stale": stale}).encode()
    headers = {"Content-Type": "application/json"}
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.warning("Could not report cookidoo sync status for %s (stale=%s): %s",
                       cookidoo_id, stale, e)


class CookidooTask(celery_app.Task):
    """Base task that logs Cookidoo calendar retries and permanent failures."""

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            "Retrying %s[%s] (retry %s/%s) after error: %s",
            self.name, task_id, self.request.retries, self.max_retries, exc,
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "Task %s[%s] failed permanently after %s retries: %s",
            self.name, task_id, self.request.retries, exc, exc_info=exc,
        )
        # args[0] is the cookidoo recipe id; flag its recipe so the stale link
        # surfaces in the UI for the user to fix manually.
        if args:
            _report_sync_status(args[0], True)

    def on_success(self, retval, task_id, args, kwargs):
        # a successful sync clears any previous stale-link warning
        if args:
            _report_sync_status(args[0], False)

__email = os.environ.get('COOKIDOO_EMAIL')
__pass = os.environ.get('COOKIDOO_PASSWORD')
__cookie_file = ".cookies"

async def _authenticated_cookidoo(session):
    """Return a Cookidoo client with a valid session.

    Loads saved cookies and validates the session, re-logging in when the
    cookies are missing or expired. load_cookies() does not verify the session
    is still alive, so get_user_info() acts as a cheap check that catches
    expired cookies (raises CookidooAuthException).
    """
    cookidoo = Cookidoo(
        session,
        cfg=CookidooConfig(
            email=__email,
            password=__pass,
            localization=(
                await get_localization_options(country="de", language="de-DE")
            )[0],
        ),
    )
    try:
        cookidoo.load_cookies(__cookie_file)
        await cookidoo.get_user_info()
    except (CookidooException, OSError) as e:
        logger.warning("Cookie session unusable (%s: %s); logging in fresh",
                       type(e).__name__, e)
        await cookidoo.login()
        cookidoo.save_cookies(__cookie_file)
    return cookidoo

@celery_app.task(base=CookidooTask, max_retries=3, retry_backoff=True, autoretry_for=(Exception,))
def add_recipe_to_cookidoo_calendar(recipe_id, date):
    """Add a recipe to the Cookidoo calendar on the given date.

    Any error is retried up to max_retries with exponential backoff; retries and
    the final failure are logged by CookidooTask.

    Args:
        recipe_id: Cookidoo recipe id to add.
        date: Target calendar day as a 'YYYY-MM-DD' string.
    """
    async def run_cookidoo_task():
        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
            cookidoo = await _authenticated_cookidoo(session)
            await cookidoo.add_recipes_to_calendar(datetime.strptime(date, '%Y-%m-%d').date(), [recipe_id])

    asyncio.run(run_cookidoo_task())

@celery_app.task(base=CookidooTask, max_retries=3, retry_backoff=True, autoretry_for=(Exception,))
def remove_recipe_from_cookidoo_calendar(recipe_id, date):
    """Remove a recipe from the Cookidoo calendar on the given date.

    Any error is retried up to max_retries with exponential backoff; retries and
    the final failure are logged by CookidooTask.

    Args:
        recipe_id: Cookidoo recipe id to remove.
        date: Calendar day the recipe is on, as a 'YYYY-MM-DD' string.
    """
    async def run_cookidoo_task():
        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
            cookidoo = await _authenticated_cookidoo(session)
            await cookidoo.remove_recipe_from_calendar(datetime.strptime(date, '%Y-%m-%d').date(), recipe_id)

    asyncio.run(run_cookidoo_task())
