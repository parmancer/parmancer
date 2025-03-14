from __future__ import annotations

import enum
import operator
import re
import sys
from copy import copy
from dataclasses import Field, dataclass, field, fields
from functools import partial, reduce
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    TypeVar,
    cast,
    overload,
)

from typing_extensions import (
    Literal,
    LiteralString,
    Protocol,
    Self,
    TypeAlias,
    TypeVarTuple,
    Unpack,
)

from parmancer.text_display import LineColumn, context_window

if sys.version_info < (3, 9):
    from typing import Pattern
else:
    from re import Pattern

# Dataclass `slots` is available on Python >= 3.10
if sys.version_info >= (3, 10):
    _slots = {"slots": True}
else:
    _slots: Dict[str, bool] = {}

__all__ = [
    "Parser",
    "TextState",
    "Result",
    "ResultAsException",
    "String",
    "Regex",
    "Bind",
    "Choice",
    "DataclassPermutation",
    "DataclassProtocol",
    "DataclassSequence",
    "EndOfText",
    "EnumMember",
    "FailureInfo",
    "ForwardParser",
    "Gate",
    "KeepOne",
    "LineColumn",
    "LookAhead",
    "Map",
    "MapFailure",
    "NamedParser",
    "OneOf",
    "ParseError",
    "Range",
    "Sequence",
    "Span",
    "StatefulParser",
    "Success",
    "Until",
]


T = TypeVar("T")
T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")
T4 = TypeVar("T4")
T5 = TypeVar("T5")
T6 = TypeVar("T6")

Ts = TypeVarTuple("Ts")

T_co = TypeVar("T_co", covariant=True)

AnyLiteral = TypeVar("AnyLiteral", bound=LiteralString)

Addable = TypeVar("Addable", contravariant=True)
AddResult = TypeVar("AddResult", covariant=True)


class SupportsAdd(Protocol[Addable, AddResult]):
    def __add__(self, other: Addable, /) -> AddResult: ...


class SupportsRAdd(Protocol[Addable, AddResult]):
    def __radd__(self, other: Addable, /) -> AddResult: ...


class SupportsSelfAdd(Protocol[T]):
    def __add__(self, other: T, /) -> T: ...


@dataclass(frozen=True, eq=True)
class FailureInfo:
    """Information about a parsing failure: the text index and a message."""

    index: int
    message: str


@dataclass(frozen=True, **_slots)
class TextState:
    """
    Parsing state: the input text, the current index of parsing, failures from previous
    parser branches for error reporting.

    Note that many `TextState` objects are created during parsing and they all contain
    the original input `text`, but these are all references to the same original string
    rather than copies.
    """

    text: str
    """The full text being parsed."""
    index: int
    """Index at start of the remaining unparsed text."""
    failures: Tuple[FailureInfo, ...] = tuple()
    """Previously encountered parsing failures, used for reporting parser failures."""

    @classmethod
    def start(cls: Type[Self], text: str) -> Self:
        """Initialize TextState for the given text with the index at the start."""
        return cls(text, 0)

    def progress(
        self: Self, index: int, failures: Tuple[FailureInfo, ...] = tuple()
    ) -> Self:
        """
        Create a new state from the current state, maintaining any extra information

        Every time a new state is made from an existing state, it should pass through
        this function to keep any values other than the basic TextState fields.
        This is similar to making a shallow copy but doesn't require mutation after
        the copy is made.
        """
        return type(self)(
            self.text,
            index,
            failures,
            **{
                field.name: getattr(self, field.name)
                for field in fields(self)
                if field.name not in ("text", "index", "failures")
            },
        )

    def at(self: Self, index: int) -> Self:
        """Move `index` to the given value, returning a new state."""
        return self.progress(index, self.failures)

    def apply(
        self: Self, parser: Parser[T_co], raise_failure: bool = True
    ) -> Result[T_co]:
        """
        Apply a parser to the current state, returning the parsing `Result` which may
        be a success or failure.
        """
        result = parser.parse_result(self)
        if not result.status and raise_failure:
            raise ResultAsException(result)
        return result

    def success(self: Self, value: T) -> Result[T]:
        """Produce a success Result with the given value."""
        return Result(True, self, FailureInfo(-1, ""), value)

    def failure(self: Self, message: str) -> Result[Any]:
        """Create a failure Result with the given failure message."""
        info = FailureInfo(index=self.index, message=message)

        new_state = self.merge_failures((info,))
        return Result(
            False,
            new_state,
            info,
            None,
        )

    def merge_state_failures(self: Self, state: TextState) -> Self:
        return self.merge_failures(state.failures)

    def merge_failures(self: Self, other: Tuple[FailureInfo, ...]) -> Self:
        furthest_failure = (
            max(info.index for info in self.failures) if self.failures else -1
        )
        result_failures: Tuple[FailureInfo, ...] = self.failures
        for failure in other:
            if furthest_failure < failure.index:
                furthest_failure = failure.index
                result_failures = (failure,)
            elif furthest_failure == failure.index:
                result_failures = (*result_failures, failure)

        return self.progress(self.index, result_failures)

    def replace_failures(self: Self, failures: Tuple[FailureInfo, ...]) -> Self:
        """Replace any current failures with new failures."""
        return self.progress(self.index, failures)

    def line_col(self: Self) -> LineColumn:
        """The line and column at the current parser index in the text."""
        return LineColumn.from_index(self.text, self.index)

    def context_display(self) -> str:
        """
        Text which displays a context window around the current parser position, with
        an indicator pointing to the character at the current index.
        """
        window, cursor = context_window(self.text, self.index, width=40)
        context: List[str] = []
        for i, line in enumerate(window):
            if i == cursor.line:
                context.append(line.rstrip("\n") + "\n")
                context.append("~" * cursor.column + "^\n")
            else:
                context.append(line)
        return "".join(context)

    def remaining(self: Self) -> str:
        """All of the text remaining to be parsed, from the current index onward."""
        return self.text[self.index :]


class ParseError(ValueError):
    """A parsing error."""

    def __init__(self, failures: Tuple[FailureInfo, ...], state: TextState) -> None:
        """Create a parsing error with specific failures for a given parser state."""
        self.failures: Tuple[FailureInfo, ...] = failures
        self.state: TextState = state

    def __str__(self) -> str:
        """
        Error text to display, including information about whichever parser(s) consumed
        the most text, along with a small window of context showing where parsing
        failed.
        """
        furthest_state = self.state.at(max(failure.index for failure in self.failures))
        messages = sorted(f"'{info.message}'" for info in self.failures)

        if len(messages) == 1:
            return f"failed with {messages[0]}\nFurthest parsing position:\n{furthest_state.context_display()}"
        else:
            return f"failed with {', '.join(messages)}\nFurthest parsing position:\n{furthest_state.context_display()}"


@dataclass(**_slots)
class Result(Generic[T_co]):
    """
    A result of running a parser, including whether it failed or succeeded, the parsed
    value if it succeeded, the text state after parsing, and any failure information
    about the furthest position in the text which has been parsed so far.
    """

    status: bool
    state: TextState
    failure_info: FailureInfo
    value: T_co

    def expect(self: Self) -> Self:
        """
        Raise `ResultAsException` if parsing failed, otherwise return the result.

        This is useful in stateful parsers as a way to exit parsing part way through
        a function; the `ResultAsException` will then be caught and turned into a
        failure `Result` by the `StatefulParser`.
        """
        if not self.status:
            raise ResultAsException(self)
        return self

    def map_failure(
        self, failure_transform: Callable[[FailureInfo], FailureInfo]
    ) -> Result[T_co]:
        """
        If the result is a failure, map the failure to a new failure value by applying
        `failure_transform`.
        """
        if self.status:
            return self
        mapped_info = failure_transform(self.failure_info)
        failures = self.state.failures
        if self.failure_info in self.state.failures:
            # Need to update the failures state
            failures = tuple(
                mapped_info if info is self.failure_info else info for info in failures
            )
        return Result(
            self.status, self.state.replace_failures(failures), mapped_info, self.value
        )


class ResultAsException(RuntimeError, Generic[T_co]):
    """An exception which contains a parsing result."""

    def __init__(self, result: Result[T_co]) -> None:
        self.result: Result[T_co] = result


class Parser(Generic[T_co]):
    """
    Parser base.

    Subclasses can override the `parse_result` method to create a specific parser, see
    `String` for example.
    """

    name: str = "Parser"

    def parse(
        self: Parser[T_co], text: str, state_handler: Type[TextState] = TextState
    ) -> T_co:
        """
        Run the parser on input text, returning the parsed value or raising a
        `ParseError` on failure.

        `text` - the text to be parsed
        `state_handler` (optional) - the class to use for handling parser state
        """
        state = state_handler.start(text)
        result = (self << end_of_text).parse_result(state)
        if not result.status:
            raise ParseError(result.state.failures, result.state)
        return result.value

    def match(
        self, text: str, state_handler: Type[TextState] = TextState
    ) -> Result[T_co]:
        """
        Run the parser on input text, returning the parsed result.

        Unlike `Parser.parse`, this method does not raise an error if parsing fails, it
        returns a `Result` type wrapping the parser output or the failure state.

        `text` - the text to be parsed
        `state_handler` (optional) - the class to use for handling parser state
        """
        state = state_handler.start(text)
        return (self << end_of_text).parse_result(state)

    def parse_result(self, state: TextState) -> Result[T_co]:
        """
        Given the input text and the current parsing position (state), parse and return
        a result (success with the parsed value, or failure with failure info).

        Override this method in subclasses to create a specific parser.
        """
        return NotImplemented  # type: ignore[no-any-return]

    @overload
    def result(self: Parser[Any], value: AnyLiteral) -> Parser[AnyLiteral]: ...

    @overload
    def result(self: Parser[Any], value: T) -> Parser[T]: ...

    def result(self: Parser[Any], value: T) -> Parser[T]:
        """Replace the current result with the given ``value``."""
        return self >> Success(value)

    def __or__(self: Parser[T1], other: Parser[T2]) -> Parser[T1 | T2]:
        """Match either self or other, returning the first parser which succeeds."""
        if isinstance(self, Choice):
            self_parsers = self.parsers
        else:
            self_parsers = (self,)

        if isinstance(other, Choice):
            other_parsers = other.parsers
        else:
            other_parsers = (other,)

        return Choice((*self_parsers, *other_parsers))

    def many(
        self: Parser[T_co],
        min_count: int = 0,
        max_count: int | float = float("inf"),
    ) -> Parser[List[T_co]]:
        """Repeat the parser until it doesn't match, storing all matches in a list.
        Optionally set a minimum or maximum number of times to match.

        :param min_count: Match at least this many times
        :param max_count: Match at most this many times
        :return: A new parser which will repeatedly apply the previous parser
        """
        return Range(self, min_count=min_count, max_count=max_count)

    def times(self: Parser[T_co], count: int) -> Parser[List[T_co]]:
        """Repeat the parser a fixed number of times, storing all matches in a list.

        :param count: Number of times to apply the parser
        :return: A new parser which will repeat the previous parser ``count`` times
        """
        return self.many(min_count=count, max_count=count).with_name(f"times({count})")

    def at_most(self: Parser[T_co], count: int) -> Parser[List[T_co]]:
        """Repeat the parser at most ``count`` times.

        :param count: Maximum number of repeats
        :return: A new parser which will repeat the previous parser up to ``count`` times
        """
        return self.many(0, count).with_name(f"at_most({count})")

    def at_least(self: Parser[T_co], count: int) -> Parser[List[T_co]]:
        """Repeat the parser at least ``count`` times.

        :param count: Minimum number of repeats
        :return: A new parser which will repeat the previous parser at least ``count`` times
        """
        return self.many(min_count=count, max_count=float("inf")).with_name(
            f"at_least({count})"
        )

    def until(
        self: Parser[T_co],
        until_parser: Parser[Any],
        min_count: int = 0,
        max_count: int | float = float("inf"),
    ) -> Parser[List[T_co]]:
        """Repeatedly apply the parser until the ``until_parser`` matches, optionally
        setting a minimum or maximum number of times to repeat.

        :param until_parser: Repeats will stop when this parser matches
        :param min_count: Optional minimum number of repeats required to succeed
        :param max_count: Optional maximum number of repeats before the ``until_parser``
            must succeed
        :return: A new parser which will repeat the previous parser until ``until_parser``
        """
        return Until(self, until_parser, min_count, max_count)

    def sep_by(
        self: Parser[T_co],
        sep: Parser[Any],
        *,
        min_count: int = 0,
        max_count: int | float = float("inf"),
    ) -> Parser[List[T_co]]:
        r"""
        Alternately apply this parser and the ``sep`` parser, keeping a list of results
        from this parser.

        For example, to match a comma-separated list of values, keeping only the values
        and discarding the commas:

        ```python
        from parmancer import regex, string

        value = regex(r"\d+")
        sep = string(", ")
        parser = value.sep_by(sep)
        assert parser.parse("1, 2, 30") == ["1", "2", "30"]
        ```

        :param self: _description_
        :param sep: The parser acting as a separator
        :param min_count: Optional minimum number of repeats
        :param max_count: Optional maximum number of repeats
        :return: A new parser which will apply this parser multiple times, with ``sep``
            applied between each repeat.
        """
        return Range(
            self, separator_parser=sep, min_count=min_count, max_count=max_count
        )

    def bind(
        self: Parser[T1],
        bind_fn: Callable[[T1], Parser[T2]],
    ) -> Parser[T2]:
        """
        Bind the result of the current parser to a function which returns another
        parser.

        :param bind_fn: A function which will take the result of the current parser as
            input and return another parser which may depend on the result.
        :return: The bound parser created by ``bind_fn``
        """
        return Bind(self, bind_fn)

    def map(
        self: Parser[T1],
        map_fn: Callable[[T1], T2],
        map_name: Optional[str] = None,
    ) -> Parser[T2]:
        """Convert the current result to a new result by passing its value through
        ``map_fn``

        :param map_fn: The current parser result value will be passed through this
            function, creating a new result.
        :param map_name: A name to give to the map function
        :return: A new parser which will convert the previous parser's result to a new
            value using ``map_fn``
        """
        if map_name is None:
            map_name = "map"
            if hasattr(map_fn, "__name__"):
                map_name = map_fn.__name__

        return Map(parser=self, map_callable=map_fn, map_name=map_name)

    def map_failure(
        self, failure_transform: Callable[[FailureInfo], FailureInfo]
    ) -> Parser[T_co]:
        """Transform a failure state using a transform function, used for example to add
        additional context to a parser failure.

        :param failure_transform: A function which converts a ``FailureInfo`` into
            another ``FailureInfo``
        :return: A parser which will map its failure info using ``failure_transform``
        """
        return MapFailure(self, failure_transform)

    def unpack(
        self: Parser[Tuple[Unpack[Ts]]],
        transform_fn: Callable[[Unpack[Ts]], T2],
    ) -> Parser[T2]:
        """When the result is a tuple, it can be unpacked and passed as *args to
        ``transform_fn``, creating a new result containing the function's output.

        :param transform_fn: Function to unpack the current result tuple into as args
        :return: An updated parser which will unpack its result into ``transform_fn``
            to produce a new result
        """
        return self.bind(lambda value: Success(transform_fn(*value))).with_name(
            "unpack"
        )

    def tuple(self: Parser[T]) -> Parser[Tuple[T]]:
        """Wrap the result in a tuple of length 1."""
        return self.map(lambda value: (value,), "Wrap tuple")

    def append(
        self: Parser[Tuple[Unpack[Ts]]], other: Parser[T2]
    ) -> Parser[Tuple[Unpack[Ts], T2]]:
        """
        Append the result of another parser to the end of the current parser's result tuple

        ```python
        from parmancer import string

        initial = string("First").tuple()
        appended = initial.append(string("Second"))

        assert appended.parse("FirstSecond") == ("First", "Second")
        ```
        """
        return self.bind(
            lambda self_value: other.bind(
                lambda other_value: Success((*self_value, other_value))
            )
        )

    def list(self: Parser[T]) -> Parser[List[T]]:
        """Wrap the result in a list."""
        return self.map(lambda value: [value], map_name="Wrap list")

    # Unpack first arg
    @overload
    def __add__(
        self: Parser[Tuple[Unpack[Ts]]],
        other: Parser[Tuple[T1]],
    ) -> Parser[Tuple[Unpack[Ts], T1]]: ...

    @overload
    def __add__(
        self: Parser[Tuple[Unpack[Ts]]],
        other: Parser[Tuple[T1, T2]],
    ) -> Parser[Tuple[Unpack[Ts], T1, T2]]: ...

    @overload
    def __add__(
        self: Parser[Tuple[Unpack[Ts]]],
        other: Parser[Tuple[T1, T2, T3]],
    ) -> Parser[Tuple[Unpack[Ts], T1, T2, T3]]: ...

    @overload
    def __add__(
        self: Parser[Tuple[Unpack[Ts]]],
        other: Parser[Tuple[T1, T2, T3, T4]],
    ) -> Parser[
        Tuple[
            Unpack[Ts],
            T1,
            T2,
            T3,
            T4,
        ]
    ]: ...

    @overload
    def __add__(
        self: Parser[Tuple[Unpack[Ts]]],
        other: Parser[Tuple[T1, T2, T3, T4, T5]],
    ) -> Parser[
        Tuple[
            Unpack[Ts],
            T1,
            T2,
            T3,
            T4,
            T5,
        ]
    ]: ...

    # Cover the rest of cases which can't return a homogeneous tuple
    @overload
    def __add__(
        self: Parser[Tuple[T1, ...]], other: Parser[Tuple[T2, ...]]
    ) -> Parser[Tuple[T1 | T2, ...]]: ...

    @overload
    def __add__(
        self: Parser[Tuple[Any, ...]], other: Parser[Tuple[Any, ...]]
    ) -> Parser[Tuple[Any, ...]]: ...

    # Literal strings are not caught by the other cases
    @overload
    def __add__(self: Parser[LiteralString], other: Parser[str]) -> Parser[str]: ...

    # Mypy calls this unreachable; pyright calls it reachable
    @overload
    def __add__(  # type: ignore[overload-cannot-match]
        self: Parser[str], other: Parser[LiteralString]
    ) -> Parser[str]: ...

    # SupportsAdd compatible
    @overload
    def __add__(
        self: Parser[SupportsAdd[Addable, AddResult]], other: Parser[Addable]
    ) -> Parser[AddResult]: ...

    @overload
    def __add__(
        self: Parser[Addable], other: Parser[SupportsRAdd[Addable, AddResult]]
    ) -> Parser[AddResult]: ...

    def __add__(self: Parser[Any], other: Parser[Any]) -> Parser[Any]:
        """Run this parser followed by ``other``, and add the result values together."""
        if isinstance(self, Sequence) and isinstance(other, Sequence):
            # Merge two sequences into one
            return Sequence((*self.parsers, *other.parsers))

        return seq(self, other).map(lambda x: x[0] + x[1], "Add")

    def concat(
        self: Parser[Iterable[SupportsSelfAdd[T]]],
    ) -> Parser[T]:
        """
        Add all the elements of an iterable result together.

        For an iterable of strings, this concatenates the strings:

        ```python
        from parmancer import digits, string

        delimited = digits.sep_by(string("-"))

        assert delimited.parse("0800-12-3") == ["0800", "12", "3"]

        assert delimited.concat().parse("0800-12-3") == "0800123"
        ```
        """

        return self.map(partial(reduce, operator.add), "Concat")

    # >>
    def __rshift__(self, other: Parser[T]) -> Parser[T]:
        """Run this parser followed by ``other``, keeping only ``other``'s result."""
        return KeepOne(left=(self,), keep=other)

    def keep_right(self, other: Parser[T]) -> Parser[T]:
        """
        This parser is run, followed by the other parser, but only the result of the
        other parser is kept.

        Another way to use this is with the `>>` operator:

        ```python
        from parmancer import string

        parser = string("a") >> string("b")
        # The "a" is matched but not kept as part of the result
        assert parser.parse("ab") == "b"
        ```
        """
        return KeepOne(left=(self,), keep=other)

    # <<
    def __lshift__(self: Parser[T], other: Parser[Any]) -> Parser[T]:
        """Run this parser followed by ``other``, keeping only this parser's result."""
        return KeepOne(keep=self, right=(other,))

    def keep_left(self: Parser[T], other: Parser[Any]) -> Parser[T]:
        """
        This parser is run, followed by the other parser, but only the result of this
        parser is kept.

        Another way to use this is with the `<<` operator:

        ```python
        from parmancer import string

        parser = string("a") << string("b")
        # The "b" is matched but not kept as part of the result
        assert parser.parse("ab") == "a"
        ```
        """
        return KeepOne(keep=self, right=(other,))

    def gate(self: Parser[T], gate_function: Callable[[T], bool]) -> Parser[T]:
        """
        Fail the parser if ``gate_function`` returns False when called on the result,
        otherwise succeed without changing the result.
        """
        return Gate(self, gate_function)

    @overload
    def optional(
        self: Parser[T1], default: Literal[None] = None
    ) -> Parser[T1 | None]: ...

    @overload
    def optional(self: Parser[T1], default: AnyLiteral) -> Parser[T1 | AnyLiteral]: ...

    @overload
    def optional(self: Parser[T1], default: T2) -> Parser[T1 | T2]: ...

    def optional(
        self: Parser[T1], default: Optional[T2] = None
    ) -> Parser[T1 | Optional[T2]]:
        """
        Make the previous parser optional by returning a result with a value of
        ``default`` if the parser failed.
        """
        return Choice((self, success(default)))

    def with_name(self, name: str) -> Parser[T_co]:
        """Set the name of the parser."""
        return NamedParser(name=name, parser=self)

    def breakpoint(self) -> Parser[T_co]:
        """Insert a breakpoint before the current parser runs, for debugging."""

        @stateful_parser
        def parser(state: TextState) -> Result[T_co]:
            breakpoint()
            result = self.parse_result(state)
            return result

        return parser


class StatefulParser(Parser[T_co]):
    parser: Callable[[TextState], Result[T_co]]

    def __init__(self, parser_fn: Callable[[TextState], Result[T_co]]):
        self.parser = parser_fn

    def parse_result(self, state: TextState) -> Result[T_co]:
        try:
            return self.parser(state)
        except ResultAsException as exception:  #  type: ignore
            return exception.result  # pyright: ignore


def stateful_parser(parser: Callable[[TextState], Result[T]]) -> Parser[T]:
    return StatefulParser(parser)


@dataclass
class Success(Parser[T]):
    success_value: T

    def parse_result(self, state: TextState) -> Result[T]:
        return state.success(self.success_value)


def success(success_value: T) -> Parser[T]:
    """
    A parser which always succeeds with a result of ``success_value`` and doesn't modify
    the input state.
    """
    return Success(success_value)


@dataclass
class MapFailure(Parser[T]):
    parser: Parser[T]
    failure_transform: Callable[[FailureInfo], FailureInfo]

    def parse_result(self, state: TextState) -> Result[Any]:
        return self.parser.parse_result(state).map_failure(self.failure_transform)


@dataclass
class String(Parser[str]):
    string: str

    def __post_init__(self) -> None:
        self.name: str = repr(self.string)

    def parse_result(self, state: TextState) -> Result[str]:
        end_index = state.index + len(self.string)
        if state.text[state.index : end_index] == self.string:
            return state.at(end_index).success(self.string)

        return state.failure(self.name)


def string(string: str) -> Parser[str]:
    """A parser which matches the value of ``string`` exactly.

    For example:

    ```python
    from parmancer import string

    assert string("ab").many().parse("abab") == ["ab", "ab"]
    ```
    """
    return String(string)


@dataclass
class Span(Parser[str]):
    length: int

    def __post_init__(self) -> None:
        self.name: str = f"Span length {self.length}"

    def parse_result(self, state: TextState) -> Result[str]:
        end_index = state.index + self.length
        if end_index > len(state.text):
            return state.failure(self.name)

        return state.at(end_index).success(state.text[state.index : end_index])


def span(length: int) -> Parser[str]:
    """A parser which matches any string span of length ``length``.

    For example, to match any strings of length 3 and then check that it matches a
    condition:

    ```python
    from parmancer import span

    # Match any 3 characters where the first character equals the last character
    parser = span(3).gate(lambda s: s[0] == s[2])

    assert parser.parse("aba") == "aba"
    # A case which doesn't match:
    assert parser.match("abc").status is False
    ```
    """
    return Span(length)


any_char: Parser[str] = span(1)
"""Match any single character.

For example:

```python
from parmancer import any_char

assert any_char.parse("!") == "!"
```
"""


PatternType: TypeAlias = "str | Pattern[str]"


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: Literal[0] = 0,
) -> Parser[str]: ...


@overload
def regex(
    pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: str | int
) -> Parser[str]: ...


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: Tuple[str | int],
) -> Parser[str]: ...


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: Tuple[str | int, str | int],
) -> Parser[Tuple[str, str]]: ...


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: Tuple[str | int, str | int, str | int],
) -> Parser[Tuple[str, str, str]]: ...


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: Tuple[str | int, str | int, str | int, str | int],
) -> Parser[Tuple[str, str, str, str]]: ...


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: Tuple[str | int, str | int, str | int, str | int, str | int],
) -> Parser[Tuple[str, str, str, str, str]]: ...


def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: str
    | int
    | Tuple[str | int]
    | Tuple[str | int, str | int]
    | Tuple[str | int, str | int, str | int]
    | Tuple[str | int, str | int, str | int, str | int]
    | Tuple[str | int, str | int, str | int, str | int, str | int]
    | Tuple[str | int, ...] = 0,
) -> Parser[str | Tuple[str, ...]]:
    r"""Match a regex ``pattern``.

    The optional ``group`` specifies which regex group(s) to keep as the parser result
    using the `re.match` syntax.
    The default it is `0`, meaning the entire string matched by the regex is used as the
    result.

    Numbered and named capture groups are supported.

    When ``group`` contains a single value: ``int``; ``str``; ``tuple[int]``;
    ``tuple[str]``; then the result is a string: ``Parser[str]``.

    When ``group`` contains a tuple of 2 or more elements, the result is a tuple of
    those strings, for example a ``group`` of `(1, 2, 3)` produces
    a ``Parser[tuple[str, str, str]]``: the result is a tuple of 3 strings.

    Some examples:

    ```python
    from parmancer import regex

    assert regex(r".").parse(">") == ">"
    assert regex(r".(a)", group=1).parse("1a") == "a"
    assert regex(r".(?P<name>a)", group="name").parse("1a") == "a"
    assert regex(
        r"(?P<hours>\d\d):(?P<minutes>\d\d)", group=("hours", "minutes")
    ).parse("10:20") == ("10", "20")
    ```

    The optional ``flags`` is passed to ``re.compile``.
    """
    if isinstance(pattern, str):
        exp = re.compile(pattern, flags)
    else:
        if flags:
            # Need to recompile with the specified flags
            exp = re.compile(pattern.pattern, flags)
        else:
            exp = pattern

    return Regex(exp, flags, group)


@dataclass
class Regex(Parser[Any]):
    """
    Parse by matching a regular expression.

    For more complete type checking, create a Regex parser using the ``regex`` function.
    """

    pattern: Pattern[str]
    flags: re.RegexFlag = re.RegexFlag(0)
    group: str | int | Tuple[str | int, ...] = 0

    def __post_init__(self) -> None:
        self.name: str = self.pattern.pattern

    def parse_result(self, state: TextState) -> Result[str | Tuple[str, ...]]:
        match = self.pattern.match(state.text, state.index)
        if match:
            # match.group needs to be broken into multiple cases to make type checking to work
            if isinstance(self.group, (int, str)):
                return state.at(match.end()).success(match.group(self.group))
            return state.at(match.end()).success(match.group(*self.group))
        else:
            return state.failure(self.name)


@dataclass
class Choice(Parser[Any]):
    """Try parsers in order until one succeeds."""

    name = "Choice"
    parsers: Tuple[Parser[Any], ...]

    def __post_init__(self) -> None:
        if not self.parsers:
            raise ValueError("The Choice parser requires at least one parser")

    def parse_result(self, state: TextState) -> Result[Any]:
        for parser in self.parsers:
            result = parser.parse_result(state)
            if result.status:
                return result
            state = result.state.at(state.index)
        return result  # pyright: ignore


@dataclass
class OneOf(Parser[Any]):
    """All parsers are tried, exactly one must succeed."""

    name = "OneOf"
    parsers: Tuple[Parser[Any], ...]

    def __post_init__(self) -> None:
        if not self.parsers:
            raise ValueError("The OneOf parser requires at least one argument")

    def parse_result(self, state: TextState) -> Result[Any]:
        results: List[Result[Any]] = []
        matched: List[str] = []
        for parser in self.parsers:
            result = parser.parse_result(state)
            if result.status:
                results.append(result)
                matched.append(parser.name)

            # Keep the result state but move it to the same start index
            state = result.state.at(state.index)
        if len(results) == 0:
            return result  # pyright: ignore
        if len(results) > 1:
            return state.failure(  # pyright: ignore
                f"Exactly one of the following parsers which all matched: {matched}"
            )
        return state.at(results[0].state.index).success(results[0].value)


# fmt: off
@overload
def one_of(parser_0: Parser[T1], /) -> Parser[T1]: ...

@overload
def one_of(parser_0: Parser[T1], parser_1: Parser[T2], /) -> Parser[T1 | T2]: ...

@overload
def one_of(
    parser_0: Parser[T1], parser_1: Parser[T2], parser_2: Parser[T3], /
) -> Parser[T1 | T2 | T3]: ...

@overload
def one_of(
    parser_0: Parser[T1], parser_1: Parser[T2], parser_2: Parser[T3], parser_3: Parser[T4], /
) -> Parser[T1 | T2 | T3 | T4]: ...

@overload
def one_of(
    parser_0: Parser[T1], parser_1: Parser[T2], parser_2: Parser[T3], parser_3: Parser[T4], parser_4: Parser[T5], /
) -> Parser[T1 | T2 | T3 | T4 | T5]: ...

@overload
def one_of(
    parser_0: Parser[T1], parser_1: Parser[T2], parser_2: Parser[T3], parser_3: Parser[T4], parser_4: Parser[T5], parser_5: Parser[T6], /,
) -> Parser[T1 | T2 | T3 | T4 | T5 | T6]: ...

@overload
def one_of(parser: Parser[Any], *parsers: Parser[Any]) -> Parser[Any]: ...
# fmt: on
def one_of(parser: Parser[Any], *parsers: Parser[Any]) -> Parser[Any]:
    r"""All parsers are tried, exactly one must succeed.

    For example, this can be used to fail on ambiguous inputs by specifying that exactly
    one parser must match the input. For date formats, the date string `"01-02-03"` may
    be ambiguous in general whereas `"2001-02-03"` may be considered unambiguous:

    ```python
    from parmancer import one_of, seq, string, regex, ParseError

    two_digit = regex(r"\d{2}").map(int)
    four_digit = regex(r"\d{4}").map(int)
    sep = string("-")

    ymd = seq((four_digit | two_digit) << sep, two_digit << sep, two_digit)
    dmy = seq(two_digit << sep, two_digit << sep, four_digit | two_digit)

    # Exactly one of the formats must match: year-month-day or day-month-year
    date = one_of(ymd, dmy)

    # This unambiguous input leads to a successful parse
    assert date.parse("2001-02-03") == (2001, 2, 3)

    # This ambiguous input leads to a failure to parse
    assert date.match("01-02-03").status is False
    ```
    """
    return OneOf((parser, *parsers))


@dataclass
class Bind(Parser[T2], Generic[T1, T2]):
    name = "Bind"
    parser: Parser[T1]
    bound: Callable[[T1], Parser[T2]]

    def __post_init__(self) -> None:
        self.name = f"Bind:{self.bound.__name__}"

    def parse_result(self, state: TextState) -> Result[T2]:
        result = self.parser.parse_result(state)
        if not result.status:
            return result  # type: ignore
        next_parser = self.bound(result.value)
        next_result = next_parser.parse_result(result.state)
        if not next_result.status:
            return next_result
        # Create a new result so that `Bind` is treated as its own node
        # This is less efficient, TODO find a better way to inherit results
        return next_result.state.success(next_result.value)


@dataclass
class Map(Parser[T2], Generic[T1, T2]):
    name = "Map"
    parser: Parser[T1]
    map_callable: Callable[[T1], T2]
    map_name: str

    def parse_result(self, state: TextState) -> Result[T2]:
        result = self.parser.parse_result(state)
        if not result.status:
            return result  # type: ignore
        return result.state.success(self.map_callable(result.value))


@dataclass
class Gate(Parser[T]):
    name = "Gate condition"
    parser: Parser[T]
    gate_function: Callable[[T], bool]

    def parse_result(self, state: TextState) -> Result[T]:
        result = self.parser.parse_result(state)
        if not result.status:
            return result
        if not self.gate_function(result.value):
            return result.state.failure(self.name)
        return result


@dataclass
class Range(Parser[List[T1]]):
    parser: Parser[T1]
    separator_parser: Optional[Parser[Any]] = None
    min_count: int = 0
    max_count: int | float = float("inf")

    def __post_init__(self) -> None:
        self.name: str = (
            f"Range({self.min_count}, {self.max_count}"
            f"{(', sep=`' + self.separator_parser.name + '`') if self.separator_parser is not None else ''}) of {self.parser.name}"
        )

    def parse_result(self, state: TextState) -> Result[List[T1]]:
        start_state = state
        count = 0
        values: List[T1] = []
        while count < self.max_count:
            # Separator
            separator_success = True
            state_before_separator = state
            if self.separator_parser is not None and count > 0:
                sep_result = self.separator_parser.parse_result(state)
                if sep_result.status:
                    state = sep_result.state
                else:
                    state = state.merge_state_failures(sep_result.state)
                    separator_success = False
            # Parser
            if separator_success:
                result = self.parser.parse_result(state)
                # TODO test that failure aggregation works in this parser
                # it doesn't/didn't
                # TODO this might be fixed but idk, need more tests
                if result.status:
                    state = result.state
                    values.append(result.value)
                    count += 1
                    continue
                else:
                    state = state_before_separator.merge_state_failures(result.state)

            if count >= self.min_count:
                break
            else:
                # Failed and didn't get to min items
                return state.at(start_state.index).failure(self.name)

        return state.success(values)


@dataclass
class EndOfText(Parser[None]):
    name = "End of text"

    def parse_result(self, state: TextState) -> Result[None]:
        if state.index >= len(state.text):
            return state.success(None)

        return state.failure(self.name)


end_of_text: Parser[None] = EndOfText()
"""Match the end of the input text."""


@dataclass()
class KeepOne(Parser[T]):
    name = "KeepOne"
    keep: Parser[T]
    left: Tuple[Parser[Any], ...] = tuple()
    right: Tuple[Parser[Any], ...] = tuple()

    def parse_result(self, state: TextState) -> Result[T]:
        # Left
        for parser in self.left:
            result = parser.parse_result(state)
            if not result.status:
                return result
            state = result.state

        # Keeper
        keep_result = self.keep.parse_result(state)
        if not keep_result.status:
            return keep_result
        state = keep_result.state

        # Right
        for parser in self.right:
            result = parser.parse_result(state)
            if not result.status:
                return result
            state = result.state
        return state.success(keep_result.value)

    def __rshift__(self: Parser[Any], other: Parser[T_co]) -> Parser[T_co]:
        # Customized >> for the KeepOne parser
        if isinstance(self, KeepOne):
            left = self
        else:
            left = KeepOne(keep=self)

        if isinstance(other, KeepOne):
            right = other
        else:
            right = KeepOne(keep=other)

        # DDR mini-game
        return KeepOne(
            left=(*left.left, left.keep, *left.right, *right.left),
            keep=right.keep,
            right=right.right,
        )

    def __lshift__(self: Parser[T1], other: Parser[Any]) -> Parser[T1]:
        # Customized << for the KeepOne parser
        if isinstance(self, KeepOne):
            left = self
        else:
            left = KeepOne(keep=self)

        if isinstance(other, KeepOne):
            right = other
        else:
            right = KeepOne(keep=other)

        # DDR mini-game
        return KeepOne(
            left=left.left,
            keep=left.keep,
            right=(*left.right, *right.left, right.keep, *right.right),
        )


# fmt: off
@overload
def seq(parser_0: Parser[T1], /) -> Parser[Tuple[T1]]: ...

@overload
def seq(parser_0: Parser[T1], parser_1: Parser[T2], /) -> Parser[Tuple[T1, T2]]: ...

@overload
def seq(
    parser_0: Parser[T1], parser_1: Parser[T2], parser_2: Parser[T3], /
) -> Parser[Tuple[T1, T2, T3]]: ...

@overload
def seq(
    parser_0: Parser[T1], parser_1: Parser[T2], parser_2: Parser[T3], parser_3: Parser[T4], /
) -> Parser[Tuple[T1, T2, T3, T4]]: ...

@overload
def seq(
    parser_0: Parser[T1], parser_1: Parser[T2], parser_2: Parser[T3], parser_3: Parser[T4], parser_4: Parser[T5], /
) -> Parser[Tuple[T1, T2, T3, T4, T5]]: ...

@overload
def seq(
    parser_0: Parser[T1], parser_1: Parser[T2], parser_2: Parser[T3], parser_3: Parser[T4], parser_4: Parser[T5], parser_5: Parser[T6], /,
) -> Parser[Tuple[T1, T2, T3, T4, T5, T6]]: ...

@overload
def seq(*parsers: Parser[Any]) -> Parser[Tuple[Any, ...]]: ...
# fmt: on
def seq(*parsers: Parser[Any]) -> Parser[Tuple[Any, ...]]:
    r"""
    A sequence of parsers are applied in order, and their results are stored in a tuple.

    For example:

    ```python
    from parmancer import seq, regex

    word = regex(r"[a-zA-Z]+")
    number = regex(r"\d").map(int)

    parser = seq(word, number, word, number, word | number)

    assert parser.parse("a1b2a") == ("a", 1, "b", 2, "a")
    assert parser.parse("a1b23") == ("a", 1, "b", 2, 3)
    ```

    There are multiple related methods for combining parsers where the result is a
    tuple: adding another parser result to the end of the tuple; concatenating two
    tuple parsers together; unpacking the tuple result as args to a function, etc.

    Here is an example which includes more tuple-related methods. Note that type
    annotations are available throughout: a type checker can find the tuple type
    for each parser, and it can tell that the `unpack` method is correctly unpacking
    a `tuple[int, str, bool]` to a function which expects those types for its arguments.

    ```python
    from parmancer import digit, letter, seq, string


    def demo(score: int, letter: str, truth: bool) -> str:
        return str(score) if truth else letter


    score = digit.map(int)
    truth = string("T").result(True) | string("F").result(False)

    # This parser's result is a tuple[int, str, bool]
    params = seq(score, letter, truth)
    assert params.parse("1aT") == (1, "a", True)

    # That tuple can be unpacked as arguments for the demo function
    parser = params.unpack(demo)

    assert parser.parse("1aT") == "1"
    assert parser.parse("2bF") == "b"

    # Another parser which returns a tuple[int, int, int]
    triple_score = seq(score, score, score)

    assert triple_score.parse("123") == (1, 2, 3)
    assert triple_score.parse("900") == (9, 0, 0)

    # These tuple parsers can be concatenated in sequence by adding them
    combined = params + triple_score

    assert combined.parse("1aT234") == (1, "a", True, 2, 3, 4)
    ```
    """

    return Sequence(parsers)


@dataclass
class Sequence(Parser[Tuple[Any, ...]]):
    """
    A sequence of parsers are applied in order, and their results are stored in a tuple.

    For more complete type checking, create a Sequence parser using the ``seq`` function.
    """

    name = "sequence"
    parsers: Tuple[Parser[Any], ...]

    def parse_result(self, state: TextState) -> Result[Tuple[Any, ...]]:
        if not self.parsers:
            raise ValueError("The Sequence parser requires at least one argument")
        values: List[Any] = []
        for parser in self.parsers:
            result = parser.parse_result(state)
            if not result.status:
                return result  # pyright: ignore
            values.append(result.value)
            state = result.state
        return state.success(tuple(values))

    def append(self: Self, other: Parser[Any]) -> Parser[Any]:
        """
        Append the result of another parser to the end of the current parser's result tuple
        """
        # TODO is this needed
        return Sequence((*self.parsers, other))


@dataclass
class Until(Parser[List[T]]):
    """
    A sequence of parsers are applied in order, and their results are stored in a tuple.

    For more complete type checking, instantiate ``Until`` using the ``until`` method of
    a parser.
    """

    parser: Parser[T]
    until_parser: Parser[Any]
    min_count: int = 0
    max_count: int | float = float("inf")

    def __post_init__(self) -> None:
        self.name: str = f"{self.parser.name}.until({self.until_parser.name}, min={self.min_count}, max={self.max_count})"

    def parse_result(self, state: TextState) -> Result[List[T]]:
        values: List[T] = []
        count = 0
        while True:
            if count >= self.min_count:
                result = self.until_parser.parse_result(state)
                if result.status:
                    return state.success(values)

            if count >= self.max_count:
                # Didn't find other parser within ``max`` matches
                return state.failure(self.name)

            result = self.parser.parse_result(state)
            if result.status:
                values.append(result.value)
                state = result.state
                count += 1
            else:
                # Did not match parser at least ``min`` times
                return state.failure(self.name)


def take(
    parser: Parser[T],
    *,
    init: bool = True,
    repr: bool = True,
    hash: bool | None = None,
    compare: bool = True,
    metadata: Mapping[Any, Any] | None = None,
) -> T:
    r"""
    Assign a parser to a field of a dataclass.

    Use this in a dataclass in conjunction with ``gather`` to concisely define parsers
    which return dataclass instances.

    ```python
    from dataclasses import dataclass

    from parmancer import gather, regex, take, whitespace


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
    ```

    """
    if metadata is None:
        metadata = {}
    return cast(
        T,
        field(
            init=init,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata={**metadata, "parser": parser},
        ),
    )


class DataclassProtocol(Protocol):
    __dataclass_fields__: ClassVar[Dict[str, Field[Any]]]
    __init__: Callable[..., None]


DataclassType = TypeVar("DataclassType", bound=DataclassProtocol)


def get_parsers_from_fields(model: Type[DataclassType]) -> Dict[str, Parser[Any]]:
    parsers: Dict[str, Parser[Any]] = {}
    for dataclass_field in fields(model):
        if "parser" not in dataclass_field.metadata:
            continue
        parsers[dataclass_field.name] = dataclass_field.metadata["parser"]
    return parsers


def gather(
    model: Type[DataclassType], field_order: Optional[Iterable[str]] = None
) -> Parser[DataclassType]:
    r"""
    Gather parsers from the fields of a dataclass into a single combined parser.
    Each field parser is applied in sequence, and each value is then assigned to that
    field to create an instance of the dataclass. That dataclass is the result of the
    combined parser.

    ```python
    from dataclasses import dataclass
    from parmancer import take, string, gather, regex


    @dataclass
    class Example:
        foo: int = take(regex(r"\d+").map(int))
        bar: bool = take(string("T").result(True) | string("F").result(False))


    parser = gather(Example)
    assert parser.parse("123T") == Example(foo=123, bar=True)
    ```
    """
    field_parsers = get_parsers_from_fields(model)
    if field_order is not None:
        field_parsers = {name: field_parsers[name] for name in field_order}
    return DataclassSequence(model, field_parsers)


@dataclass
class DataclassSequence(Parser[DataclassType]):
    """Parser created by `gather`."""

    name = "Data"
    model: Type[DataclassType]
    field_parsers: Dict[str, Parser[Any]]

    def __post_init__(self) -> None:
        self.name = f"Data:{self.model.__name__}"

    def parse_result(self, state: TextState) -> Result[DataclassType]:
        parsed_fields: Dict[str, Any] = {}
        for name, parser in self.field_parsers.items():
            self.name = f"Data:{self.model.__name__}/field:{name}"
            result = parser.parse_result(state)
            if not result.status:
                return result
            state = result.state
            parsed_fields[name] = result.value

        return state.success(self.model(**parsed_fields))


def gather_perm(model: Type[DataclassType]) -> Parser[DataclassType]:
    r"""
    Parse all fields of a dataclass parser in any order.

    Example:

    ```python
    from dataclasses import dataclass
    from parmancer import take, string, gather_perm, regex


    @dataclass
    class Example:
        foo: int = take(regex(r"\d+").map(int))
        bar: bool = take(string("T").result(True) | string("F").result(False))


    parser = gather_perm(Example)
    assert parser.parse("T123") == Example(foo=123, bar=True)
    ```
    """
    return DataclassPermutation(model)


@dataclass
class DataclassPermutation(Parser[DataclassType]):
    model: Type[DataclassType]
    field_parsers: Dict[str, Parser[Any]] = field(init=False)

    def __post_init__(self) -> None:
        self.field_parsers = get_parsers_from_fields(self.model)
        self.name: str = "Dataclass permutation"

    def parse_result(self, state: TextState) -> Result[DataclassType]:
        parsed_fields: Dict[str, Any] = {}
        parsers = copy(self.field_parsers)
        result = None
        while parsers:
            for field_name, parser in tuple(parsers.items()):
                result = parser.parse_result(state)
                if not result.status:
                    # May pass later in the permutation so don't return yet
                    continue

                state = result.state
                parsed_fields[field_name] = result.value
                parsers.pop(field_name)
                break
            else:
                # No parsers matched
                if result is None:
                    raise ValueError(
                        "Dataclass parser must contain at least one parser"
                    )
                return result

        return state.success(self.model(**parsed_fields))


E = TypeVar("E", bound=enum.Enum)


@dataclass
class EnumMember(Parser[E]):
    enum: Type[E]
    item_parser: Parser[E] = field(init=False)

    def __post_init__(self) -> None:
        items = sorted(
            (enum_member for enum_member in self.enum),
            key=lambda e: len(str(e.value)),
            reverse=True,
        )
        self.item_parser = reduce(
            operator.or_,
            [string(str(item.value)).result(item) for item in items],
        )

    def parse_result(self, state: TextState) -> Result[E]:
        return self.item_parser.parse_result(state)


def from_enum(enum: Type[E]) -> Parser[E]:
    """Match any value from an enum, producing the enum value as a result.

    For example:

    ```python
    import enum
    from parmancer import from_enum


    class Pet(enum.Enum):
        CAT = "cat"
        DOG = "dog"


    pet = from_enum(Pet)
    assert pet.parse("cat") == Pet.CAT
    assert pet.parse("dog") == Pet.DOG
    # This case doesn't match:
    assert pet.match("foo").status is False
    ```
    """
    return EnumMember(enum)


@dataclass
class LookAhead(Parser[T]):
    parser: Parser[T]

    def parse_result(self, state: TextState) -> Result[T]:
        result = self.parser.parse_result(state)
        if not result.status:
            return result
        # Return the result without moving the state index forward
        return state.success(result.value)


def look_ahead(parser: Parser[T]) -> Parser[T]:
    """
    Check whether a parser matches the next part of the input without changing the state
    of the parser: no input is consumed and no result is kept.
    """
    return LookAhead(parser)


def string_from(*strings: str) -> Parser[str]:
    """Any string from a given collection of strings.

    ```python
    from parmancer import string_from

    parser = string_from("cat", "dog")

    assert parser.parse("cat") == "cat"
    ```
    """
    return reduce(
        operator.or_,
        # Sort longest first, so that overlapping options work correctly
        (string(s) for s in sorted(strings, key=len, reverse=True)),
    )


def char_from(string: str) -> Parser[str]:
    """Any character contained in ``string``.

    For example:

    ```python
    from parmancer import char_from

    assert char_from("abc").parse("c") == "c"
    assert char_from("abc").match("d").status is False
    ```
    """
    return any_char.gate(lambda c: c in string).with_name(f"[{string}]")


@dataclass
class ForwardParser(Parser[T]):
    """A forward-defined parser."""

    parser_iterator: Callable[[], Iterator[Parser[T]]]

    def parse_result(self, state: TextState) -> Result[T]:
        parser = self.get_parser()
        result = parser.parse_result(state)
        return result

    def get_parser(self) -> Parser[T]:
        return next(self.parser_iterator())


def forward_parser(parser_iterator: Callable[[], Iterator[Parser[T]]]) -> Parser[T]:
    """Define a parser which refers to another parser which hasn't been defined yet

    Wrap a generator which yields the parser to refer to.
    This makes recursive parser definitions possible, for example:

    ```python
    from parmancer import forward_parser, string, Parser
    from typing import Iterator


    @forward_parser
    def _parser() -> Iterator[Parser[str]]:
        yield parser


    # `parser` refers to itself recursively via `_parser`.
    parser = string("a") | string("(") >> _parser << string(")")

    assert parser.parse("(a)") == "a"
    assert parser.parse("(((a)))") == "a"
    ```

    """
    return ForwardParser(parser_iterator=parser_iterator)


@dataclass
class NamedParser(Parser[T]):
    """A forward-defined parser."""

    parser: Parser[T]
    name: str

    def parse_result(self, state: TextState) -> Result[T]:
        return self.parser.parse_result(state).map_failure(
            lambda f: FailureInfo(f.index, self.name)
        )
