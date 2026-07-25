from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from dotenv import find_dotenv, load_dotenv


ModelMode = Literal["auto", "local", "openai"]
DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
DEFAULT_LONGCAT_MODEL = "LongCat-2.0"
DEFAULT_LONGCAT_BASE_URL = "https://api.longcat.chat/openai/v1"


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_value(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def _normalize_base_url(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.rstrip("/")
    if normalized.endswith("/chat/completions"):
        normalized = normalized[: -len("/chat/completions")]
    parsed = urlsplit(normalized)
    if parsed.hostname == "api.longcat.chat" and parsed.path.rstrip("/") in {"", "/openai"}:
        return urlunsplit((parsed.scheme, parsed.netloc, "/openai/v1", "", ""))
    return normalized


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "景区讲解词多平台营销内容助手"
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = Path("data")
    model_mode: ModelMode = "auto"
    model_name: str = "gpt-5-mini"
    openai_api_key: str | None = field(default=None, repr=False)
    openai_base_url: str | None = None
    model_timeout_seconds: float = 14.0
    model_max_retries: int = 0
    max_input_chars: int = 12_000
    prompt_version: str = "2026-07-25.v1"
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    debug: bool = False

    @property
    def database_path(self) -> Path:
        return self.data_dir / "wenan.sqlite3"

    @property
    def checkpoint_path(self) -> Path:
        return self.data_dir / "checkpoints.sqlite3"

    @property
    def resolved_model_mode(self) -> Literal["local", "openai"]:
        if self.model_mode == "auto":
            return "openai" if self.openai_api_key else "local"
        return self.model_mode

    @property
    def is_longcat(self) -> bool:
        return urlsplit(self.openai_base_url or "").hostname == "api.longcat.chat"

    @classmethod
    def from_env(cls) -> "Settings":
        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path, override=False)

        origins = os.getenv("APP_CORS_ORIGINS")
        longcat_api_key = _env_value("LONGCAT_API_KEY")
        longcat_url = _env_value("LONGCAT_URL")
        longcat_model = _env_value("LONGCAT_MODEL")
        openai_api_key = _env_value("OPENAI_API_KEY")
        openai_base_url = _env_value("OPENAI_BASE_URL")
        openai_model = _env_value("OPENAI_MODEL")
        uses_longcat = bool(longcat_api_key or longcat_url or longcat_model)
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            host=os.getenv("APP_HOST", "127.0.0.1"),
            port=int(os.getenv("APP_PORT", "8000")),
            data_dir=Path(os.getenv("APP_DATA_DIR", "data")),
            model_mode=os.getenv("APP_MODEL_MODE", "auto").lower(),  # type: ignore[arg-type]
            model_name=openai_model
            or longcat_model
            or (DEFAULT_LONGCAT_MODEL if uses_longcat else DEFAULT_OPENAI_MODEL),
            openai_api_key=openai_api_key or longcat_api_key,
            openai_base_url=_normalize_base_url(
                openai_base_url
                or longcat_url
                or (DEFAULT_LONGCAT_BASE_URL if longcat_api_key else None)
            ),
            model_timeout_seconds=float(os.getenv("MODEL_TIMEOUT_SECONDS", "14")),
            model_max_retries=int(os.getenv("MODEL_MAX_RETRIES", "0")),
            max_input_chars=int(os.getenv("APP_MAX_INPUT_CHARS", "12000")),
            cors_origins=tuple(item.strip() for item in origins.split(",") if item.strip())
            if origins
            else DEFAULT_CORS_ORIGINS,
            debug=_as_bool(os.getenv("APP_DEBUG")),
        )

    def validate(self) -> None:
        if self.model_mode not in {"auto", "local", "openai"}:
            raise ValueError("APP_MODEL_MODE 必须是 auto、local 或 openai")
        if self.model_mode == "openai" and not self.openai_api_key:
            raise ValueError("APP_MODEL_MODE=openai 时必须设置 OPENAI_API_KEY")
        if self.max_input_chars < 100:
            raise ValueError("APP_MAX_INPUT_CHARS 不能小于 100")
