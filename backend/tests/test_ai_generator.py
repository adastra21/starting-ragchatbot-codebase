"""Tests for AIGenerator tool-calling flow with CourseSearchTool."""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import List, Any

from ai_generator import AIGenerator

# ---------------------------------------------------------------------------
# Lightweight mock objects that mimic the Anthropic SDK response shapes
# ---------------------------------------------------------------------------


@dataclass
class MockTextBlock:
    text: str = ""
    type: str = "text"


@dataclass
class MockToolUseBlock:
    name: str = ""
    input: dict = field(default_factory=dict)
    id: str = "tool_abc123"
    type: str = "tool_use"


@dataclass
class MockResponse:
    content: List[Any] = field(default_factory=list)
    stop_reason: str = "end_turn"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_generator() -> AIGenerator:
    """Create an AIGenerator with a mocked Anthropic client."""
    with patch("anthropic.Anthropic"):
        gen = AIGenerator(api_key="test-key", model="test-model")
    gen.client = MagicMock()
    return gen


def _search_tool_defs() -> list:
    """Minimal tool definition list matching search_course_content."""
    return [
        {
            "name": "search_course_content",
            "description": "Search course materials",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        }
    ]


# ---------------------------------------------------------------------------
# Tests – direct (non-tool) responses
# ---------------------------------------------------------------------------


class TestDirectResponses:
    """When Claude does NOT call a tool."""

    def test_returns_text_from_response(self):
        gen = _make_generator()
        gen.client.messages.create.return_value = MockResponse(
            content=[MockTextBlock(text="Direct answer")], stop_reason="end_turn"
        )

        result = gen.generate_response("What is AI?")

        assert result == "Direct answer"
        assert gen.client.messages.create.call_count == 1

    def test_no_tool_manager_needed(self):
        gen = _make_generator()
        gen.client.messages.create.return_value = MockResponse(
            content=[MockTextBlock(text="Answer")], stop_reason="end_turn"
        )

        result = gen.generate_response("Hello", tools=_search_tool_defs())

        assert result == "Answer"

    def test_system_prompt_contains_tool_descriptions(self):
        gen = _make_generator()
        gen.client.messages.create.return_value = MockResponse(
            content=[MockTextBlock(text="x")], stop_reason="end_turn"
        )

        gen.generate_response("q")

        call_kw = gen.client.messages.create.call_args.kwargs
        assert "search_course_content" in call_kw["system"]
        assert "get_course_outline" in call_kw["system"]

    def test_conversation_history_appended(self):
        gen = _make_generator()
        gen.client.messages.create.return_value = MockResponse(
            content=[MockTextBlock(text="x")], stop_reason="end_turn"
        )

        gen.generate_response("q", conversation_history="User: Hi\nAssistant: Hello")

        call_kw = gen.client.messages.create.call_args.kwargs
        assert "Previous conversation" in call_kw["system"]
        assert "User: Hi" in call_kw["system"]


# ---------------------------------------------------------------------------
# Tests – tool-use responses  (the CourseSearchTool path)
# ---------------------------------------------------------------------------


class TestToolUseCalling:
    """When Claude decides to call search_course_content."""

    def _simulate_tool_round_trip(
        self,
        gen,
        tool_input,
        tool_output,
        final_text="Final answer",
        tool_name="search_course_content",
        tool_id="tool_abc123",
    ):
        """
        Set up the mock client to:
          1st call → tool_use response
          2nd call → final text response
        Returns the generate_response result.
        """
        tool_response = MockResponse(
            content=[
                MockTextBlock(text="Searching..."),
                MockToolUseBlock(name=tool_name, id=tool_id, input=tool_input),
            ],
            stop_reason="tool_use",
        )
        final_response = MockResponse(
            content=[MockTextBlock(text=final_text)], stop_reason="end_turn"
        )
        gen.client.messages.create.side_effect = [tool_response, final_response]

        mock_tm = MagicMock()
        mock_tm.execute_tool.return_value = tool_output

        result = gen.generate_response(
            query="question", tools=_search_tool_defs(), tool_manager=mock_tm
        )
        return result, mock_tm

    # --- Core flow ---

    def test_tool_call_triggers_two_api_calls(self):
        gen = _make_generator()
        self._simulate_tool_round_trip(gen, {"query": "RAG"}, "search results")
        assert gen.client.messages.create.call_count == 2

    def test_tool_manager_receives_correct_tool_name_and_input(self):
        gen = _make_generator()
        _, mock_tm = self._simulate_tool_round_trip(
            gen, {"query": "What is RAG?"}, "content about RAG"
        )
        mock_tm.execute_tool.assert_called_once_with(
            "search_course_content", query="What is RAG?"
        )

    def test_returns_final_text_after_tool_use(self):
        gen = _make_generator()
        result, _ = self._simulate_tool_round_trip(
            gen, {"query": "RAG"}, "results", final_text="RAG is …"
        )
        assert result == "RAG is …"

    # --- Follow-up message structure ---

    def test_followup_messages_have_three_entries(self):
        """user → assistant (tool_use) → user (tool_result)."""
        gen = _make_generator()
        self._simulate_tool_round_trip(gen, {"query": "q"}, "r")

        second_call_kw = gen.client.messages.create.call_args_list[1].kwargs
        msgs = second_call_kw["messages"]

        assert len(msgs) == 3
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[2]["role"] == "user"

    def test_followup_tool_result_format(self):
        """The tool_result block must have type, tool_use_id, and content."""
        gen = _make_generator()
        self._simulate_tool_round_trip(
            gen, {"query": "q"}, "tool output text", tool_id="id_42"
        )

        second_msgs = gen.client.messages.create.call_args_list[1].kwargs["messages"]
        tool_result_block = second_msgs[2]["content"][0]

        assert tool_result_block["type"] == "tool_result"
        assert tool_result_block["tool_use_id"] == "id_42"
        assert tool_result_block["content"] == "tool output text"

    def test_followup_call_excludes_tools(self):
        """The second API call should NOT include tools or tool_choice."""
        gen = _make_generator()
        self._simulate_tool_round_trip(gen, {"query": "q"}, "r")

        second_kw = gen.client.messages.create.call_args_list[1].kwargs
        assert "tools" not in second_kw
        assert "tool_choice" not in second_kw

    def test_followup_preserves_system_prompt(self):
        """The second call must carry the same system prompt."""
        gen = _make_generator()
        self._simulate_tool_round_trip(gen, {"query": "q"}, "r")

        first_kw = gen.client.messages.create.call_args_list[0].kwargs
        second_kw = gen.client.messages.create.call_args_list[1].kwargs
        assert second_kw["system"] == first_kw["system"]

    # --- Edge cases ---

    def test_tool_use_without_tool_manager_returns_first_text(self):
        """If no tool_manager is provided, fall back to content[0].text."""
        gen = _make_generator()
        gen.client.messages.create.return_value = MockResponse(
            content=[
                MockTextBlock(text="I would search, but can't"),
                MockToolUseBlock(name="search_course_content", input={"query": "q"}),
            ],
            stop_reason="tool_use",
        )

        result = gen.generate_response("q", tools=_search_tool_defs())

        assert result == "I would search, but can't"

    def test_tool_execution_exception_propagates(self):
        """If the tool raises, the exception should bubble up."""
        gen = _make_generator()
        gen.client.messages.create.return_value = MockResponse(
            content=[
                MockToolUseBlock(name="search_course_content", input={"query": "q"})
            ],
            stop_reason="tool_use",
        )
        mock_tm = MagicMock()
        mock_tm.execute_tool.side_effect = Exception("tool boom")

        with pytest.raises(Exception, match="tool boom"):
            gen.generate_response("q", tools=_search_tool_defs(), tool_manager=mock_tm)

    def test_api_exception_on_followup_propagates(self):
        """If the second API call fails, the error should propagate."""
        gen = _make_generator()
        tool_resp = MockResponse(
            content=[
                MockToolUseBlock(name="search_course_content", input={"query": "q"})
            ],
            stop_reason="tool_use",
        )
        gen.client.messages.create.side_effect = [
            tool_resp,
            Exception("API overloaded"),
        ]
        mock_tm = MagicMock()
        mock_tm.execute_tool.return_value = "results"

        with pytest.raises(Exception, match="API overloaded"):
            gen.generate_response("q", tools=_search_tool_defs(), tool_manager=mock_tm)

    # --- First call setup ---

    def test_first_call_includes_tools_and_tool_choice(self):
        gen = _make_generator()
        self._simulate_tool_round_trip(gen, {"query": "q"}, "r")

        first_kw = gen.client.messages.create.call_args_list[0].kwargs
        assert "tools" in first_kw
        assert first_kw["tool_choice"] == {"type": "auto"}
