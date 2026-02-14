"""
API endpoint tests for the FastAPI application.

These tests use a lightweight test app (built in conftest.py) that mirrors
the real endpoints in app.py but skips the static-file mount and startup
event, so they run without needing the frontend directory or docs on disk.
"""

import pytest
from unittest.mock import MagicMock


# ── POST /api/query ──────────────────────────────────────────────────────


class TestQueryEndpoint:
    """Tests for POST /api/query"""

    def test_query_returns_200(self, client):
        resp = client.post("/api/query", json={"query": "What is Python?"})
        assert resp.status_code == 200

    def test_query_response_has_required_fields(self, client):
        resp = client.post("/api/query", json={"query": "What is Python?"})
        body = resp.json()
        assert "answer" in body
        assert "sources" in body
        assert "session_id" in body

    def test_query_returns_answer_from_rag(self, client):
        resp = client.post("/api/query", json={"query": "What is Python?"})
        body = resp.json()
        assert body["answer"] == "Python is a general-purpose programming language."

    def test_query_returns_sources_as_objects(self, client, sample_sources):
        resp = client.post("/api/query", json={"query": "What is Python?"})
        body = resp.json()
        assert len(body["sources"]) == len(sample_sources)
        for src in body["sources"]:
            assert "text" in src
            assert "link" in src

    def test_query_creates_session_when_not_provided(self, client):
        resp = client.post("/api/query", json={"query": "Hello"})
        body = resp.json()
        assert body["session_id"] == "test-session-id"

    def test_query_uses_provided_session_id(self, client, mock_rag_system):
        resp = client.post(
            "/api/query",
            json={"query": "Hello", "session_id": "my-session"},
        )
        body = resp.json()
        assert body["session_id"] == "my-session"
        mock_rag_system.query.assert_called_once_with("Hello", "my-session")

    def test_query_passes_question_to_rag(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "Explain decorators"})
        mock_rag_system.query.assert_called_once()
        args = mock_rag_system.query.call_args[0]
        assert args[0] == "Explain decorators"

    def test_query_missing_query_field_returns_422(self, client):
        resp = client.post("/api/query", json={})
        assert resp.status_code == 422

    def test_query_empty_string_is_accepted(self, client):
        resp = client.post("/api/query", json={"query": ""})
        assert resp.status_code == 200

    def test_query_rag_exception_returns_500(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("ChromaDB unavailable")
        resp = client.post("/api/query", json={"query": "Hello"})
        assert resp.status_code == 500
        assert "ChromaDB unavailable" in resp.json()["detail"]

    def test_query_invalid_json_returns_422(self, client):
        resp = client.post(
            "/api/query",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


# ── GET /api/courses ─────────────────────────────────────────────────────


class TestCoursesEndpoint:
    """Tests for GET /api/courses"""

    def test_courses_returns_200(self, client):
        resp = client.get("/api/courses")
        assert resp.status_code == 200

    def test_courses_response_has_required_fields(self, client):
        body = client.get("/api/courses").json()
        assert "total_courses" in body
        assert "course_titles" in body

    def test_courses_returns_correct_count(self, client, sample_course_titles):
        body = client.get("/api/courses").json()
        assert body["total_courses"] == len(sample_course_titles)

    def test_courses_returns_correct_titles(self, client, sample_course_titles):
        body = client.get("/api/courses").json()
        assert body["course_titles"] == sample_course_titles

    def test_courses_analytics_exception_returns_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("DB error")
        resp = client.get("/api/courses")
        assert resp.status_code == 500
        assert "DB error" in resp.json()["detail"]


# ── Root / static fallback ───────────────────────────────────────────────


class TestRootEndpoint:
    """The test app intentionally omits the static-file mount.
    Verify that unmounted paths return 404 (not a crash)."""

    def test_root_returns_404_without_static_mount(self, client):
        resp = client.get("/")
        assert resp.status_code == 404

    def test_unknown_path_returns_404(self, client):
        resp = client.get("/nonexistent")
        assert resp.status_code == 404


# ── Source model edge cases ──────────────────────────────────────────────


class TestSourceEdgeCases:
    """Verify that the API correctly serialises various source shapes."""

    def test_source_with_none_link(self, client, mock_rag_system):
        mock_rag_system.query.return_value = (
            "Answer",
            [{"text": "Some course", "link": None}],
        )
        body = client.post("/api/query", json={"query": "x"}).json()
        assert body["sources"][0]["link"] is None

    def test_empty_sources_list(self, client, mock_rag_system):
        mock_rag_system.query.return_value = ("No results found.", [])
        body = client.post("/api/query", json={"query": "x"}).json()
        assert body["sources"] == []
