import os
import pytest
from flask import Flask
from application import create_app  # Assuming your Flask app factory is here
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

def test_screenshot_week_generates_image(client, app):
    """Test that the /week route generates and saves the week.png image."""
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