from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path("config/config.yaml")


class ConfigError(RuntimeError):
    pass


@dataclass
class Config:
    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, *path: str, default: Any = None) -> Any:
        node: Any = self.raw
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def require(self, *path: str) -> Any:
        value = self.get(*path)
        if value is None:
            raise ConfigError(f"Missing required config key: {'.'.join(path)}")
        return value


def load_config(path: str | Path | None = None) -> Config:
    cfg_path = Path(path or os.environ.get("DOT11_CONFIG") or DEFAULT_CONFIG_PATH)
    if not cfg_path.exists():
        raise ConfigError(
            f"Config not found at {cfg_path}. Copy config/config.example.yaml "
            f"to config/config.yaml or set DOT11_CONFIG."
        )
    with cfg_path.open() as f:
        data = yaml.safe_load(f) or {}
    return Config(raw=data)
