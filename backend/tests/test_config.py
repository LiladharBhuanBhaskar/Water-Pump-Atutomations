from app.core.config import settings


def test_test_database_url_is_available_and_isolated():
    assert hasattr(settings, "TEST_DATABASE_URL")
    assert "test" in settings.TEST_DATABASE_URL.lower()
