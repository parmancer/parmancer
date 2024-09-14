import re
from dataclasses import dataclass

from parmancer import gather, padding, regex, seq, string, take, whitespace


def test_combining_parsers() -> None:
    """
    Create small parsers then combine them together to parse larger inputs.
    Small parsers are easy to understand and test, leading to maintainable, modular
    parsers.
    """
    # Simple parsers with limited scope
    hello = regex("hello", flags=re.IGNORECASE)
    target = regex("[a-z]+")

    # A slightly bigger parser which combines multiple parsers together
    parser = (hello >> whitespace >> target).sep_by(string(", "))

    assert parser.parse("Hello pal, hello world, HELLO there") == [
        "pal",
        "world",
        "there",
    ]


def test_common_functionality() -> None:
    """
    Parsers come with a set of methods for common parsing functionality like repeatedly
    matching a parser, mapping the result of a parser through a function, and various
    ways of combining parsers or transforming results.
    """
    # Any letters, followed by a colon which will not be part of the result
    key = regex(r"[a-zA-Z]+") << string(":")

    # Any text containing digits, mapped from string to int
    value = regex(r"\d+").map(int)

    # Combine the key and value, ignoring space around the key
    pair = seq(padding >> key << padding, value)

    # Match at least 1 of these key-value pairs, separated by newlines.
    # Map the resulting list of tuples to a dictionary.
    parser = pair.sep_by(string("\n"), min_count=1).map(dict)

    example = """first: 1
    second: 100
    xyz: 0"""

    assert parser.parse(example) == {"first": 1, "second": 100, "xyz": 0}


def test_type_checking() -> None:
    """
    During development, type checking reveals problems with parsers as soon as they are
    written, such as trying to map a ``str`` result into a function which expects an
    ``int``.
    """

    def double(value: int) -> int:
        return value * 2

    # This line gives a type error of ``type "str" is incompatible with type "int"``:
    # value_parser = regex(r"\d+").map(double)

    # Map the result to an int first, then type checking succeeds:
    value_parser = regex(r"\d+").map(int).map(double)

    assert value_parser.parse("4") == 8


def test_structured_data() -> None:
    """
    Create parsers which produce **structured data** like dataclasses.
    """

    @dataclass
    class Person:
        # Each field has a parser associated with it.
        name: str = take(regex(r"\w+") << whitespace)
        age: int = take(regex(r"\d+").map(int))

    # "Gather" the dataclass fields into a combined parser which returns
    # an instance of the dataclass
    person_parser = gather(Person)
    person = person_parser.parse("Bilbo 111")

    assert person == Person(name="Bilbo", age=111)
