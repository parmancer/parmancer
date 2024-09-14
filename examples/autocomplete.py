"""
This example shows a parser which can be used for producing auto-complete suggestions.

A few parsers such as `string_completion` are defined, and when used with the `completions`
function, auto-completions can be generated for any input string which matches some prefix
of the parser.

See the tests at the end of this module for examples of defining a parser for completions.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass
from enum import Enum
from functools import partial, reduce
from itertools import accumulate
from typing import Any, Iterator, List, Tuple, Type, Union

from typing_extensions import TypeVar

from parmancer import (
    FailureInfo,
    ParseError,
    Parser,
    Result,
    TextState,
    forward_parser,
    seq,
    whitespace,
)


def map_autocomplete_info(
    info: FailureInfo, option: str, completion: str
) -> FailureInfo:
    return AutocompleteInfo(index=info.index, message=option, completions=(completion,))


@dataclass
class StringCompletion(Parser[str]):
    """A parser which contains autocomplete information in its failure states."""

    string: str

    def __post_init__(self) -> None:
        self.name = repr(self.string)

    def parse_result(self, state: TextState) -> Result[str]:
        string_length = len(self.string)
        text = state.text[state.index : state.index + string_length]

        *_, prefix = [
            pre for pre in accumulate(self.string, initial="") if text.startswith(pre)
        ]
        if prefix == self.string:
            return state.at(state.index + string_length).success(self.string)
        return (
            state.at(state.index + len(prefix))
            .failure(f"Only part of the string matched: '{prefix}'")
            .map_failure(
                partial(
                    map_autocomplete_info,
                    option=self.string,
                    completion=self.string[len(prefix) :],
                )
            )
        )


def string_completion(string: str) -> Parser[str]:
    """Create an autocomplete parser for the input ``string``."""
    return StringCompletion(string)


def string_completion_from(*strings: str) -> Parser[str]:
    """Match one of the given strings, with information about how much of the prefix
    matched in the case of failure."""
    sorted_strings = tuple(sorted(strings, key=len, reverse=True))
    return reduce(
        operator.or_,
        [string_completion(option) for option in sorted_strings],
    )


@dataclass(frozen=True, eq=True)
class AutocompleteInfo(FailureInfo):
    """Store information about the available completions in a Parser failure state."""

    completions: Tuple[str, ...]


E = TypeVar("E", bound=Enum)


def enum_completion(enum: Type[E]) -> Parser[E]:
    """Autocompletion parser from enum values."""
    items = sorted(
        (enum_member for enum_member in enum),
        key=lambda e: len(str(e.value)),
        reverse=True,
    )
    return reduce(
        operator.or_,
        [string_completion(str(item.value)).result(item) for item in items],
    )


def completions(parser: Parser[Any], text: str) -> List[str]:
    try:
        parser.parse(text)
        return []
    except ParseError as exception:
        expected = exception.failures
        continuations = reduce(
            operator.add,
            [
                [*(option.completions if isinstance(option, AutocompleteInfo) else [])]
                for option in expected
            ],
        )
        # Deduplicate
        return list(dict.fromkeys(continuations))


def test_basic_completions() -> None:
    """
    `completions` returns a list of strings which could make the current parser match
    if it failed.
    """
    # Arrange
    parser = string_completion_from(
        "sim",
        "simpson",
        "sid",
    ) << string_completion(".")

    assert completions(parser, "si") == ["mpson", "m", "d"]
    assert completions(parser, "sim") == ["pson", "."]
    assert completions(parser, "sim.") == []
    assert completions(parser, "simps") == ["on"]
    assert completions(parser, "simpson") == ["."]
    assert completions(parser, "simpson.") == []


# The types mirror the definitions of the parsers below
# It's possible to fall back to an `Any` type, e.g. `QueryType = Any` if this level
# of type information is not needed.
SingleQueryType = Union[Tuple[str, str], str]
DoubleQueryType = Tuple[SingleQueryType, str, "QueryType"]
QueryType = Union[DoubleQueryType, SingleQueryType]


def test_query_builder_autocomplete() -> None:
    """Create a query language which parses strings like 'a and b', then use it
    in an autocomplete parser.
    """

    # Arrange
    @forward_parser
    def _query() -> Iterator[Parser[QueryType]]:
        yield query

    class BinaryOp(str, Enum):
        """An enumeration of binary operators."""

        AND = "and"
        OR = "or"
        XOR = "xor"

    binary_op = enum_completion(BinaryOp) << whitespace

    class UnaryOp(str, Enum):
        """An enumeration of unary operators."""

        NOT = "not"

    unary_op = enum_completion(UnaryOp) << whitespace

    # Could come from a dynamic source like a database
    variable_names = ["mo", "moon", "marker"]
    variable = string_completion_from(*variable_names) << whitespace

    single = seq(unary_op, variable) | variable
    double = seq(single, binary_op, _query)

    query = double | single

    # Act
    # autocomplete "not"
    assert completions(query, "mo and no") == ["t"]
    # autocomplete "and"
    assert completions(query, "marker a") == ["nd"]
    # autocomplete known variable names
    assert completions(query, "marker and m") == ["arker", "oon", "o"]
