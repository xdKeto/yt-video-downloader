from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import AppError


@dataclass(frozen=True)
class AppConfig:
    output_dir: Path = Path("downloads")
    temp_dir: Path = Path(".stream-downloader-temp")
    profile: str = "maximum"
    retries: int = 5
    fragment_retries: int = 10
    wait_interval: float = 60
    wait_timeout: float = 1800
    ffmpeg_location: str | None = None
    js_runtime: str = "deno"
    cookies_from_browser: tuple[str, str | None] | None = None
    config_path: Path | None = None


def load_config(path: str | Path | None, overrides: dict[str, Any] | None = None) -> AppConfig:
    values: dict[str, Any] = {}
    if path:
        config_path = Path(path).expanduser()
        try:
            with config_path.open("rb") as stream:
                parsed = tomllib.load(stream)
        except FileNotFoundError as exc:
            raise AppError(f"Configuration file not found: {config_path}", 2) from exc
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise AppError(f"Cannot read configuration file {config_path}: {exc}", 2) from exc
        section = parsed.get("stream_downloader", parsed)
        if not isinstance(section, dict):
            raise AppError("Configuration must be a TOML table.", 2)
        allowed = {"output_dir", "temp_dir", "profile", "retries", "fragment_retries", "wait_interval", "wait_timeout", "ffmpeg_location", "js_runtime"}
        values.update({key: value for key, value in section.items() if key in allowed})
        values["config_path"] = config_path
    if overrides:
        values.update({key: value for key, value in overrides.items() if value is not None})
    try:
        for key in ("output_dir", "temp_dir", "config_path"):
            if values.get(key) is not None:
                values[key] = Path(values[key]).expanduser()
        cfg = AppConfig(**values)
    except (TypeError, ValueError) as exc:
        raise AppError(f"Invalid configuration value: {exc}", 2) from exc
    if cfg.profile not in {"maximum", "mp4"}:
        raise AppError("Profile must be 'maximum' or 'mp4'.", 2)
    if cfg.retries < 0 or cfg.fragment_retries < 0:
        raise AppError("Retry counts cannot be negative.", 2)
    if cfg.wait_interval <= 0 or cfg.wait_timeout <= 0:
        raise AppError("Wait interval and timeout must be greater than zero.", 2)
    return cfg

