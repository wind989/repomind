"""Create a local Docker Compose environment file without printing secrets.

The generated .env.docker is intentionally ignored by Git.  It uses a fresh,
isolated MySQL account and bootstrap administrator for the Docker deployment.
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ENV = PROJECT_ROOT / ".env"
TARGET_ENV = PROJECT_ROOT / ".env.docker"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def random_secret() -> str:
    # token_urlsafe only uses characters that are safe in a dotenv value and URL.
    return secrets.token_urlsafe(32)


def main() -> int:
    if TARGET_ENV.exists():
        print(".env.docker already exists; no file was changed.")
        return 1
    if not SOURCE_ENV.exists():
        print("Missing .env; create the local application configuration first.")
        return 1

    source = read_env(SOURCE_ENV)
    api_key = source.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("DEEPSEEK_API_KEY is missing from .env; no file was created.")
        return 1

    mysql_password = random_secret()
    values = {
        "MYSQL_DATABASE": "repomind",
        "MYSQL_USER": "repomind_user",
        "MYSQL_PASSWORD": mysql_password,
        "MYSQL_ROOT_PASSWORD": random_secret(),
        "DATABASE_URL": (
            "mysql+pymysql://repomind_user:"
            f"{mysql_password}@mysql:3306/repomind?charset=utf8mb4"
        ),
        "DEEPSEEK_API_KEY": api_key,
        "DEEPSEEK_BASE_URL": source.get(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        ),
        "DEEPSEEK_MODEL": source.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "LOG_LEVEL": source.get("LOG_LEVEL", "INFO"),
        "JWT_SECRET_KEY": random_secret(),
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": source.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"),
        "BOOTSTRAP_ADMIN_USERNAME": source.get(
            "BOOTSTRAP_ADMIN_USERNAME", "repomind_admin"
        ),
        "BOOTSTRAP_ADMIN_PASSWORD": random_secret(),
    }
    content = "# Generated locally by scripts/create_docker_env.py. Never commit this file.\n"
    content += "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
    TARGET_ENV.write_text(content, encoding="utf-8", newline="\n")
    print("Created .env.docker with isolated Docker credentials; no secrets were printed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
