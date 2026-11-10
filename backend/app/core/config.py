"""Application settings loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core
    app_name: str = "Designflow"
    app_env: str = "development"
    app_url: str = "http://localhost:8000"
    secret_key: str = "dev-secret-key-change-me-please-32-chars-min"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    # Database (MongoDB). mongomock:// = in-memory, used by tests
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "designflow"

    # Redis
    redis_url: str = ""

    # Admin seed
    admin_email: str = "admin@designflow.local"
    admin_password: str = "Admin123!"
    admin_name: str = "Founder"
    seed_demo_data: bool = True

    # AI: provider = ollama (local, free) | anthropic | mock
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5-5"
    llm_max_tokens: int = 2048

    # Pricing: per-request prices are stored in USD; other currencies use these rates
    fx_gbp: float = 0.79
    fx_inr: float = 84.0
    default_currency: str = "USD"
    reporting_currency: str = "GBP"  # everything you receive is reported/settled in this currency (match your Stripe payout currency)
    image_provider: str = "mock"
    # AI image generation (logos and hero imagery, like ChatGPT images). auto = OpenAI if a key is set, else Gemini, else none
    # (none = the built-in vector design engine draws everything itself).
    ai_image_provider: str = "auto"
    openai_api_key: str = ""
    openai_image_model: str = "gpt-image-1"
    openai_image_quality: str = "medium"  # low | medium | high
    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-2.5-flash-image"
    lead_provider: str = "mock"
    serpapi_key: str = ""

    # Storage
    storage_backend: str = "local"
    local_storage_path: str = "./uploads"
    max_upload_mb: int = 50
    gdrive_service_account_file: str = "./secrets/gdrive-service-account.json"
    gdrive_root_folder_id: str = ""

    # Billing
    billing_provider: str = "mock"
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter: str = ""
    stripe_price_pro: str = ""
    stripe_price_premium: str = ""
    currency: str = "USD"

    # Email
    email_provider: str = "mock"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "hello@designflow.local"
    outreach_auto_send: bool = False

    # Agents
    agents_enabled: bool = True
    agent_auto_run_on_accept: bool = True
    lead_agent_cron: str = "0 9 * * *"
    outreach_followup_cron: str = "0 8 * * *"
    marketing_agent_cron: str = "0 10 * * 1,3,5"

    # Rate limiting
    rate_limit_default: str = "120/minute"
    rate_limit_auth: str = "10/minute"

    @field_validator("secret_key")
    @classmethod
    def _secret_len(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("SECRET_KEY must be at least 16 characters")
        return v

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def upload_dir(self) -> Path:
        p = Path(self.local_storage_path)
        if not p.is_absolute():
            p = PROJECT_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    def llm_model_for(self, agent_key: str) -> str:
        """Per-agent model override via LLM_MODEL_<AGENT> env var."""
        import os

        base = self.ollama_model if self.llm_provider.lower() == "ollama" else self.llm_model
        return os.getenv(f"LLM_MODEL_{agent_key.upper()}", "") or base

    @property
    def is_primary_admin_locked(self) -> bool:
        return True

    def to_reporting(self, amount: float, currency: str) -> float:
        """Convert an amount in any supported currency to the reporting currency (REPORTING_CURRENCY, GBP by default)."""
        rates = {"USD": 1.0, "GBP": self.fx_gbp, "INR": self.fx_inr}
        usd = float(amount or 0) / rates.get((currency or "USD").upper(), 1.0)
        return round(usd * rates.get(self.reporting_currency.upper(), 1.0), 2)

    def convert_price(self, usd: float, currency: str) -> float:
        cur = (currency or "USD").upper()
        if cur == "GBP":
            return round(float(usd) * self.fx_gbp)
        if cur == "INR":
            return round(float(usd) * self.fx_inr / 10) * 10
        return round(float(usd))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
