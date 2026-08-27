"""Application configuration.

All configuration is loaded from environment variables (optionally from a
`.env` file placed in the backend directory). No secrets are hardcoded here.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Settings:
    def __init__(self) -> None:
        # LLM (OpenAI-compatible) configuration. The API key is read from the
        # environment only and is never persisted to the database.
        self.llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.llm_api_key: str = os.getenv("LLM_API_KEY", "")
        self.llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

        # Storage: SQLite database + local PDF directory.
        self.data_dir: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
        self.papers_dir: Path = Path(os.getenv("PAPERS_DIR", str(self.data_dir / "papers")))
        self.uploads_dir: Path = Path(os.getenv("UPLOADS_DIR", str(self.data_dir / "uploads")))
        self.db_path: Path = Path(os.getenv("DB_PATH", str(self.data_dir / "openlab.db")))

        # arXiv API rate limiting / retry.
        self.arxiv_request_interval: float = _get_float("ARXIV_REQUEST_INTERVAL", 3.0)
        self.arxiv_max_retries: int = _get_int("ARXIV_MAX_RETRIES", 3)

        # PDF download retry.
        self.download_max_retries: int = _get_int("DOWNLOAD_MAX_RETRIES", 3)
        self.download_retry_delay: float = _get_float("DOWNLOAD_RETRY_DELAY", 2.0)

        # Search history: max number of papers kept per snapshot.
        self.search_history_snapshot_limit: int = _get_int(
            "SEARCH_HISTORY_SNAPSHOT_LIMIT", 50
        )

        # Semantic Scholar: optional API key raises the official Graph API quota.
        self.semantic_scholar_api_key: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

        # Outbound proxy for external HTTP (search/download) is user-configurable
        # in the settings UI and persisted inside the LLM config file; see
        # ``llm_config.get_http_proxy``. Kept here only as documentation of the
        # fallback env var name.
        self.http_proxy_env_name: str = "HTTP_PROXY_OVERRIDE"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
