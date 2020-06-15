import asyncio
import multiprocessing
import pytest

from tests.http_mock import http_mock_server


@pytest.fixture
def http_server():
    app = http_mock_server()

    server = multiprocessing.Process(
        daemon=True,
        target=app.run,
        kwargs=dict(
            host="127.0.0.1",
            port=8080,
        )
    )
    server.start()
    yield
    server.terminate()


@pytest.fixture(scope="session")
def event_loop(request):
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
