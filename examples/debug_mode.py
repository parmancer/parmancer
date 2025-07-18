"""
Demonstration of debug mode functionality in parmancer.

Debug mode provides detailed information about parser execution when a parser fails:
additional information is kept at the cost of performance, so debug mode could be used
while developing a parser and then switched off when the parser is finished.

When debug=True is passed to .parse(), the error message will include:
- A parse tree showing which parsers have run and their results
- Successful parsers show their results with "= value" format
- Failed parsers are marked with "X (failed)"
"""

from dataclasses import dataclass
from parmancer import gather, regex, string, take, ParseError, seq, one_of


@dataclass
class Person:
    name: str = take(regex(r"\w+"))
    age: int = take(string(" ") >> regex(r"\d+").map(int))


def test_basic_debug_mode() -> None:
    """Demonstrate debug mode with a simple parser."""
    parser = string("hello")

    # Normal mode error should be concise
    try:
        parser.parse("world")
        assert False, "Expected ParseError"
    except ParseError as e:
        normal_error = str(e)
        assert "failed with ''hello''" in normal_error

    # Debug mode error should include parse tree
    try:
        parser.parse("world", debug=True)
        assert False, "Expected ParseError"
    except ParseError as e:
        debug_error = str(e)
        assert "Debug information:" in debug_error
        assert "Parse tree:" in debug_error
        assert "'hello' X (failed)" in debug_error


def test_complex_debug_mode() -> None:
    """Demonstrate debug mode with a complex dataclass parser."""
    parser = gather(Person)

    # This should fail when trying to parse the age
    try:
        parser.parse("John abc", debug=True)
        assert False, "Expected ParseError"
    except ParseError as e:
        debug_error = str(e)
        assert "Debug information:" in debug_error
        assert "Parse tree:" in debug_error
        # Should show the dataclass structure and field parsing
        assert "Person" in debug_error
        assert "field:name" in debug_error
        assert "field:age" in debug_error


def test_furthest_parser_tracking() -> None:
    """Demonstrate how debug mode shows the furthest parser that attempted to parse."""
    # Parser with multiple alternatives that fail at different positions
    parser = one_of(
        seq(string("hello"), string(" "), regex(r"\d+")).with_name("Option A"),
        seq(string("hello"), string(" "), regex(r"[A-Z]+")).with_name("Option B"),
    )

    try:
        parser.parse("hello world", debug=True)
        assert False, "Expected ParseError"
    except ParseError as e:
        debug_error = str(e)
        assert "Debug information:" in debug_error
        assert "Option A" in debug_error
        assert "Option B" in debug_error
        # Both alternatives should show they got past "hello " but failed on the final part
        assert "'hello' = 'hello'" in debug_error
        assert "' ' = ' '" in debug_error


def test_successful_parsing_with_debug() -> None:
    """Show that debug mode works for successful parsing too."""
    parser = gather(Person)

    # Debug mode should work the same for successful parsing
    result = parser.parse("Alice 25", debug=True)
    assert result == Person(name="Alice", age=25)
