"""Generate local-only JWT and bootstrap-admin credentials in an ignored .env file."""

from __future__ import annotations

import argparse
import secrets
from pathlib import Path


AUTH_KEYS = (
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "BOOTSTRAP_ADMIN_USERNAME",
    "BOOTSTRAP_ADMIN_PASSWORD",
)


def existing_keys(env_file: Path) -> set[str]:
    return {
        line.split("=", 1)[0].strip()
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize local RepoMind JWT credentials")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--username", default="repomind_admin")
    arguments = parser.parse_args()

    env_file = arguments.env_file.resolve()
    if not env_file.is_file():
        raise FileNotFoundError(f"Environment file does not exist: {env_file}")
    if existing_keys(env_file).intersection(AUTH_KEYS):
        raise RuntimeError("Authentication entries already exist; refusing to overwrite them")

    content = env_file.read_text(encoding="utf-8").rstrip()
    generated = "\n".join(
        (
            "# Local-only authentication bootstrap. Keep this ignored file private.",
            f"JWT_SECRET_KEY={secrets.token_urlsafe(48)}",
            "JWT_ALGORITHM=HS256",
            "ACCESS_TOKEN_EXPIRE_MINUTES=60",
            f"BOOTSTRAP_ADMIN_USERNAME={arguments.username}",
            f"BOOTSTRAP_ADMIN_PASSWORD={secrets.token_urlsafe(24)}",
        )
    )
    env_file.write_text(f"{content}\n\n{generated}\n", encoding="utf-8")
    print(f"Local authentication initialized for username: {arguments.username}")
    print("The generated password and JWT secret are stored only in the local .env file.")


if __name__ == "__main__":
    main()
