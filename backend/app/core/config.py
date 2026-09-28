import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

MIN_SECRET_KEY_LENGTH = 32
_KNOWN_INSECURE_KEYS = {
    "super-secret-key-change-this-in-production-uzbekistan-audit",
    "replace-with-a-secure-random-string",
}

class Settings(BaseSettings):
    PROJECT_NAME: str = "Yordamchi Buxgalter AI"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SQL_ECHO: bool = False  # logs every SQL statement incl. data; local debugging only
    API_V1_STR: str = "/api/v1"
    
    # PostgreSQL Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "12345"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "yordamchi_buxgalter"
    
    DATABASE_URL: str = "postgresql+asyncpg://postgres:12345@localhost:5433/yordamchi_buxgalter"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://postgres:12345@localhost:5433/yordamchi_buxgalter"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # AI Providers
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    
    # Security
    # Must be set via environment (>= 32 random chars); there is deliberately no default
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # First administrator, created on startup only when the users table is empty
    BOOTSTRAP_ADMIN_USERNAME: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # File storage (real accounting data: keep outside version control)
    UPLOAD_DIR: str = os.path.join(_BACKEND_DIR, "app", "uploads")
    BACKUP_DIR: str = os.path.join(_BACKEND_DIR, "backups")

    # Dangerous operations: factory reset / organization data wipe
    ALLOW_SYSTEM_RESET: bool = False

    # Didox / Soliq adapters only generate simulated documents; never enable on real books
    INTEGRATIONS_DEMO_MODE: bool = False

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    def assert_secure(self) -> None:
        """Fails fast when security-critical settings are missing or weak."""
        if len(self.SECRET_KEY) < MIN_SECRET_KEY_LENGTH or self.SECRET_KEY in _KNOWN_INSECURE_KEYS:
            raise RuntimeError(
                f"SECRET_KEY o'rnatilmagan yoki juda qisqa (kamida {MIN_SECRET_KEY_LENGTH} belgi). "
                "Masalan: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        if self.ALGORITHM not in ("HS256", "HS384", "HS512"):
            raise RuntimeError(f"Qo'llab-quvvatlanmaydigan JWT algoritmi: {self.ALGORITHM}")

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
