# Repository Guidelines

## Project Structure & Module Organization

The FastAPI backend lives in `wenan_backend/`. Keep HTTP routes and app construction in `app.py`, command-line startup in `cli.py`, workflow orchestration in `workflow.py`, persistence in `repository.py`, and request/response models in `schemas.py`. Fact extraction, validation, prompts, and model agents have dedicated modules. `main.py` is a minimal local entry point. Tests are under `tests/` and mirror backend concerns (for example, `test_validation.py`). Runtime session data is written to `data/` and must remain untracked. Product requirements are documented in `需求规格说明书.md`.

## Build, Test, and Development Commands

- `uv sync --extra dev` installs Python 3.11+ runtime and test dependencies from `uv.lock`.
- `uv run wenan-api` starts the configured FastAPI service.
- `uv run python main.py` provides an equivalent local entry point.
- `uv run pytest` runs the complete test suite; pytest is configured for quiet output and discovers `tests/`.
- `uv build` creates wheel and source distributions through Hatchling.

Copy `.env.example` to `.env` for local configuration. Use `APP_MODEL_MODE=local` when developing without an external model API.

## Coding Style & Naming Conventions

Use four-space indentation, UTF-8, type hints, and standard PEP 8 naming: `snake_case` for modules, functions, and variables; `PascalCase` for classes; and `UPPER_SNAKE_CASE` for constants. Keep functions focused and preserve the current separation between API, service, workflow, repository, and validation layers. No formatter or linter is currently configured, so match surrounding code and keep imports grouped as standard library, third-party, then local.

## Testing Guidelines

Tests use `pytest` and FastAPI’s `TestClient`. Name files `test_<area>.py` and tests `test_<behavior>()`. Use `tmp_path` for persistence tests and local model mode to keep tests deterministic and network-independent. Add tests for success paths, validation failures, HTTP status codes, and persisted state when changing behavior. Run `uv run pytest` before opening a pull request.

## Commit & Pull Request Guidelines

The repository has no commit history yet, so no established convention exists. Use short, imperative commit subjects such as `Add session regeneration validation`, and keep unrelated changes separate. Pull requests should explain the behavior change, list verification commands, link relevant issues or requirements, and include sample requests/responses for API changes. Call out schema, environment-variable, or persistence-format changes explicitly.

## Security & Configuration

Never commit `.env`, API keys, or generated `data/`. Update `.env.example` whenever configuration options change, using safe placeholder values only.
