"""Secret storage for the AI provider API key.

The key is kept OUT of the SQLite database and OUT of any API response.
It is stored in a local JSON file under `data/secrets.json` (gitignored)
with restrictive permissions where the platform supports it.

Rules enforced here:
  * GET endpoints must call `mask_key()` - the raw key is never returned.
  * The key is only ever used server-side to call the configured provider.
  * The key is never placed in AI conversation messages or logs.
"""
import json
import os
import stat
from pathlib import Path
from typing import Optional

from .config import settings


def _load_store() -> dict:
    path: Path = settings.secrets_path
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def _save_store(store: dict) -> None:
    path: Path = settings.secrets_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")
    try:
        # Restrict to the current user where the platform supports it (POSIX).
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass  # Windows: rely on the user profile's directory ACLs.


def get_stored_key() -> Optional[str]:
    """Return the API key stored via the Settings page, or None."""
    store = _load_store()
    key = store.get("api_key", "")
    return key or None


def set_stored_key(key: str) -> None:
    _save_store({**_load_store(), "api_key": key})


def clear_stored_key() -> None:
    _save_store({k: v for k, v in _load_store().items() if k != "api_key"})


def mask_key(key: Optional[str]) -> Optional[str]:
    """Return a display-safe form like 'nvapi-****abcd', never the key."""
    if not key:
        return None
    if len(key) <= 8:
        return "****"
    return f"{key[:6]}...{key[-4:]}"
