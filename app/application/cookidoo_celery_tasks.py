from celery import Celery
import asyncio
import aiohttp
import os
from cookidoo_api import Cookidoo, CookidooConfig
from cookidoo_api.helpers import get_localization_options
from datetime import datetime

celery_app = Celery('tasks', broker='redis://redis:6379/0', backend='redis://redis:6379/0')
celery_app.conf.broker_connection_retry_on_startup = True

__email = os.environ.get('COOKIDOO_EMAIL')
__pass = os.environ.get('COOKIDOO_PASSWORD')

@celery_app.task(bind=True, max_retries=3, retry_backoff=True)
def add_recipe_to_cookidoo_calendar(self, recipe_id, date):
    try:
        async def run_cookidoo_task():
            async with aiohttp.ClientSession() as session:
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
                await cookidoo.login()
                await cookidoo.refresh_token()
                await cookidoo.add_recipes_to_calendar(datetime.strptime(date, '%Y-%m-%d').date(), [recipe_id])

        asyncio.run(run_cookidoo_task())
    except aiohttp.ClientError as e:
        print(f"Network error: {e}")
        #raise self.retry(exc=e) #re-raise the exception, so celery can handle the retry.
    except Exception as e:
        print(f"Could not add recipe to cookidoo due to an unexpected error occurred: {e}")
        # Handle other exceptions as needed
        # Potentially send an alert or perform cleanup
        #raise #if you want to mark the task as failed.

@celery_app.task(bind=True, max_retries=3, retry_backoff=True)
def remove_recipe_from_cookidoo_calendar(self, recipe_id, date):
    try:
        async def run_cookidoo_task():
            async with aiohttp.ClientSession() as session:
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
                await cookidoo.login()
                await cookidoo.refresh_token()
                await cookidoo.remove_recipe_from_calendar(datetime.strptime(date, '%Y-%m-%d').date(), recipe_id)

        asyncio.run(run_cookidoo_task())
    except aiohttp.ClientError as e:
        print(f"Network error: {e}")
        #raise self.retry(exc=e) #re-raise the exception, so celery can handle the retry.
    except Exception as e:
        print(f"Could not remove recipe from cookidoo due to an unexpected error occurred: {e}")
        # Handle other exceptions as needed
        # Potentially send an alert or perform cleanup
        #raise #if you want to mark the task as failed.
