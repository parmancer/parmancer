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


def demo_basic_debug() -> None:
    """Demonstrate debug mode with a simple parser."""
    print("=== Basic Debug Mode Demo ===")
    parser = string("hello")

    print("Normal mode error:")
    try:
        parser.parse("world")
    except ParseError as e:
        print(str(e))

    print("\nDebug mode error:")
    try:
        parser.parse("world", debug=True)
    except ParseError as e:
        print(str(e))


def demo_complex_debug() -> None:
    """Demonstrate debug mode with a complex dataclass parser."""
    print("\n=== Complex Parser Debug Mode Demo ===")
    parser = gather(Person)

    print("Attempting to parse 'John abc' (should fail on age parsing):")
    try:
        parser.parse("John abc", debug=True)
    except ParseError as e:
        print(str(e))


def demo_furthest_parser_tracking() -> None:
    """Demonstrate how debug mode shows the furthest parser that attempted to parse."""
    print("\n=== Furthest Parser Tracking Demo ===")

    # Parser with multiple alternatives that fail at different positions
    parser = one_of(
        seq(string("hello"), string(" "), regex(r"\d+")).with_name("Option A"),
        seq(string("hello"), string(" "), regex(r"[A-Z]+")).with_name("Option B"),
    )

    print("Attempting to parse 'hello world' with multiple alternatives:")
    print("- First alternative expects digits after 'hello '")
    print("- Second alternative expects uppercase letters after 'hello '")
    print("Both will fail at the same furthest position (after 'hello '):")

    try:
        parser.parse("hello world", debug=True)
    except ParseError as e:
        print(str(e))


def demo_successful_parsing() -> None:
    """Show that debug mode works for successful parsing too."""
    print("\n=== Successful Parsing with Debug Mode ===")
    parser = gather(Person)

    result = parser.parse("Alice 25", debug=True)
    print(f"Successfully parsed: {result}")


if __name__ == "__main__":
    demo_basic_debug()
    demo_complex_debug()
    demo_furthest_parser_tracking()
    demo_successful_parsing()
