"""
The regex parser wraps ``re`` in a parser combinator.

By default, the result of the parser is the entire match (group 0) as a string, but
other group(s) can be specified, some examples with the resulting parser type:

- ``regex(r"abc")``: ``Parser[str]``
- ``regex(r"ab(c)", group=1)``: ``Parser[str]``
- ``regex(r"ab(?P<target>c)", group="target")``: ``Parser[str]``

A tuple of groups will produce a tuple of strings as a result:

- ``regex(r"a(b)(c)", group=(1, 2))``: ``Parser[Tuple[str, str]]``
- ``regex(r"a(?P<one>b)(?P<two>c)", group=("one", "two"))``: ``Parser[Tuple[str, str]]``

``re`` flags can be passed, for example ``regex("anyCASE", flags=re.IGNORECASE)``.

See detailed examples below.
"""

import re
from dataclasses import dataclass
from typing import Tuple

from parmancer import digits, gather, regex, seq, string, take


def test_regex() -> None:
    """By default the entire match becomes the result."""
    default = regex(r"abc")
    assert default.parse("abc") == "abc"


def test_int_group() -> None:
    """When the group is an int, the match from that group becomes the result."""
    int_group = regex(r"ab(c)", group=1)
    assert int_group.parse("abc") == "c"


def test_named_group() -> None:
    """
    When the group is a string, it refers to a named capture group and puts that
    group in the result.
    """
    named_group = regex(r"ab(?P<target>c)", group="target")
    assert named_group.parse("abc") == "c"


def test_tuple_int_groups() -> None:
    """
    When the group is a tuple of ints, the result is a tuple of the matched capture
    groups.
    """
    tuple_int_groups = regex(r"a(b)(c)", group=(1, 2))
    assert tuple_int_groups.parse("abc") == ("b", "c")


def test_singleton_tuple_group() -> None:
    """
    When the group is a tuple of a single int, the `regex` parser has the same logic as
    Python's `re` module: The result type is `str` instead of `Tuple[str]`.
    """
    tuple_int_singleton = regex(r"a(b)", group=(1,))
    assert tuple_int_singleton.parse("ab") == "b"


def test_tuple_named_groups() -> None:
    """
    When the group is a tuple of strings, the result is a tuple of the matched named
    capture groups.
    """
    tuple_int_groups = regex(r"a(?P<first>b)(?P<second>c)", group=("first", "second"))
    assert tuple_int_groups.parse("abc") == ("b", "c")


def test_mixed_named_int_groups() -> None:
    """Combinations of int groups and named capture groups can be used."""
    mixed_groups = regex(r"a(?P<first>b)(?P<second>c)", group=("first", 2))
    assert mixed_groups.parse("abc") == ("b", "c")


def test_unpack_groups_with_lambda() -> None:
    """The tuple result of a `regex` parser can be used in combination with `unpack`."""
    parser = regex(r"(\d+) \+ (\d+) - (\d+)", group=(1, 2, 3))

    mapped_parser = parser.unpack(lambda a, b, c: int(a) + int(b) - int(c))

    assert mapped_parser.parse("4 + 3 - 2") == 5


def test_unpack_groups_with_functions() -> None:
    """Unpack can be used with named functions."""
    parser = regex(
        r"Hello (?P<name>\w+): (?P<first>\d+) \+ (?P<second>\d+)",
        group=("name", "first", "second"),
    )

    def sum_greet(name: str, first: str, second: str) -> Tuple[str, int]:
        return (name, int(first) + int(second))

    mapped_parser = parser.unpack(sum_greet)

    assert mapped_parser.parse("Hello World: 10 + 14") == ("World", 24)


def test_regex_parsers_in_dataclass() -> None:
    """Regex parsers can be used with dataclass field parsers."""
    digits = regex(r"\d+")

    @dataclass
    class Sum:
        id: str = take(digits << string(": "))
        first: int = take(digits.map(int) << string(" + "))
        second: int = take(digits.map(int))

    parser = gather(Sum)
    mapped_parser = parser.map(lambda res: {res.id: res.first + res.second})
    assert mapped_parser.parse("123: 3 + 4") == {"123": 7}


def test_regex_ignorecase_flag() -> None:
    """Regex flags are passed through to the Python `re` module."""
    parser = regex("anyCASE", flags=re.IGNORECASE)
    assert parser.parse("anycase") == "anycase"
    assert parser.parse("ANYCASE") == "ANYCASE"


def test_regex_multiple_flags() -> None:
    """Multiple `re` flags can be passed to the regex parser"""
    parser = regex(
        r"""[a-z] +  # any letter
        ,    # a separator
        \d *  # any digits""",
        flags=re.IGNORECASE | re.VERBOSE,
    )
    assert parser.parse("a,12") == "a,12"
    assert parser.parse("A,12") == "A,12"


def test_example_sum() -> None:
    """
    A parser can be made as a combination of multiple parsers and combinators
    including `regex` to build up more complete parsers.
    """
    # A parser which extracts text from a greeting
    greeting = regex(r"Hello (\w+)! ", group=1)

    # A parser which extracts any number of integers separated by `+` and sums them
    adder = digits.map(int).sep_by(string(" + ")).map(sum)

    # The `greeting` and `adder` parsers combined in sequence
    parser = seq(greeting, adder)

    # The result is a tuple containing the `greeting` result followed by the `adder` result
    # Type checkers can identify the type of `result` as `tuple[str, int]`
    result = parser.parse("Hello World! 1 + 9 + 14")
    assert result == ("World", 24)
