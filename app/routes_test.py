import os
import urllib.request
import pytest
from flask import Flask
from application import create_app  # Assuming your Flask app factory is here


def _dev_server_reachable(url, timeout=2):
    """Return True if an HTTP server answers at ``url`` within ``timeout`` seconds."""
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


@pytest.fixture
def app():
    """Create and configure a test Flask application."""
    app = create_app()  # Initialize your Flask app
    app.config['TESTING'] = True
    # You might need to configure other settings for testing
    with app.app_context():
        yield app

@pytest.fixture
def client(app):
    """A test client for the Flask application."""
    return app.test_client()

@pytest.mark.skipif(os.getenv("CI") == "true",
                    reason="integration test needs Chromium + DB; skipped in CI")
def test_screenshot_week_generates_image(client, app):
    """Test that the /week route generates and saves the week.png image.

    INTEGRATION TEST — PREREQUISITE: a running Flask dev server.
    The /week handler launches headless Chromium and navigates to SCREENSHOT_URL
    (default http://localhost:5000/), so it needs the dev server (and its DB) up
    and serving the calendar page. It does NOT screenshot this test client.

    To run locally, start the stack first, e.g.:
        docker compose -f docker-compose.dev.yml up app
    then run pytest with CI unset. If the server is not reachable the test skips
    with an explanatory message (rather than a confusing assertion failure).
    """
    screenshot_url = os.environ.get("SCREENSHOT_URL", "http://localhost:5000/")
    if not _dev_server_reachable(screenshot_url):
        pytest.skip(
            f"Flask dev server not reachable at {screenshot_url}. "
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