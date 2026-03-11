from src.api.main import app


def test_health_route_registered() -> None:
    paths = {route.path for route in app.routes}
    assert "/health" in paths
