"""Configuration lue depuis l'environnement (fichier .env via Docker Compose)."""
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # Base de données : l'application utilise le rôle restreint ilk_app, les migrations le rôle propriétaire.
    database_url: str = "postgresql+psycopg://ilk_app:change-me@localhost:5432/ilk"
    migration_database_url: str = ""

    # Secrets
    session_secret: str = Field(default="", description="Clé HMAC des jetons de session (>= 32 caractères)")
    mfa_encryption_key: str = Field(default="", description="Clé de chiffrement des secrets TOTP (>= 32 caractères)")

    # Sessions
    session_idle_minutes: int = 30
    session_absolute_hours: int = 10
    cookie_secure: bool = False  # True dès que l'accès passe par HTTPS (Tailscale/TLS)
    mfa_required_for_all: bool = False

    # Anti force brute
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    rate_limit_per_minute: int = 300
    login_rate_limit_per_minute: int = 10

    # Documents
    documents_dir: str = "/data/documents"
    max_upload_mb: int = 200

    # IA locale (Ollama)
    ollama_url: str = ""
    ollama_model: str = "qwen2.5:7b-instruct"
    ollama_timeout_s: int = 120

    # IA cloud (désactivée par défaut)
    cloud_ai_provider: str = ""  # "anthropic" ou vide
    cloud_ai_api_key: str = ""
    cloud_ai_model: str = "claude-opus-5-5"
    cloud_ai_max_tokens: int = 4000
    ai_policy_version: str = "2026-10"

    @field_validator("session_secret", "mfa_encryption_key")
    @classmethod
    def _long_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("doit contenir au moins 32 caractères aléatoires")
        return v

    @property
    def cloud_configured(self) -> bool:
        return self.cloud_ai_provider == "anthropic" and bool(self.cloud_ai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
