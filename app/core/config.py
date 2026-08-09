import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str
    database_url: str
    log_level: str
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    bootstrap_admin_username: str
    bootstrap_admin_password: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    chroma_path: Path


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "RepoMind API"),
        database_url=os.getenv("DATABASE_URL", "").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        jwt_secret_key=os.getenv("JWT_SECRET_KEY", "").strip(),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256").strip(),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
        bootstrap_admin_username=os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip(),
        bootstrap_admin_password=os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip(),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip(),
        chroma_path=Path(os.getenv("CHROMA_PATH", str(PROJECT_ROOT / "storage" / "chroma"))),
    )
