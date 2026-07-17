from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str = ""
    gemini_api_key: str = ""

    neo4j_uri: str = ""
    neo4j_username: str = ""
    neo4j_password: str = ""

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # LLM call tuning. Defaults match the live Council's existing behavior
    # (up to 4 concurrent evidence-agent calls per convening, fail over to
    # Gemini quickly on a real rate limit); batch scripts that run many
    # Council convenings back to back (e.g. run_memory_loop_experiment.py)
    # can override these via .env to stay under a free-tier TPM budget.
    llm_max_concurrent_requests: int = 8
    groq_max_consecutive_429s: int = 2
    groq_retry_backoff_cap_seconds: float = 10.0

    # Emergency Response Orchestrator (Step 9). SMTP is the channel the
    # user chose; Slack/Discord are left as empty, unused placeholders.
    ero_smtp_host: str = ""
    ero_smtp_port: int = 587
    ero_smtp_username: str = ""
    ero_smtp_password: str = ""
    ero_alert_from_email: str = ""
    ero_alert_to_email: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
