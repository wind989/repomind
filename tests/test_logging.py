from app.core.logging import redact_secrets


def test_redact_secrets_masks_common_credentials() -> None:
    value = "api_key=secret-token mysql+pymysql://user:password@db/repomind Bearer access-token"
    redacted = redact_secrets(value)

    assert "secret-token" not in redacted
    assert "password@" not in redacted
    assert "access-token" not in redacted
