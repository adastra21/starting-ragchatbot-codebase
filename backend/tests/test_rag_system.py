"""Tests for RAGSystem.query() – the full content-query pipeline."""

import pytest
from unittest.mock import MagicMock, patch, call
from dataclasses import dataclass, field
from typing import List, Any

from vector_store import SearchResults

# ---------------------------------------------------------------------------
# Mock Anthropic SDK objects (same as test_ai_generator)
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
# Helpers
# ---------------------------------------------------------------------------


def _mock_config():
    cfg = MagicMock()
    cfg.CHUNK_SIZE = 800
    cfg.CHUNK_OVERLAP = 100
    cfg.CHROMA_PATH = "./test_chroma"
    cfg.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    cfg.MAX_RESULTS = 5
    cfg.ANTHROPIC_API_KEY = "test-key"
    cfg.ANTHROPIC_MODEL = "test-model"
    cfg.MAX_HISTORY = 2
    return cfg


# ---------------------------------------------------------------------------
# Tests – tool registration
# ---------------------------------------------------------------------------


class TestToolRegistration:

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_both_tools_registered(self, _sm, _dp, _vs, _ai):
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())

        names = list(rag.tool_manager.tools.keys())
        assert "search_course_content" in names
        assert "get_course_outline" in names

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_tool_definitions_passed_to_generator(self, _sm, _dp, _vs, _ai):
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())
        rag.ai_generator.generate_response.return_value = "resp"

        rag.query("q")

        kw = rag.ai_generator.generate_response.call_args.kwargs
        assert len(kw["tools"]) == 2
        assert kw["tool_manager"] is rag.tool_manager


# ---------------------------------------------------------------------------
# Tests – query plumbing
# ---------------------------------------------------------------------------


class TestQueryPlumbing:

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_query_wraps_user_question(self, _sm, _dp, _vs, _ai):
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())
        rag.ai_generator.generate_response.return_value = "resp"

        rag.query("What is RAG?")

        prompt = rag.ai_generator.generate_response.call_args.kwargs["query"]
        assert "What is RAG?" in prompt
        assert "course materials" in prompt.lower()

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_query_returns_tuple(self, _sm, _dp, _vs, _ai):
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())
        rag.ai_generator.generate_response.return_value = "answer"

        result = rag.query("q")

        assert isinstance(result, tuple)
        assert len(result) == 2
        response, sources = result
        assert response == "answer"
        assert isinstance(sources, list)

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_session_history_forwarded(self, _sm, _dp, _vs, _ai):
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())
        rag.session_manager.get_conversation_history.return_value = "User: Hi"
        rag.ai_generator.generate_response.return_value = "resp"

        rag.query("q", session_id="s1")

        kw = rag.ai_generator.generate_response.call_args.kwargs
        assert kw["conversation_history"] == "User: Hi"

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_no_session_sends_none_history(self, _sm, _dp, _vs, _ai):
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())
        rag.ai_generator.generate_response.return_value = "resp"

        rag.query("q")

        kw = rag.ai_generator.generate_response.call_args.kwargs
        assert kw["conversation_history"] is None


# ---------------------------------------------------------------------------
# Tests – source lifecycle
# ---------------------------------------------------------------------------


class TestSourceLifecycle:

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_sources_returned_from_search_tool(self, _sm, _dp, _vs, _ai):
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())
        rag.search_tool.last_sources = [
            {"text": "AI Course - Lesson 1", "link": "http://example.com"}
        ]
        rag.ai_generator.generate_response.return_value = "answer"

        _, sources = rag.query("q")

        assert len(sources) == 1
        assert sources[0]["text"] == "AI Course - Lesson 1"

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_sources_reset_after_query(self, _sm, _dp, _vs, _ai):
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())
        rag.search_tool.last_sources = [{"text": "S", "link": None}]
        rag.ai_generator.generate_response.return_value = "answer"

        rag.query("q")

        assert rag.search_tool.last_sources == []

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_empty_sources_when_no_tool_called(self, _sm, _dp, _vs, _ai):
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())
        rag.ai_generator.generate_response.return_value = "general answer"

        _, sources = rag.query("What is machine learning?")

        assert sources == []


# ---------------------------------------------------------------------------
# Tests – error propagation
# ---------------------------------------------------------------------------


class TestErrorPropagation:

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_generator_exception_propagates(self, _sm, _dp, _vs, _ai):
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())
        rag.ai_generator.generate_response.side_effect = Exception("API down")

        with pytest.raises(Exception, match="API down"):
            rag.query("q")


# ---------------------------------------------------------------------------
# Tests – end-to-end tool execution through the RAG system
# ---------------------------------------------------------------------------


class TestEndToEndToolExecution:
    """Simulate the full path: query → AI calls tool → tool hits store → answer."""

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_search_tool_produces_valid_output(self, _sm, _dp, _vs, _ai):
        """Directly invoke the registered search tool through the manager."""
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())

        # Wire the mock vector store to return results
        rag.vector_store.search.return_value = SearchResults(
            documents=["RAG combines retrieval and generation."],
            metadata=[{"course_title": "AI Fundamentals", "lesson_number": 2}],
            distances=[0.25],
        )
        rag.vector_store.get_lesson_link.return_value = "https://example.com/ai/2"

        result = rag.tool_manager.execute_tool(
            "search_course_content", query="What is RAG?"
        )

        assert isinstance(result, str)
        assert "RAG" in result
        assert "AI Fundamentals" in result

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_search_tool_error_returns_message_not_exception(self, _sm, _dp, _vs, _ai):
        """store.search returning an error should yield a message, not crash."""
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())

        rag.vector_store.search.return_value = SearchResults(
            documents=[],
            metadata=[],
            distances=[],
            error="Search error: collection is empty",
        )

        result = rag.tool_manager.execute_tool(
            "search_course_content", query="anything"
        )

        assert "Search error" in result

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_full_query_with_simulated_tool_call(self, _sm, _dp, _vs, _ai):
        """
        Simulate the complete flow: generate_response calls the search tool
        through tool_manager, then returns a final answer.
        """
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())

        # Set up vector store mock
        rag.vector_store.search.return_value = SearchResults(
            documents=["MCP is Model Context Protocol"],
            metadata=[{"course_title": "MCP Course", "lesson_number": 1}],
            distances=[0.2],
        )
        rag.vector_store.get_lesson_link.return_value = "https://example.com/mcp/1"

        # Make generate_response simulate the tool call internally
        def fake_generate(
            query, conversation_history=None, tools=None, tool_manager=None
        ):
            if tool_manager and tools:
                tool_result = tool_manager.execute_tool(
                    "search_course_content", query="MCP"
                )
                assert isinstance(tool_result, str)
                assert len(tool_result) > 0
                return f"Based on content: {tool_result}"
            return "no tools"

        rag.ai_generator.generate_response.side_effect = fake_generate

        response, sources = rag.query("What is MCP?")

        assert "MCP" in response
        assert len(sources) == 1
        assert sources[0]["text"] == "MCP Course - Lesson 1"
        assert sources[0]["link"] == "https://example.com/mcp/1"

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_store_exception_during_tool_call_propagates(self, _sm, _dp, _vs, _ai):
        """
        If vector_store.search raises during a tool call, the exception
        should propagate up through rag.query() so the API returns 500.
        """
        from rag_system import RAGSystem

        rag = RAGSystem(_mock_config())

        rag.vector_store.search.side_effect = Exception("ChromaDB crashed")

        def fake_generate(
            query, conversation_history=None, tools=None, tool_manager=None
        ):
            if tool_manager:
                return tool_manager.execute_tool("search_course_content", query="q")
            return "no tools"

        rag.ai_generator.generate_response.side_effect = fake_generate

        with pytest.raises(Exception, match="ChromaDB crashed"):
            rag.query("q")
