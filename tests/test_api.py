from pathlib import Path

from fastapi.testclient import TestClient

from wenan_backend.app import create_app
from wenan_backend.config import Settings


SAMPLE_TEXT = (
    "拙政园位于苏州市，始建于明代，占地78亩。"
    "门票80元，开放时间07:30-17:30。园内讲解以原始资料为准。"
)


def _settings(data_dir: Path) -> Settings:
    return Settings(data_dir=data_dir, model_mode="local")


def test_generate_query_and_regenerate_are_persisted(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path / "data")
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sessions/generate",
            json={"original_text": SAMPLE_TEXT},
        )
        assert response.status_code == 201, response.text
        created = response.json()
        session_id = created["session_id"]
        assert created["status"] == "success"
        assert set(created["outputs"]) == {"xiaohongshu", "video", "moments"}
        assert created["validation"]["status"] == "passed"
        assert created["validation"]["direct_usable"] is True

        captured: dict[str, object] = {}
        original_generate = app.state.content_service.agents.generate

        def capture_generate(
            platform,
            original_text,
            facts,
            user_instruction=None,
            previous_content=None,
        ):
            captured["instruction"] = user_instruction
            captured["previous_content"] = previous_content
            return original_generate(
                platform,
                original_text,
                facts,
                user_instruction,
                previous_content,
            )

        monkeypatch.setattr(app.state.content_service.agents, "generate", capture_generate)
        regenerated = client.post(
            f"/api/v1/sessions/{session_id}/outputs/xiaohongshu/regenerate",
            json={"user_instruction": "语气更克制"},
        )
        assert regenerated.status_code == 200, regenerated.text
        regenerated_body = regenerated.json()
        assert regenerated_body["outputs"]["xiaohongshu"]["version"] == 2
        assert regenerated_body["outputs"]["video"]["version"] == 1
        assert regenerated_body["outputs"]["moments"]["version"] == 1
        assert captured["instruction"] == "语气更克制"
        assert captured["previous_content"] == created["outputs"]["xiaohongshu"]["content"]

    restarted_app = create_app(settings)
    with TestClient(restarted_app) as client:
        restored = client.get(f"/api/v1/sessions/{session_id}")
        assert restored.status_code == 200
        assert restored.json()["outputs"]["xiaohongshu"]["version"] == 2
        assert client.get("/api/v1/sessions").json()[0]["session_id"] == session_id


def test_blank_and_sensitive_inputs_are_rejected(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path / "data"))
    with TestClient(app) as client:
        blank = client.post("/api/v1/sessions/generate", json={"original_text": "   "})
        assert blank.status_code == 422

        pii = client.post(
            "/api/v1/sessions/generate",
            json={"original_text": "讲解员电话是13800138000，请联系后参观。"},
        )
        assert pii.status_code == 422
        assert pii.json()["error"]["code"] == "sensitive_information_detected"


def test_missing_session_returns_404(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path / "data"))
    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


def test_frontend_demo_is_served(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path / "data"))
    with TestClient(app) as client:
        response = client.get("/demo/")
        script = client.get("/demo/app.js")
        stylesheet = client.get("/demo/styles.css")

    assert response.status_code == 200
    assert "景区营销内容生成" in response.text
    assert "结构数据" not in response.text
    assert 'data-view="raw"' not in response.text
    assert script.status_code == 200
    assert 'request("/api/v1/sessions/generate"' in script.text
    assert "createXiaohongshuPreview" in script.text
    assert "createVideoPreview" in script.text
    assert "createMomentsPreview" in script.text
    assert "发送并重新生成" in script.text
    assert "outputs/${platform}/regenerate" in script.text
    assert stylesheet.status_code == 200
