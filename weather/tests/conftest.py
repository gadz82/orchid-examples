import pytest


def pytest_configure(config):
    config.option.asyncio_mode = "auto"


@pytest.fixture
def weather_config():
    from pathlib import Path

    from orchid_ai.config.loader import load_config

    config_path = Path(__file__).resolve().parents[1] / "agents.yaml"
    return load_config(str(config_path))


@pytest.fixture
def auth_context():
    from orchid_ai.core.state import OrchidAuthContext

    return OrchidAuthContext(
        access_token="test-token",
        tenant_key="weather-demo",
        user_id="test-user",
    )
