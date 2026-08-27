from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    APP_NAME: str = "Autonomous AI Software Factory"
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    SECRET_KEY: str = "dev-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    JWT_ALGORITHM: str = "HS256"

    DATABASE_URL: str = "postgresql+asyncpg://factory:factory@localhost:5432/factory"
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10

    REDIS_URL: str = "redis://localhost:6379/0"

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None

    # NOTE (fixed): these previously named models absent from
    # pricing_table.json (claude-3-5-haiku-20241022 /
    # claude-3-5-sonnet-20241022), so any deployment that relied on these
    # class defaults instead of .env.example got silent $0.003/$0.015
    # fallback pricing for every single call instead of the model's real
    # price. Aligned to the same model names .env.example and
    # pricing_table.json already agree on.
    MODEL_CHEAP: str = "claude-haiku-4-5-20251001"
    MODEL_CODING: str = "claude-sonnet-5"
    MODEL_REASONING: str = "claude-opus-4-8"
    MODEL_FALLBACK: str = "claude-haiku-4-5-20251001"
    MODEL_PROVIDER_CHEAP: Literal["openai", "anthropic", "stub", "gemini", "groq"] = "anthropic"
    MODEL_PROVIDER_CODING: Literal["openai", "anthropic", "stub", "gemini", "groq"] = "anthropic"
    MODEL_PROVIDER_REASONING: Literal["openai", "anthropic", "stub", "gemini", "groq"] = "anthropic"
    MODEL_PROVIDER_FALLBACK: Literal["openai", "anthropic", "stub", "gemini", "groq"] = "anthropic"

    CONTEXT_BUDGET_PLANNER_TOKENS: int = 8000
    CONTEXT_BUDGET_CODING_TOKENS: int = 4000
    CONTEXT_BUDGET_REVIEW_TOKENS: int = 3000
    CONTEXT_BUDGET_DEBUG_TOKENS: int = 5000
    CONTEXT_BUDGET_TEST_TOKENS: int = 3000
    CONTEXT_BUDGET_DOCS_TOKENS: int = 3000

    MAX_TASK_RETRIES: int = 3
    RETRY_BACKOFF_BASE_SECONDS: float = 2.0
    RETRY_BACKOFF_MAX_SECONDS: float = 60.0
    MAX_PARALLEL_TASKS: int = 4
    TASK_BATCH_AWAIT_TIMEOUT_SECONDS: int = 900
    AGENT_TOOL_LOOP_MAX_ITERATIONS: int = 8
    PLANNER_JSON_REPAIR_ATTEMPTS: int = 2

    DEFAULT_PROJECT_TOKEN_BUDGET: int = 500_000
    HIGH_COST_ESCALATION_USD: float = 1.00

    SANDBOX_ENABLED: bool = True
    SANDBOX_IMAGE: str = "factory-sandbox:latest"
    SANDBOX_TIMEOUT_SECONDS: int = 60
    SANDBOX_MEMORY_LIMIT: str = "512m"
    SANDBOX_CPU_LIMIT: float = 1.0
    SANDBOX_NETWORK_DISABLED: bool = True
    WORKSPACE_ROOT: str = "/tmp/factory-workspaces"

    PRICING_TABLE_PATH: str = "app/orchestrator/pricing_table.json"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
