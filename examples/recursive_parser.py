from typing import Iterator, List, Tuple, Union

from parmancer import Parser, forward_parser, regex, string

RT = Union[int, List["RT"]]


def test_recursive_parser() -> None:
    """
    A recursive parser can be defined by using @forward_parser.

    The type of the parser has to be explicitly declared with a type alias which
    is also recursively defined using a forward-declaration.

    This works because the forward_parser generator can refer the target parser before
    the target parser is defined. Then, when defining the parser, it can use `_parser`
    to indirectly refer to itself, creating a recursive parser.
    """
    digits = regex("[0-9]+").map(int)

    @forward_parser
    def _parser() -> Iterator[Parser[RT]]:
        yield parser

    # The explicit type annotation of `Parser[RT]` could be omitted
    parser: Parser[RT] = digits | string("(") >> (
        _parser.sep_by(string(" ")) << string(")")
    )

    result = parser.parse("(0 1 (2 3 (4 5 6)))")

    assert result == [0, 1, [2, 3, [4, 5, 6]]]


def test_minimal_recursive_parser() -> None:
    """A minimal recursive parser as an example."""

    @forward_parser
    def _parser() -> Iterator[Parser[str]]:
        yield parser

    # ``parser`` refers to itself recursively via ``_parser``.
    parser = string("a") | string("(") >> _parser << string(")")

    assert parser.parse("(a)") == "a"
    assert parser.parse("(((a)))") == "a"


RT2 = Union[int, Tuple[str, "RT2"]]


def test_indirect_recursive_parser() -> None:
    """
    Multiple forward-declared parsers can all be used together. A can refer to B which
    refers to C which refers back to A, or any other recursive relationship.
    """
    digits = regex("[0-9]+").map(int)
    letters = regex("[a-z]+")

    @forward_parser
    def _third() -> Iterator[Parser[RT2]]:
        yield third

    @forward_parser
    def _second() -> Iterator[Parser[RT2]]:
        yield second

    # Note this example is contrived, it could be simplified into fewer parsers.
    first = string("(") >> _second << string(")")
    second = digits | letters & _third
    third = string(">") >> first

    result = third.parse(">(first>(second>(3)))")

    assert result == ("first", ("second", 3))
