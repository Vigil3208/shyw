from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from wenan_backend.config import Settings


def test_settings_loads_dotenv_without_overriding_process_environment(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "APP_MODEL_MODE=openai",
                "OPENAI_API_KEY=from-dotenv",
                "OPENAI_BASE_URL=https://example.invalid/v1",
                "OPENAI_MODEL=dotenv-model",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with patch.dict(os.environ, {"OPENAI_MODEL": "process-model"}, clear=True):
        settings = Settings.from_env()

    assert settings.model_mode == "openai"
    assert settings.openai_api_key == "from-dotenv"
    assert settings.openai_base_url == "https://example.invalid/v1"
    assert settings.model_name == "process-model"


def test_settings_maps_longcat_variables_to_openai_compatible_client(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "LONGCAT_API_KEY=longcat-key",
                "LONGCAT_URL=https://api.longcat.chat/openai/v1/chat/completions",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with patch.dict(os.environ, {}, clear=True):
        settings = Settings.from_env()

    assert settings.resolved_model_mode == "openai"
    assert settings.openai_api_key == "longcat-key"
    assert settings.openai_base_url == "https://api.longcat.chat/openai/v1"
    assert settings.model_name == "LongCat-2.0"
    assert settings.is_longcat is True


def test_settings_normalizes_longcat_endpoint_without_v1(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "LONGCAT_API_KEY=longcat-key",
                "LONGCAT_URL=https://api.longcat.chat/openai/chat/completions",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with patch.dict(os.environ, {}, clear=True):
        settings = Settings.from_env()

    assert settings.openai_base_url == "https://api.longcat.chat/openai/v1"
