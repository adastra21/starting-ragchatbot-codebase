# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the server (from project root)
./run.sh
# OR manually:
cd backend && uv run uvicorn app:app --reload --port 8000

# Run a single backend module directly
cd backend && uv run python <module>.py
```

The web UI is at `http://localhost:8000`, API docs at `http://localhost:8000/docs`.

## Architecture

This is a RAG (Retrieval-Augmented Generation) chatbot that answers questions about course materials. It uses Claude with tool-calling to search a ChromaDB vector database, then synthesizes answers from retrieved content.

### Query Flow

```
POST /api/query → app.py → RAGSystem.query() → AIGenerator.generate_response()
  → Claude API (with tool definitions) → Claude calls search_course_content tool
  → ToolManager → CourseSearchTool.execute() → VectorStore.search() → ChromaDB
  → results flow back → Claude generates final answer → response with sources
```

### Key Components (all in `backend/`)

- **app.py** - FastAPI application. Two endpoints: `POST /api/query` and `GET /api/courses`. Loads documents from `../docs/` on startup. Catches all exceptions and returns 500 with the error message as detail.
- **rag_system.py** - Orchestrator that wires together all components. `query()` is the main entry point for processing user questions.
- **ai_generator.py** - Claude API client. Handles the tool-use loop: sends initial request with tools, executes tool calls via ToolManager, sends results back to Claude for final answer. Model and params configured via `base_params` dict.
- **vector_store.py** - ChromaDB wrapper with two collections: `course_catalog` (course metadata, used for semantic course name resolution) and `course_content` (chunked text, used for content search). Course titles serve as IDs.
- **search_tools.py** - Tool abstraction layer. `Tool` ABC defines the interface; `CourseSearchTool` implements it for course search. `ToolManager` registers tools and routes Claude's tool calls to the right implementation. Sources are tracked on the tool instance (`last_sources`) and must be reset after retrieval.
- **document_processor.py** - Parses course text files with a specific format (title/link/instructor header, then `Lesson N: Title` sections). Chunks text by sentence boundaries respecting `CHUNK_SIZE`/`CHUNK_OVERLAP`.
- **config.py** - Dataclass config. Loads `.env` from project root via `python-dotenv`. Key settings: model (`claude-sonnet-4-20250514`), embedding model (`all-MiniLM-L6-v2`), chunk size (800), max results (5), max history (2).
- **session_manager.py** - In-memory conversation history keyed by session ID. History is formatted as a string and injected into the system prompt.
- **models.py** - Pydantic models: `Course`, `Lesson`, `CourseChunk`.

### Document Format

Course documents in `docs/` follow this structure:
```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <title>
Lesson Link: <url>
<content>

Lesson 1: <title>
...
```

### Frontend

Single-page app in `frontend/index.html`, served as static files by FastAPI. Communicates with the backend via `/api/query` and `/api/courses`.

## Configuration

- `.env` in project root must contain `ANTHROPIC_API_KEY`
- `config.py` reads env vars at module load time (before the `Config` dataclass is instantiated)
- ChromaDB persists to `backend/chroma_db/`; delete this directory to force re-indexing of documents
- The server runs from the `backend/` directory (CWD), so relative paths in config (like `./chroma_db` and `../docs`) are relative to `backend/`
