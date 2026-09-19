"""Project-wide configuration: one loader for configs/config.yaml + .env.

Secrets come from .env (gitignored); non-secret tunables from configs/config.yaml.
All module code should pull tunables through this loader — never hardcode paths,
seeds, or analysis windows in modules (AGENTS.md §6).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def load_config() -> dict:
    """Read configs/config.yaml, anchored at the project root."""
    cfg_path = PROJECT_ROOT / "configs" / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg


def project_path(*parts: str) -> Path:
    """Resolve a path in config against the project root."""
    return PROJECT_ROOT.joinpath(*parts)


@lru_cache(maxsize=1)
def load_env() -> dict:
    """Read .env (if present) into a dict. Never raises / never logs secrets."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return {}
    result: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result