"""Application configuration.

All secrets are read from environment variables (or the local secrets store)
and never hardcoded. The `.env` file is loaded from the project root.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is in requirements
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[2]

if load_dotenv is not None:
    load_dotenv(ROOT / ".env")


class Settings:
    def __init__(self) -> None:
        self.root = ROOT
        self.data_dir = Path(os.getenv("CODETUTOR_DATA_DIR", str(ROOT / "data")))
        self.db_path = self.data_dir / "codetutor.db"
        self.secrets_path = self.data_dir / "secrets.json"
        self.exec_tmp_dir = self.data_dir / "exec_tmp"

        self.host = os.getenv("CODETUTOR_HOST", "127.0.0.1")
        self.port = int(os.getenv("CODETUTOR_PORT", "8123"))

        self.max_body_bytes = 1_500_000          # ~1.5 MB request bodies
        self.max_code_chars = 60_000              # student code size limit
        self.max_message_chars = 12_000          # chat message size limit

        self.exec_timeout_default = 10            # seconds
        self.exec_timeout_max = 20
        self.exec_memory_mb = 256                 # sandbox memory cap
        self.max_output_bytes = 65_536            # stdout/stderr cap per run
        self.exec_max_concurrency = 3

        # Fallback AI provider taken from the environment. The Settings page
        # (stored in the DB + local secrets file) takes precedence.
        self.env_provider = {
            "name": os.getenv("CODETUTOR_PROVIDER_NAME", "").strip(),
            "base_url": os.getenv("CODETUTOR_API_BASE_URL", "").strip(),
            "model": os.getenv("CODETUTOR_MODEL", "").strip(),
            "key": os.getenv("CODETUTOR_API_KEY", "").strip(),
        }

        # Sliding-window rate limits: (name -> (max_requests, window_seconds))
        self.rate_limits = {
            "ai": (20, 60),        # chat / explain / debug
            "ai_test": (10, 60),   # provider connection tests
            "execution": (40, 60), # sandboxed code runs
        }

        self.app_name = "CodeTutor AI"


settings = Settings()
