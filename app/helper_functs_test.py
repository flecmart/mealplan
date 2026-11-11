import pytest

from application import helper_functs


def test_scrape_recipe_refuses_file_url():
    with pytest.raises(ValueError):
        helper_functs.scrape_recipe("file:///nonexistent#https://example.com/", "")
