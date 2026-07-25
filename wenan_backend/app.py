from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import Depends, FastAPI, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import Settings
from .schemas import (
    GenerateRequest,
    HealthResponse,
    Platform,
    RegenerateRequest,
    SessionListItem,
    SessionView,
)
from .service import ContentService, ServiceError


FRONTEND_DIR = FilePath(__file__).resolve().parent.parent / "frontend"


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        service = ContentService(app_settings)
        app.state.content_service = service
        yield
        service.close()

    app = FastAPI(
        title=app_settings.app_name,
        version=__version__,
        description="事实锁定的景区讲解词多平台营销内容生成 API",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_service(request: Request) -> ContentService:
        return request.app.state.content_service

    @app.exception_handler(ServiceError)
    async def service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health(service: ContentService = Depends(get_service)) -> HealthResponse:
        return HealthResponse(
            status="ok",
            model_mode=service.agents.mode,
            database="ok",
        )

    @app.post(
        "/api/v1/sessions/generate",
        response_model=SessionView,
        status_code=201,
        tags=["generation"],
    )
    def generate(
        payload: GenerateRequest,
        service: ContentService = Depends(get_service),
    ) -> SessionView:
        return service.generate(payload)

    @app.get(
        "/api/v1/sessions",
        response_model=list[SessionListItem],
        tags=["sessions"],
    )
    def list_sessions(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
        service: ContentService = Depends(get_service),
    ) -> list[SessionListItem]:
        return service.list_sessions(limit, offset)

    @app.get(
        "/api/v1/sessions/{session_id}",
        response_model=SessionView,
        tags=["sessions"],
    )
    def get_session(
        session_id: Annotated[str, Path(min_length=36, max_length=36)],
        service: ContentService = Depends(get_service),
    ) -> SessionView:
        return service.get_session(session_id)

    @app.post(
        "/api/v1/sessions/{session_id}/outputs/{platform}/regenerate",
        response_model=SessionView,
        tags=["generation"],
    )
    def regenerate(
        session_id: Annotated[str, Path(min_length=36, max_length=36)],
        platform: Platform,
        payload: RegenerateRequest,
        service: ContentService = Depends(get_service),
    ) -> SessionView:
        return service.regenerate(session_id, platform, payload.user_instruction)

    if FRONTEND_DIR.is_dir():
        app.mount(
            "/demo",
            StaticFiles(directory=FRONTEND_DIR, html=True),
            name="frontend-demo",
        )

    return app


app = create_app()
