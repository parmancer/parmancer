"""
.. include:: ../README.md
"""

from parmancer.parser import (
    FailureInfo,
    ParseError,
    Parser,
    Result,
    TextState,
    any_char,
    char_from,
    end_of_text,
    forward_parser,
    from_enum,
    gather,
    gather_perm,
    look_ahead,
    one_of,
    regex,
    seq,
    span,
    stateful_parser,
    string,
    string_from,
    success,
    take,
)

__all__ = [
    "string",
    "regex",
    "whitespace",
    "padding",
    "digit",
    "digits",
    "letter",
    "string_from",
    "char_from",
    "span",
    "any_char",
    "end_of_text",
    "from_enum",
    "seq",
    "one_of",
    "success",
    "look_ahead",
    "take",
    "gather",
    "gather_perm",
    "stateful_parser",
    "forward_parser",
    "Parser",
    "Result",
    "ParseError",
    "FailureInfo",
    "TextState",
]


whitespace: Parser[str] = regex(r"\s+")
r"""1 or more spaces: `regex(r"\s+")`"""

padding: Parser[str] = regex(r"\s*")
r"""0 or more spaces: `regex(r"\s*")`"""

letter: Parser[str] = any_char.gate(lambda c: c.isalpha()).set_name("Letter")
r"""A character ``c`` for which ``c.isalpha()`` is true."""

digit: Parser[str] = regex(r"[0-9]").set_name("Digit")
"""A numeric digit."""

digits: Parser[str] = regex(r"[0-9]+").set_name("Digits")
"""Any number of numeric digits in a row."""
