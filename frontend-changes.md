# Frontend Changes

No frontend files were modified in this change. This feature adds backend code quality tooling (black formatter and development scripts).

# Testing Framework Enhancements

## Changes Made

### 1. `pyproject.toml` — pytest configuration & new dev dependency

- Added `[tool.pytest.ini_options]` section with:
  - `testpaths = ["backend/tests"]` — so `uv run pytest` works from the project root without specifying paths
  - `pythonpath = ["backend"]` — ensures backend modules are importable
  - `markers` — defines an `integration` marker for tests that need real ChromaDB data
- Added `httpx>=0.28.0` to dev dependencies (required by FastAPI's `TestClient`)

### 2. `backend/tests/conftest.py` — shared fixtures & test app

Expanded the minimal path-setup file into a full fixture module:

- **Pydantic models** (`QueryRequest`, `Source`, `QueryResponse`, `CourseStats`) — mirrored from `app.py` to avoid importing the real app, which mounts static files from `../frontend/` that don't exist in the test environment.
- **`sample_sources`** fixture — reusable source dicts matching the `ToolManager.get_last_sources()` format.
- **`sample_course_titles`** fixture — reusable list of course title strings.
- **`mock_rag_system`** fixture — a `MagicMock` pre-configured with return values for `query()`, `session_manager.create_session()`, and `get_course_analytics()`.
- **`_build_test_app()`** helper — creates a lightweight FastAPI app with the same `/api/query` and `/api/courses` endpoints as the real app, wired to an injected (mock) RAG system. No static-file mount or startup event.
- **`test_app`** fixture — the test FastAPI app backed by `mock_rag_system`.
- **`client`** fixture — a synchronous `TestClient` for the test app.

### 3. `backend/tests/test_api.py` — API endpoint tests (20 tests)

New test file with four test classes:

| Class | Tests | What it covers |
|---|---|---|
| `TestQueryEndpoint` | 11 | `POST /api/query` — happy path, response shape, session creation/forwarding, input validation (missing field → 422, invalid JSON → 422), RAG exception → 500 |
| `TestCoursesEndpoint` | 5 | `GET /api/courses` — happy path, response shape, correct count/titles, analytics exception → 500 |
| `TestRootEndpoint` | 2 | Root `/` and unknown paths return 404 (no static mount in test app) |
| `TestSourceEdgeCases` | 2 | Sources with `null` link, empty sources list |

## Test Results

All 73 tests pass (53 existing + 20 new), no regressions:

```
backend/tests/test_ai_generator.py   — 15 passed
backend/tests/test_api.py            — 20 passed
backend/tests/test_rag_system.py     — 13 passed
backend/tests/test_search_tools.py   — 25 passed
```
