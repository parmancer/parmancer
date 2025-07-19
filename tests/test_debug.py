"""Tests for debug mode functionality."""

import pytest
from dataclasses import dataclass

from parmancer import (
    ParseError,
    DebugTextState,
    TextState,
    gather,
    regex,
    string,
    take,
    seq,
    one_of,
)


def test_debug_mode_basic_failure() -> None:
    """Test that debug mode provides enhanced error information on failure."""
    parser = string("hello")

    # Test normal mode
    with pytest.raises(ParseError) as exc_info:
        parser.parse("world")

    normal_error = str(exc_info.value)
    assert "Debug information:" not in normal_error

    # Test debug mode
    with pytest.raises(ParseError) as exc_info:
        parser.parse("world", debug=True)

    debug_error = str(exc_info.value)
    assert "Debug information:" in debug_error
    assert "Parse tree:" in debug_error
    assert "X (failed)" in debug_error  # New failure marker


def test_debug_mode_with_complex_parser() -> None:
    """Test debug mode with a more complex parser structure."""

    @dataclass
    class Person:
        name: str = take(regex(r"\w+"))
        age: int = take(string(" ") >> regex(r"\d+").map(int))

    parser = gather(Person)

    # This should fail when trying to parse the age
    with pytest.raises(ParseError) as exc_info:
        parser.parse("John abc", debug=True)

    debug_error = str(exc_info.value)
    assert "Debug information:" in debug_error
    assert "Parse tree:" in debug_error
    # Should show the dataclass structure and field parsing
    assert "Person" in debug_error
    assert "field:name" in debug_error
    assert "field:age" in debug_error


def test_debug_mode_success_case() -> None:
    """Test that debug mode works correctly for successful parsing."""
    parser = string("hello")

    # Should work the same in both modes for successful parsing
    result_normal = parser.parse("hello")
    result_debug = parser.parse("hello", debug=True)

    assert result_normal == result_debug == "hello"


def test_debug_text_state_directly() -> None:
    """Test DebugTextState functionality directly."""
    state = DebugTextState.start("hello world")

    # Test that it behaves like a normal TextState
    assert state.text == "hello world"
    assert state.index == 0
    assert state.failures == tuple()

    # Test that it has the tree attribute
    assert hasattr(state, "tree")
    assert state.tree.name == "Parser"
    assert state.tree.children == []


def test_debug_state_progress() -> None:
    """Test that DebugTextState maintains tree state across progress calls."""
    state = DebugTextState.start("hello")

    # Progress to a new position
    new_state = state.progress(3)

    # Should maintain the tree
    assert hasattr(new_state, "tree")
    assert isinstance(new_state, DebugTextState)
    assert new_state.index == 3


def test_debug_mode_with_match_method() -> None:
    """Test that debug mode works with the match method as well."""
    parser = string("hello")

    # Test normal match
    result_normal = parser.match("world")
    assert not result_normal.status

    # Test debug match
    result_debug = parser.match("world", debug=True)
    assert not result_debug.status
    assert isinstance(result_debug.state, DebugTextState)


def test_debug_info_format() -> None:
    """Test that debug information is properly formatted."""
    parser = string("expected") >> string("text")

    with pytest.raises(ParseError) as exc_info:
        parser.parse("wrong input", debug=True)

    debug_error = str(exc_info.value)

    # Check that all expected sections are present
    assert "Debug information:" in debug_error
    assert "=" * 18 in debug_error  # New shorter header separator
    assert "Parse tree:" in debug_error
    assert "X (failed)" in debug_error  # New failure marker


def test_debug_mode_preserves_original_error() -> None:
    """Test that debug mode includes the original error information."""
    parser = string("hello")

    with pytest.raises(ParseError) as exc_info:
        parser.parse("world", debug=True)

    error_str = str(exc_info.value)

    # Should contain both the original error and debug info
    assert "failed with" in error_str  # Original error format
    assert "Debug information:" in error_str  # Debug info


def test_debug_mode_with_nested_parsers() -> None:
    """Test debug mode with nested parser structures."""
    inner_parser = string("inner")
    outer_parser = string("outer") >> inner_parser

    with pytest.raises(ParseError) as exc_info:
        outer_parser.parse("outer wrong", debug=True)

    debug_error = str(exc_info.value)
    assert "Debug information:" in debug_error
    # The parse tree should show the nested structure
    assert "Parse tree:" in debug_error


def test_furthest_parser_tracking() -> None:
    """Test that debug mode correctly identifies the furthest parser that attempted to parse."""
    # Create a parser with multiple alternatives that fail at different positions
    parser = one_of(
        seq(string("hello"), string(" "), regex(r"\d+")),
        seq(string("hello"), string(" "), regex(r"[A-Z]+")),
    )

    with pytest.raises(ParseError) as exc_info:
        parser.parse("hello world", debug=True)

    debug_error = str(exc_info.value)

    # Should show the parse tree with both failed alternatives
    assert "Debug information:" in debug_error
    assert "Parse tree:" in debug_error
    # Should show both failed parsers in the tree
    assert "\\d+ X (failed)" in debug_error
    assert "[A-Z]+ X (failed)" in debug_error
    # Should show successful parsers before the failures
    assert "'hello' = 'hello'" in debug_error
    assert "' ' = ' '" in debug_error


def test_debug_mode_shows_successful_parsers() -> None:
    """Test that debug mode shows which parsers succeeded before the failure."""
    parser = seq(string("hello"), string(" "), regex(r"\d+"))

    with pytest.raises(ParseError) as exc_info:
        parser.parse("hello world", debug=True)

    debug_error = str(exc_info.value)

    # Should show the successful parsers in the parse tree with new format
    assert "'hello' = 'hello'" in debug_error
    assert "' ' = ' '" in debug_error
    # Should show the failed parser with new failure marker
    assert "\\d+ X (failed)" in debug_error


def test_debug_mode_type_overloads() -> None:
    """Test that the type overloads work correctly for debug mode."""
    parser = string("hello")

    # Test debug=True (should work without state_handler)
    result1 = parser.parse("hello", debug=True)
    assert result1 == "hello"

    # Test debug=False with state_handler (should work)
    result2 = parser.parse("hello", state_handler=TextState, debug=False)
    assert result2 == "hello"

    # Test default behavior (should work)
    result3 = parser.parse("hello")
    assert result3 == "hello"

    # Test match method with debug=True
    result4 = parser.match("hello", debug=True)
    assert result4.status is True
    assert result4.value == "hello"

    # Test match method with state_handler
    result5 = parser.match("hello", state_handler=TextState)
    assert result5.status is True
    assert result5.value == "hello"
