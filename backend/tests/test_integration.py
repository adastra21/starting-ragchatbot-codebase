"""
Integration tests that exercise real components (VectorStore, ChromaDB,
CourseSearchTool) against the actual persisted data and the live API endpoint.

These tests do NOT mock the vector store — they use the real chroma_db on disk.
The Anthropic API is mocked where needed to avoid costs / flakiness.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import List, Any

# ---------------------------------------------------------------------------
# Real component imports
# ---------------------------------------------------------------------------
from config import Config
from vector_store import VectorStore, SearchResults
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from ai_generator import AIGenerator


# ---------------------------------------------------------------------------
# Mock Anthropic SDK objects
# ---------------------------------------------------------------------------

@dataclass
class MockTextBlock:
    text: str = ""
    type: str = "text"

@dataclass
class MockToolUseBlock:
    name: str = ""
    input: dict = field(default_factory=dict)
    id: str = "tool_abc"
    type: str = "tool_use"

@dataclass
class MockResponse:
    content: List[Any] = field(default_factory=list)
    stop_reason: str = "end_turn"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_vector_store():
    """Create a VectorStore pointing at the real chroma_db on disk."""
    chroma_path = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
    if not os.path.exists(chroma_path):
        pytest.skip("No chroma_db directory — run the server once to populate it")
    cfg = Config()
    return VectorStore(chroma_path, cfg.EMBEDDING_MODEL, cfg.MAX_RESULTS)


@pytest.fixture
def search_tool(real_vector_store):
    return CourseSearchTool(real_vector_store)


@pytest.fixture
def outline_tool(real_vector_store):
    return CourseOutlineTool(real_vector_store)


@pytest.fixture
def tool_manager(search_tool, outline_tool):
    mgr = ToolManager()
    mgr.register_tool(search_tool)
    mgr.register_tool(outline_tool)
    return mgr


# ---------------------------------------------------------------------------
# 1. Real VectorStore tests
# ---------------------------------------------------------------------------

class TestRealVectorStore:
    """Verify the real ChromaDB data is accessible and searchable."""

    def test_courses_exist(self, real_vector_store):
        """There should be at least one course in the catalog."""
        titles = real_vector_store.get_existing_course_titles()
        assert len(titles) > 0, "No courses found in chroma_db"

    def test_course_content_collection_not_empty(self, real_vector_store):
        """The course_content collection should have documents."""
        count = real_vector_store.course_content.count()
        assert count > 0, "course_content collection is empty"

    def test_search_returns_results(self, real_vector_store):
        """A broad query should return at least one result from course_content."""
        results = real_vector_store.search(query="What is this course about?")
        assert not results.error, f"Search returned error: {results.error}"
        assert not results.is_empty(), "Search returned no documents"

    def test_search_results_have_expected_metadata(self, real_vector_store):
        """Each result should carry course_title and lesson_number metadata."""
        results = real_vector_store.search(query="introduction")
        assert not results.is_empty()
        for meta in results.metadata:
            assert "course_title" in meta, f"Missing course_title in metadata: {meta}"
            assert "lesson_number" in meta, f"Missing lesson_number in metadata: {meta}"

    def test_resolve_course_name(self, real_vector_store):
        """Semantic name resolution should find a real course."""
        titles = real_vector_store.get_existing_course_titles()
        # Use a substring of the first course title
        first_title = titles[0]
        short_name = first_title.split(":")[0] if ":" in first_title else first_title[:10]

        resolved = real_vector_store._resolve_course_name(short_name)
        assert resolved is not None, f"Could not resolve '{short_name}'"

    def test_search_with_course_filter(self, real_vector_store):
        """Filtered search should return results for a known course."""
        titles = real_vector_store.get_existing_course_titles()
        results = real_vector_store.search(
            query="lesson content", course_name=titles[0]
        )
        assert not results.error, f"Filtered search error: {results.error}"

    def test_get_course_metadata(self, real_vector_store):
        """get_course_metadata should return title, lessons, etc."""
        titles = real_vector_store.get_existing_course_titles()
        meta = real_vector_store.get_course_metadata(titles[0])
        assert meta is not None, "get_course_metadata returned None"
        assert "title" in meta
        assert "lessons" in meta


# ---------------------------------------------------------------------------
# 2. Real CourseSearchTool tests
# ---------------------------------------------------------------------------

class TestRealCourseSearchTool:
    """Run CourseSearchTool.execute() against real ChromaDB data."""

    def test_execute_broad_query(self, search_tool):
        """A general query should return formatted content, not an error."""
        result = search_tool.execute(query="What is this course about?")
        assert isinstance(result, str)
        assert "No relevant content found" not in result, "Expected results but got empty"
        assert len(result) > 20, f"Result suspiciously short: {result!r}"

    def test_execute_specific_query(self, search_tool):
        """A topic-specific query should return relevant content."""
        result = search_tool.execute(query="machine learning")
        assert isinstance(result, str)
        # Should be either content or a 'no results' message — not a crash
        assert len(result) > 0

    def test_execute_with_real_course_name(self, search_tool, real_vector_store):
        """Search filtered by a real course name should work."""
        titles = real_vector_store.get_existing_course_titles()
        result = search_tool.execute(query="introduction", course_name=titles[0])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_execute_sets_sources(self, search_tool):
        """After a successful search, last_sources should be populated."""
        search_tool.execute(query="What is this course about?")
        assert isinstance(search_tool.last_sources, list)
        # If content was found, sources should be non-empty
        # (could be empty if the query happened to find nothing)

    def test_execute_sources_have_text_and_link_keys(self, search_tool):
        """Each source dict should have 'text' and 'link' — no leftover keys."""
        search_tool.execute(query="What is this course about?")
        for source in search_tool.last_sources:
            assert "text" in source, f"Source missing 'text': {source}"
            assert "link" in source, f"Source missing 'link': {source}"
            unexpected = set(source.keys()) - {"text", "link"}
            assert not unexpected, f"Unexpected keys in source: {unexpected}"


# ---------------------------------------------------------------------------
# 3. Real CourseOutlineTool tests (control — this path works)
# ---------------------------------------------------------------------------

class TestRealCourseOutlineTool:
    """Verify the outline tool works against real data (known working path)."""

    def test_execute_returns_outline(self, outline_tool, real_vector_store):
        titles = real_vector_store.get_existing_course_titles()
        short = titles[0].split(":")[0] if ":" in titles[0] else titles[0][:10]
        result = outline_tool.execute(course_name=short)
        assert "Course:" in result
        assert "Lesson" in result


# ---------------------------------------------------------------------------
# 4. ToolManager routing with real tools
# ---------------------------------------------------------------------------

class TestRealToolManager:
    """Test that ToolManager correctly routes to real tool instances."""

    def test_execute_search_via_manager(self, tool_manager):
        result = tool_manager.execute_tool(
            "search_course_content", query="introduction"
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_execute_outline_via_manager(self, tool_manager, real_vector_store):
        titles = real_vector_store.get_existing_course_titles()
        result = tool_manager.execute_tool(
            "get_course_outline", course_name=titles[0]
        )
        assert isinstance(result, str)
        assert "Course:" in result


# ---------------------------------------------------------------------------
# 5. AIGenerator integration — mock only the Anthropic API
# ---------------------------------------------------------------------------

class TestAIGeneratorWithRealTools:
    """
    Use a real ToolManager + real CourseSearchTool + real VectorStore,
    but mock the Anthropic client to avoid live API calls.
    This tests the exact code path that fails in production.
    """

    def test_content_query_full_path(self, tool_manager, real_vector_store):
        """
        Simulate Claude calling search_course_content:
        1st API call → tool_use
        2nd API call → final text
        Verify no exceptions in the full chain.
        """
        with patch("anthropic.Anthropic"):
            gen = AIGenerator(api_key="test", model="test")
        gen.client = MagicMock()

        # 1st response: Claude decides to search
        tool_response = MockResponse(
            content=[
                MockToolUseBlock(
                    name="search_course_content",
                    id="tool_1",
                    input={"query": "What is this course about?"},
                ),
            ],
            stop_reason="tool_use",
        )
        # 2nd response: Claude synthesizes an answer
        final_response = MockResponse(
            content=[MockTextBlock(text="This course covers…")],
            stop_reason="end_turn",
        )
        gen.client.messages.create.side_effect = [tool_response, final_response]

        result = gen.generate_response(
            query="What is this course about?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager,
        )

        assert result == "This course covers…"
        sources = tool_manager.get_last_sources()
        assert isinstance(sources, list)

    def test_content_query_tool_result_is_string(self, tool_manager):
        """The tool result passed back to Claude must be a string."""
        result = tool_manager.execute_tool(
            "search_course_content", query="introduction"
        )
        assert isinstance(result, str), (
            f"Tool returned {type(result).__name__}, expected str. "
            f"Value: {result!r}"
        )


# ---------------------------------------------------------------------------
# 6. FastAPI endpoint integration (mock Anthropic, use real everything else)
# ---------------------------------------------------------------------------

class TestQueryResponseModel:
    """
    Test that the Pydantic response model in app.py can accept the source
    format produced by the tool system.

    ROOT CAUSE: The original QueryResponse had `sources: List[str]`, but
    ToolManager.get_last_sources() returns `[{"text": "...", "link": "..."}]`.
    Pydantic rejects dicts for List[str] → ValidationError → HTTP 500.
    """

    def test_source_format_matches_response_model(self, search_tool):
        """Sources from a real search must be valid for the API response model."""
        from app import Source, QueryResponse

        search_tool.execute(query="What is this course about?")
        sources = search_tool.last_sources

        # This is the exact construction the endpoint does — it must not raise
        try:
            QueryResponse(
                answer="test answer",
                sources=sources,
                session_id="session_1",
            )
        except Exception as e:
            pytest.fail(
                f"QueryResponse rejected tool sources: {e}\n"
                f"Sources were: {sources}\n"
                f"This means the Source/QueryResponse model in app.py does not "
                f"match the dict format returned by ToolManager.get_last_sources()."
            )

    def test_source_model_accepts_dict_with_text_and_link(self):
        """The Source model must accept the dict shape tools produce."""
        from app import Source

        src = Source(**{"text": "AI Course - Lesson 1", "link": "https://example.com"})
        assert src.text == "AI Course - Lesson 1"
        assert src.link == "https://example.com"

    def test_source_model_accepts_none_link(self):
        """Source.link should be optional (None is valid)."""
        from app import Source

        src = Source(**{"text": "Course", "link": None})
        assert src.link is None

    def test_query_response_rejects_plain_strings_as_sources(self):
        """
        Regression guard: if sources is List[Source], plain strings must
        NOT be silently accepted — that would hide the opposite bug.
        """
        from app import QueryResponse
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            QueryResponse(
                answer="test",
                sources=["plain string source"],
                session_id="s1",
            )
