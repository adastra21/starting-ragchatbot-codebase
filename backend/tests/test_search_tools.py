"""Tests for CourseSearchTool.execute() and ToolManager."""

import pytest
from unittest.mock import MagicMock

from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from vector_store import SearchResults


class TestCourseSearchToolExecute:
    """Tests for the execute method of CourseSearchTool."""

    def setup_method(self):
        self.mock_store = MagicMock()
        self.tool = CourseSearchTool(self.mock_store)

    # --- Basic execution ---

    def test_execute_calls_store_search_with_query_only(self):
        """execute(query) should call store.search with correct args."""
        self.mock_store.search.return_value = SearchResults(
            documents=["content"], metadata=[{"course_title": "C", "lesson_number": 1}], distances=[0.5]
        )
        self.mock_store.get_lesson_link.return_value = None
        self.mock_store.get_course_link.return_value = None

        self.tool.execute(query="What is RAG?")

        self.mock_store.search.assert_called_once_with(
            query="What is RAG?", course_name=None, lesson_number=None
        )

    def test_execute_passes_course_name_filter(self):
        """execute(query, course_name) should forward course_name to store."""
        self.mock_store.search.return_value = SearchResults(
            documents=["content"], metadata=[{"course_title": "MCP", "lesson_number": 2}], distances=[0.3]
        )
        self.mock_store.get_lesson_link.return_value = None
        self.mock_store.get_course_link.return_value = None

        self.tool.execute(query="architecture", course_name="MCP")

        self.mock_store.search.assert_called_once_with(
            query="architecture", course_name="MCP", lesson_number=None
        )

    def test_execute_passes_lesson_number_filter(self):
        """execute(query, lesson_number) should forward lesson_number to store."""
        self.mock_store.search.return_value = SearchResults(
            documents=["content"], metadata=[{"course_title": "C", "lesson_number": 3}], distances=[0.2]
        )
        self.mock_store.get_lesson_link.return_value = None
        self.mock_store.get_course_link.return_value = None

        self.tool.execute(query="content", lesson_number=3)

        self.mock_store.search.assert_called_once_with(
            query="content", course_name=None, lesson_number=3
        )

    def test_execute_passes_all_filters(self):
        """execute(query, course_name, lesson_number) should forward both filters."""
        self.mock_store.search.return_value = SearchResults(
            documents=["content"], metadata=[{"course_title": "MCP", "lesson_number": 5}], distances=[0.1]
        )
        self.mock_store.get_lesson_link.return_value = None
        self.mock_store.get_course_link.return_value = None

        self.tool.execute(query="topic", course_name="MCP", lesson_number=5)

        self.mock_store.search.assert_called_once_with(
            query="topic", course_name="MCP", lesson_number=5
        )

    # --- Return value format ---

    def test_execute_returns_string(self):
        """execute should always return a string."""
        self.mock_store.search.return_value = SearchResults(
            documents=["RAG is retrieval-augmented generation."],
            metadata=[{"course_title": "AI Course", "lesson_number": 1}],
            distances=[0.5],
        )
        self.mock_store.get_lesson_link.return_value = "https://example.com/l1"

        result = self.tool.execute(query="What is RAG?")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_execute_result_contains_document_content(self):
        """Formatted result should contain the actual document text."""
        self.mock_store.search.return_value = SearchResults(
            documents=["RAG combines retrieval with generation for better answers."],
            metadata=[{"course_title": "AI", "lesson_number": 1}],
            distances=[0.3],
        )
        self.mock_store.get_lesson_link.return_value = None
        self.mock_store.get_course_link.return_value = None

        result = self.tool.execute(query="RAG")

        assert "RAG combines retrieval with generation" in result

    def test_execute_result_contains_course_context(self):
        """Formatted result should include course title header."""
        self.mock_store.search.return_value = SearchResults(
            documents=["Some content"],
            metadata=[{"course_title": "Deep Learning 101", "lesson_number": 2}],
            distances=[0.4],
        )
        self.mock_store.get_lesson_link.return_value = None
        self.mock_store.get_course_link.return_value = None

        result = self.tool.execute(query="test")

        assert "Deep Learning 101" in result
        assert "Lesson 2" in result

    # --- Empty / error results ---

    def test_execute_returns_message_on_empty_results(self):
        """execute should return a 'no results' message when search is empty."""
        self.mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )

        result = self.tool.execute(query="nonexistent topic")

        assert "No relevant content found" in result

    def test_execute_empty_results_include_course_filter_info(self):
        """Empty-results message should mention course name if filtered."""
        self.mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )

        result = self.tool.execute(query="x", course_name="MCP")

        assert "MCP" in result

    def test_execute_empty_results_include_lesson_filter_info(self):
        """Empty-results message should mention lesson number if filtered."""
        self.mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )

        result = self.tool.execute(query="x", lesson_number=5)

        assert "lesson 5" in result

    def test_execute_returns_error_message_from_store(self):
        """execute should relay the error message from SearchResults."""
        self.mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[],
            error="No course found matching 'xyz'"
        )

        result = self.tool.execute(query="test", course_name="xyz")

        assert result == "No course found matching 'xyz'"

    def test_execute_propagates_store_exception(self):
        """If store.search raises, execute should not swallow the exception."""
        self.mock_store.search.side_effect = Exception("DB connection lost")

        with pytest.raises(Exception, match="DB connection lost"):
            self.tool.execute(query="test")

    # --- Source tracking ---

    def test_execute_populates_last_sources(self):
        """After a successful search, last_sources should be populated."""
        self.mock_store.search.return_value = SearchResults(
            documents=["content"],
            metadata=[{"course_title": "AI Course", "lesson_number": 1}],
            distances=[0.4],
        )
        self.mock_store.get_lesson_link.return_value = "https://example.com/l1"

        self.tool.execute(query="test")

        assert len(self.tool.last_sources) == 1
        assert self.tool.last_sources[0]["text"] == "AI Course - Lesson 1"
        assert self.tool.last_sources[0]["link"] == "https://example.com/l1"

    def test_execute_falls_back_to_course_link(self):
        """If lesson link is None, source should use course link."""
        self.mock_store.search.return_value = SearchResults(
            documents=["content"],
            metadata=[{"course_title": "AI Course", "lesson_number": 1}],
            distances=[0.4],
        )
        self.mock_store.get_lesson_link.return_value = None
        self.mock_store.get_course_link.return_value = "https://example.com/course"

        self.tool.execute(query="test")

        assert self.tool.last_sources[0]["link"] == "https://example.com/course"

    def test_execute_deduplicates_sources(self):
        """Duplicate (same course + lesson) results should produce one source."""
        self.mock_store.search.return_value = SearchResults(
            documents=["chunk 1", "chunk 2"],
            metadata=[
                {"course_title": "AI", "lesson_number": 1},
                {"course_title": "AI", "lesson_number": 1},
            ],
            distances=[0.3, 0.4],
        )
        self.mock_store.get_lesson_link.return_value = None
        self.mock_store.get_course_link.return_value = None

        self.tool.execute(query="test")

        assert len(self.tool.last_sources) == 1

    def test_execute_empty_results_do_not_set_sources(self):
        """When search returns empty, last_sources should remain empty."""
        self.mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )

        self.tool.execute(query="nothing")

        assert self.tool.last_sources == []

    # --- Metadata edge cases ---

    def test_execute_handles_missing_lesson_number(self):
        """If metadata has no lesson_number key, formatting should not crash."""
        self.mock_store.search.return_value = SearchResults(
            documents=["content"],
            metadata=[{"course_title": "AI Course"}],  # no lesson_number
            distances=[0.4],
        )
        self.mock_store.get_course_link.return_value = None

        result = self.tool.execute(query="test")

        assert isinstance(result, str)
        assert "AI Course" in result

    def test_execute_handles_multiple_courses(self):
        """Results from different courses should each appear in output."""
        self.mock_store.search.return_value = SearchResults(
            documents=["content A", "content B"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2},
            ],
            distances=[0.3, 0.5],
        )
        self.mock_store.get_lesson_link.return_value = None
        self.mock_store.get_course_link.return_value = None

        result = self.tool.execute(query="test")

        assert "Course A" in result
        assert "Course B" in result

    # --- Tool definition ---

    def test_tool_definition_has_required_fields(self):
        """Tool definition must have name, description, and input_schema."""
        defn = self.tool.get_tool_definition()

        assert defn["name"] == "search_course_content"
        assert "description" in defn
        assert "input_schema" in defn
        assert "query" in defn["input_schema"]["properties"]
        assert defn["input_schema"]["required"] == ["query"]


class TestToolManager:
    """Tests for ToolManager registration and dispatch."""

    def test_register_and_list_tools(self):
        mgr = ToolManager()
        mock_store = MagicMock()
        mgr.register_tool(CourseSearchTool(mock_store))
        mgr.register_tool(CourseOutlineTool(mock_store))

        defs = mgr.get_tool_definitions()
        names = [d["name"] for d in defs]

        assert "search_course_content" in names
        assert "get_course_outline" in names

    def test_execute_unknown_tool_returns_error(self):
        mgr = ToolManager()
        result = mgr.execute_tool("nonexistent")
        assert "not found" in result

    def test_execute_routes_to_correct_tool(self):
        mgr = ToolManager()
        mock_store = MagicMock()
        mock_store.search.return_value = SearchResults(
            documents=["hit"], metadata=[{"course_title": "C", "lesson_number": 1}], distances=[0.1]
        )
        mock_store.get_lesson_link.return_value = None
        mock_store.get_course_link.return_value = None

        mgr.register_tool(CourseSearchTool(mock_store))
        result = mgr.execute_tool("search_course_content", query="test")

        assert isinstance(result, str)
        mock_store.search.assert_called_once()

    def test_get_last_sources_returns_populated_sources(self):
        mgr = ToolManager()
        mock_store = MagicMock()
        tool = CourseSearchTool(mock_store)
        tool.last_sources = [{"text": "S", "link": "http://x"}]
        mgr.register_tool(tool)

        assert mgr.get_last_sources() == [{"text": "S", "link": "http://x"}]

    def test_reset_sources_clears_all(self):
        mgr = ToolManager()
        mock_store = MagicMock()
        t1 = CourseSearchTool(mock_store)
        t2 = CourseOutlineTool(mock_store)
        t1.last_sources = [{"text": "A"}]
        t2.last_sources = [{"text": "B"}]
        mgr.register_tool(t1)
        mgr.register_tool(t2)

        mgr.reset_sources()

        assert t1.last_sources == []
        assert t2.last_sources == []
