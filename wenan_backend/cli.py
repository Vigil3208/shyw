from __future__ import annotations

import uvicorn

from .config import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "wenan_backend.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
