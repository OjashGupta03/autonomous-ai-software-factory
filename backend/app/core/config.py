"""
Application configuration.

All configuration is sourced from environment variables (see .env.example
at the repo root). Nothing here should contain real secrets - defaults are
safe placeholders for local development only.

Design note: every tunable that affects orchestration behaviour (retry
limits, context budgets, concurrency) lives here so the whole cost/latency
profile of the system can be changed without touching code. See
docs/07-token-optimization.md and docs/23-design-decisions.md.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General -----------------------------------------------------
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    APP_NAME: str = "Autonomous AI Software Factory"
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # --- Security ------------------------------------------------------
    SECRET_KEY: str = "dev-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    JWT_ALGORITHM: str = "HS256"

    # --- Database ------------------------------------------------------
    # Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host:5432/db
    DATABASE_URL: str = "postgresql+asyncpg://factory:factory@localhost:5432/factory"
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10

    # --- Redis -----------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- CORS --------------------------------------------------------
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # --- Model providers (see app/orchestrator/model_router.py) --------
    # A provider key is only required for the tiers you actually route to.
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None

    # Model tiers - deliberately separate from "provider" so operators can
    # mix vendors per tier (e.g. a cheap OpenAI model + an Anthropic model
    # for hard reasoning) without touching orchestration code.
    MODEL_CHEAP: str = "claude-3-5-haiku-20241022"
    MODEL_CODING: str = "claude-3-5-sonnet-20241022"
    MODEL_REASONING: str = "claude-3-5-sonnet-20241022"
    MODEL_FALLBACK: str = "claude-3-5-haiku-20241022"
    MODEL_PROVIDER_CHEAP: Literal["openai", "anthropic", "stub", "gemini", "groq"] = "anthropic"
    MODEL_PROVIDER_CODING: Literal["openai", "anthropic", "stub", "gemini", "groq"] = "anthropic"
    MODEL_PROVIDER_REASONING: Literal["openai", "anthropic", "stub", "gemini", "groq"] = "anthropic"
    MODEL_PROVIDER_FALLBACK: Literal["openai", "anthropic", "stub", "gemini", "groq"] = "anthropic"

    # --- Context engineering (docs/06-context-engineering.md) ----------
    CONTEXT_BUDGET_PLANNER_TOKENS: int = 8000
    CONTEXT_BUDGET_CODING_TOKENS: int = 4000
    CONTEXT_BUDGET_REVIEW_TOKENS: int = 3000
    CONTEXT_BUDGET_DEBUG_TOKENS: int = 5000
    CONTEXT_BUDGET_TEST_TOKENS: int = 3000
    CONTEXT_BUDGET_DOCS_TOKENS: int = 3000

    # --- Orchestration / failure recovery -------------------------------
    MAX_TASK_RETRIES: int = 3
    RETRY_BACKOFF_BASE_SECONDS: float = 2.0
    RETRY_BACKOFF_MAX_SECONDS: float = 60.0
    MAX_PARALLEL_TASKS: int = 4
    TASK_BATCH_AWAIT_TIMEOUT_SECONDS: int = 900
    AGENT_TOOL_LOOP_MAX_ITERATIONS: int = 8

    # --- Cost controls ---------------------------------------------------
    DEFAULT_PROJECT_TOKEN_BUDGET: int = 500_000
    HIGH_COST_ESCALATION_USD: float = 1.00  # single call above this needs approval

    # --- Sandbox execution (docs/11-code-execution-sandbox.md) ----------
    SANDBOX_ENABLED: bool = True
    SANDBOX_IMAGE: str = "factory-sandbox:latest"
    SANDBOX_TIMEOUT_SECONDS: int = 60
    SANDBOX_MEMORY_LIMIT: str = "512m"
    SANDBOX_CPU_LIMIT: float = 1.0
    SANDBOX_NETWORK_DISABLED: bool = False
    WORKSPACE_ROOT: str = "/tmp/factory-workspaces"

    # --- Pricing table path (see app/orchestrator/pricing.py) ----------
    PRICING_TABLE_PATH: str = "app/orchestrator/pricing_table.json"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Settings are cached for process lifetime; tests override via
    dependency_overrides rather than mutating this singleton."""
    return Settings()
