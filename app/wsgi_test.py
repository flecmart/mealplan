import pytest

def test_import_wsgi():
    try:
        import wsgi
        assert True
    except ImportError:
        assert False