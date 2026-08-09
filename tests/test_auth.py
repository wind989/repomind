import pytest

from app.core.config import get_settings
from app.main import app
from app.models.user import User
from app.services.auth import get_current_user, hash_password


@pytest.fixture()
def configured_auth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-that-is-not-for-production")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_jwt_login_me_and_protected_route(client, test_db, configured_auth) -> None:
    user = User(
        username="local-admin",
        password_hash=hash_password("correct-horse-battery-staple"),
        is_active=True,
        is_admin=True,
    )
    test_db.add(user)
    test_db.commit()

    app.dependency_overrides.pop(get_current_user)
    try:
        unauthorized = client.get("/knowledge-bases")
        assert unauthorized.status_code == 401

        bad_login = client.post(
            "/auth/token",
            data={"username": "local-admin", "password": "incorrect"},
        )
        assert bad_login.status_code == 401

        login = client.post(
            "/auth/token",
            data={"username": "local-admin", "password": "correct-horse-battery-staple"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        profile = client.get("/auth/me", headers=headers)
        assert profile.status_code == 200
        assert profile.json()["username"] == "local-admin"

        protected = client.get("/knowledge-bases", headers=headers)
        assert protected.status_code == 200
    finally:
        app.dependency_overrides[get_current_user] = lambda: User(
            id=1,
            username="test-admin",
            password_hash="unused",
            is_active=True,
            is_admin=True,
        )
