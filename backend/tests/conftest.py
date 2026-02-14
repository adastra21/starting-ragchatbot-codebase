import sys
import os

# Add backend directory to path so we can import modules directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional


# ---------------------------------------------------------------------------
# Pydantic models (mirrored from app.py to avoid importing the real app,
# which mounts static files that don't exist in the test environment)
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class Source(BaseModel):
    text: str
    link: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


# ---------------------------------------------------------------------------
# Sample test data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_sources():
    """Source dicts as returned by ToolManager.get_last_sources()."""
    return [
        {"text": "Intro to Python - Lesson 1", "link": "https://example.com/python/1"},
        {"text": "Intro to Python - Lesson 2", "link": "https://example.com/python/2"},
    ]


@pytest.fixture
def sample_course_titles():
    return ["Intro to Python", "Advanced Machine Learning", "Web Development 101"]


# ---------------------------------------------------------------------------
# Mock RAG system
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_rag_system(sample_sources, sample_course_titles):
    """A MagicMock that behaves like RAGSystem for the API layer."""
    rag = MagicMock()

    # query() returns (answer_string, sources_list)
    rag.query.return_value = (
        "Python is a general-purpose programming language.",
        sample_sources,
    )

    # session_manager.create_session() returns a deterministic ID
    rag.session_manager.create_session.return_value = "test-session-id"

    # get_course_analytics() returns a stats dict
    rag.get_course_analytics.return_value = {
        "total_courses": len(sample_course_titles),
        "course_titles": sample_course_titles,
    }

    return rag


# ---------------------------------------------------------------------------
# Test FastAPI app & client
#
# We build a lightweight app that replicates the real endpoints from app.py
# but without the static-file mount or startup event, so tests run without
# needing the frontend directory or document files on disk.
# ---------------------------------------------------------------------------


def _build_test_app(rag_system):
    """Create a FastAPI app wired to the given (mock) RAG system."""
    test_app = FastAPI()

    @test_app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()
            answer, sources = rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @test_app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return test_app


@pytest.fixture
def test_app(mock_rag_system):
    """A FastAPI application backed by mock_rag_system."""
    return _build_test_app(mock_rag_system)


@pytest.fixture
def client(test_app):
    """Synchronous test client for the test app."""
    return TestClient(test_app)
