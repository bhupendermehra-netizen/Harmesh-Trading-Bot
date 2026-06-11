def test_app_factory():
    from app import create_app
    app = create_app()
    assert app is not None
    assert app.name == "app"
    assert app.secret_key is not None


def test_dashboard_route():
    from app import create_app
    app = create_app()
    with app.test_client() as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Harmesh" in resp.data


def test_api_status():
    from app import create_app
    app = create_app()
    with app.test_client() as client:
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "paper" in data
        assert "backtest" in data
        assert "timestamp" in data


def test_config_loader():
    from config.loader import load_config
    cfg = load_config()
    assert cfg is not None
    assert "system" in cfg
    assert "trading" in cfg


def test_config_validator():
    from config.validator import validate_config
    assert validate_config() is True
