from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Runtime configuration for the "brain".

    Notes:
    - Default provider is a stub so the system runs without credentials.
    - For OpenAI-compatible gateways, set OPENAI_BASE_URL + OPENAI_API_KEY.
    - For local transformers, install optional deps and set provider=transformers.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    brain_llm_provider: str = "stub"  # stub | openai | transformers
    brain_model: str = "gpt-4o-mini"

    # OpenAI-compatible
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    # API behavior
    cors_allow_origins: str = "*"  # comma-separated or '*'
    max_index_chars: int = 200_000


settings = Settings()

