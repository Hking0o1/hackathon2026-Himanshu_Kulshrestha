from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_file() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    env_path = root_dir / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw is not None else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw is not None else default


@dataclass(slots=True)
class Settings:
    root_dir: Path
    backend_dir: Path
    data_dir: Path
    audit_log_path: Path
    failure_modes_path: Path
    schema_path: Path
    admin_token: str
    worker_count: int
    confidence_threshold: float
    escalation_amount_threshold: float
    max_retries: int
    max_react_iterations: int
    chaos_enabled: bool
    chaos_timeout_rate: float
    chaos_malformed_rate: float
    chaos_server_error_rate: float
    chaos_success_rate: float
    chaos_seed: int
    database_url: str
    groq_api_key: str
    groq_model: str
    gemini_api_key: str
    gemini_model: str
    huggingface_api_key: str
    huggingface_model: str
    ollama_base_url: str
    ollama_model: str
    llm_request_timeout: float

    @classmethod
    def from_env(cls) -> "Settings":
        root_dir = Path(__file__).resolve().parents[1]
        backend_dir = root_dir / "backend"
        return cls(
            root_dir=root_dir,
            backend_dir=backend_dir,
            data_dir=backend_dir / "data",
            audit_log_path=root_dir / "audit_log.json",
            failure_modes_path=root_dir / "failure_modes.md",
            schema_path=backend_dir / "db" / "schema.sql",
            admin_token=os.getenv("ADMIN_TOKEN", "change_me_in_production"),
            worker_count=_env_int("WORKER_COUNT", 5),
            confidence_threshold=_env_float("CONFIDENCE_THRESHOLD", 0.6),
            escalation_amount_threshold=_env_float("ESCALATION_AMOUNT_THRESHOLD", 200.0),
            max_retries=_env_int("MAX_RETRIES", 3),
            max_react_iterations=_env_int("MAX_REACT_ITERATIONS", 8),
            chaos_enabled=_env_bool("CHAOS_ENABLED", False),
            chaos_timeout_rate=_env_float("CHAOS_TIMEOUT_RATE", 0.15),
            chaos_malformed_rate=_env_float("CHAOS_MALFORMED_RATE", 0.10),
            chaos_server_error_rate=_env_float("CHAOS_SERVER_ERROR_RATE", 0.15),
            chaos_success_rate=_env_float("CHAOS_SUCCESS_RATE", 0.60),
            chaos_seed=_env_int("CHAOS_SEED", 2026),
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://shopwave:password@localhost:5432/shopwave",
            ),
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            huggingface_api_key=os.getenv("HUGGINGFACE_API_KEY", ""),
            huggingface_model=os.getenv("HUGGINGFACE_MODEL", "facebook/bart-large-mnli"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            llm_request_timeout=_env_float("LLM_REQUEST_TIMEOUT", 20.0),
        )
_load_dotenv_file()
settings = Settings.from_env()
