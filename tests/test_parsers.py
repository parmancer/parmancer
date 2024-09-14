import enum
import re
from dataclasses import dataclass
from typing import Any, Tuple

import pytest

from parmancer import (
    digit,
    letter,
    padding,
    whitespace,
)
from parmancer.parser import (
    Choice,
    FailureInfo,
    KeepOne,
    OneOf,
    ParseError,
    Parser,
    Result,
    Sequence,
    TextState,
    any_char,
    char_from,
    from_enum,
    gather,
    look_ahead,
    one_of,
    regex,
    seq,
    stateful_parser,
    string,
    string_from,
    success,
    take,
)


def test_string() -> None:
    parser = string("x")
    assert parser.parse("x") == "x"
    with pytest.raises(ParseError):
        parser.parse("y")
    with pytest.raises(ParseError):
        parser.parse("y")
    with pytest.raises(ParseError):
        parser.parse("dog")


def test_regex_str() -> None:
    parser = regex(r"[0-9]")

    assert parser.parse("1") == "1"
    assert parser.parse("4") == "4"
    with pytest.raises(ParseError):
        parser.parse("x")


def test_regex_compiled() -> None:
    parser = regex(re.compile(r"[0-9]"))
    assert parser.parse("1") == "1"
    with pytest.raises(ParseError):
        parser.parse("x")


def test_regex_group_number() -> None:
    parser = regex(r"a([0-9])b", group=1)
    assert parser.parse("a1b") == "1"
    with pytest.raises(ParseError):
        parser.parse("x")


def test_regex_group_name() -> None:
    parser = regex(r"a(?P<name>[0-9])b", group="name")
    assert parser.parse("a1b") == "1"
    with pytest.raises(ParseError):
        parser.parse("x")


def test_regex_group_tuple() -> None:
    parser = regex(r"a([0-9])b([0-9])c", group=(1, 2))
    assert parser.parse("a1b2c") == ("1", "2")
    with pytest.raises(ParseError):
        parser.parse("x")


def test_regex_ignorecase_flag() -> None:
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


def test_regex_change_compiled_flags() -> None:
    """Multiple `re` flags can be passed to the regex parser"""
    parser = regex(re.compile("anyCASE"), flags=re.IGNORECASE)
    assert parser.parse("anycase") == "anycase"
    assert parser.parse("ANYCASE") == "ANYCASE"


def test_rshift() -> None:
    xy_parser = string("x") >> string("y")
    assert xy_parser.parse("xy") == "y"

    with pytest.raises(ParseError):
        xy_parser.parse("y")
    with pytest.raises(ParseError):
        xy_parser.parse("z")


def test_lshift() -> None:
    xy_parser = string("x") << string("y")
    assert xy_parser.parse("xy") == "x"

    with pytest.raises(ParseError):
        xy_parser.parse("y")
    with pytest.raises(ParseError):
        xy_parser.parse("z")


def test_multiple_shifts_are_flattened() -> None:
    """
    The KeepOne parser leads to flat rather than nested parsers to keep the parser
    structure simpler.
    """
    a, b, c, d, e = string("a"), string("b"), string("c"), string("d"), string("e")
    parser = a >> b >> c << d << e
    assert isinstance(parser, KeepOne)
    # Without custom KeepOne << and >> logic, this would end up with a nested structure:
    # KeepOne(
    #     left=(a,),
    #     keep=KeepOne(
    #         left=(b,), keep=KeepOne(keep=c, right=(KeepOne(keep=d, right=(e,)),))
    #     ),
    # )
    # This structure is simplified by the custom << and >> overrides in KeepOne,
    # leaving a flatter structure:
    # KeepOne(left=(a, b), keep=c, right=(d, e))
    assert parser.left == (a, b)
    assert parser.keep == c
    assert parser.right == (d, e)


def test_bind() -> None:
    piped = None

    def binder(x: str) -> Parser[str]:
        nonlocal piped
        piped = x
        return string("y")

    parser = string("x").bind(binder)

    assert parser.parse("xy") == "y"
    assert piped == "x"

    with pytest.raises(ParseError):
        parser.parse("x")


def test_map() -> None:
    parser = digit.map(int)
    assert parser.parse("7") == 7


def test_and() -> None:
    parser = digit & letter
    assert parser.parse("1A") == ("1", "A")


def test_append() -> None:
    parser = digit.pair(letter).append(letter)
    assert parser.parse("1AB") == ("1", "A", "B")


def test_combine() -> None:
    parser = digit.pair(letter).append(letter).unpack(lambda a, b, c: (c + b + a))
    assert parser.parse("1AB") == "BA1"


def test_combine_mixed_types() -> None:
    def demo(a: int, b: str, c: bool) -> Tuple[int, str, bool]:
        return (a, b, c)

    parser = digit.map(int).pair(letter).append(digit.map(bool)).unpack(demo)
    assert parser.parse("1A1") == (1, "A", True)


def test_state_parser() -> None:
    x: Result[Any] = None  # type: ignore
    y: Result[Any] = None  # type: ignore

    @stateful_parser
    def xy(s: TextState) -> Result[int]:
        nonlocal x
        nonlocal y
        x = s.apply(string("x"))
        y = x.state.apply(string("y"))
        return y.state.success(3)

    assert xy.parse("xy") == 3
    assert x.value == "x"
    assert y.value == "y"


def test_multiple_failures() -> None:
    abc = string("a") | string("b") | string("c")

    with pytest.raises(ParseError, match="''a'', ''b'', ''c''") as err:
        abc.parse("d")

    assert err.value.failures == (
        FailureInfo(index=0, message="'a'"),
        FailureInfo(index=0, message="'b'"),
        FailureInfo(index=0, message="'c'"),
    )


def test_stateful_parser_early_return() -> None:
    @stateful_parser
    def xy(s: TextState) -> Result[None]:
        _ = string("x").parse_result(s).expect()
        _ = string("y").parse_result(s).expect()
        assert False  # won't be reached in this test

    parser = xy | string("z")
    # should not finish executing xy()
    assert parser.parse("z") == "z"


def test_or() -> None:
    x_or_y = string("x") | string("y")

    assert x_or_y.parse("x") == "x"
    assert x_or_y.parse("y") == "y"


def test_or_with_then() -> None:
    parser = (string("\\") >> string("y")) | string("z")
    assert parser.parse("\\y") == "y"
    assert parser.parse("z") == "z"

    with pytest.raises(ParseError):
        parser.parse("\\z")


def test_nested_ors_are_flattened() -> None:
    first = string("a") | string("b")
    second = string("c") | string("d")
    third = first | second
    assert isinstance(first, Choice)
    assert isinstance(second, Choice)
    assert isinstance(third, Choice)
    assert third.parsers == (*first.parsers, *second.parsers)


def test_nested_ors_are_not_flattened_if_grouped() -> None:
    first = (string("a") | string("b")).set_name("Custom name")
    second = string("c") | string("d")
    third = first | second
    assert isinstance(first, Choice)
    assert isinstance(second, Choice)
    assert first.is_grouped
    assert not second.is_grouped
    assert isinstance(third, Choice)
    # `first` is kept whole rather than being flattened to its `.parsers`
    assert third.parsers == (first, *second.parsers)


def test_many() -> None:
    letters = letter.many()
    assert letters.parse("x") == ["x"]
    assert letters.parse("xyz") == ["x", "y", "z"]
    assert letters.parse("") == []

    with pytest.raises(ParseError):
        letters.parse("1")


def test_many_with_then() -> None:
    parser = string("x").many() >> string("y")
    assert parser.parse("y") == "y"
    assert parser.parse("xy") == "y"
    assert parser.parse("xxxxxy") == "y"


def test_times_zero() -> None:
    zero_letters = letter.times(0)
    assert zero_letters.parse("") == []

    with pytest.raises(ParseError):
        zero_letters.parse("x")


def test_times() -> None:
    three_letters = letter.times(3)
    assert three_letters.parse("xyz") == ["x", "y", "z"]

    with pytest.raises(ParseError):
        three_letters.parse("xy")
    with pytest.raises(ParseError):
        three_letters.parse("xyzw")


def test_times_with_then() -> None:
    then_digit = letter.times(3) >> digit
    assert then_digit.parse("xyz1") == "1"

    with pytest.raises(ParseError):
        then_digit.parse("xy1")
    with pytest.raises(ParseError):
        then_digit.parse("xyz")
    with pytest.raises(ParseError):
        then_digit.parse("xyzw")


def test_range_with_min_and_max() -> None:
    some_letters = letter.many(2, 4)

    assert some_letters.parse("xy") == ["x", "y"]
    assert some_letters.parse("xyz") == ["x", "y", "z"]
    assert some_letters.parse("xyzw") == ["x", "y", "z", "w"]

    with pytest.raises(ParseError):
        some_letters.parse("x")
    with pytest.raises(ParseError):
        some_letters.parse("xyzwv")


def test_range_with_min_and_max_and_then() -> None:
    then_digit = letter.many(2, 4) >> digit

    assert then_digit.parse("xy1") == "1"
    assert then_digit.parse("xyz1") == "1"
    assert then_digit.parse("xyzw1") == "1"

    with pytest.raises(ParseError):
        then_digit.parse("xy")
    with pytest.raises(ParseError):
        then_digit.parse("xyzw")
    with pytest.raises(ParseError):
        then_digit.parse("xyzwv1")
    with pytest.raises(ParseError):
        then_digit.parse("x1")


def test_at_most() -> None:
    ab = string("ab")
    assert ab.at_most(2).parse("") == []
    assert ab.at_most(2).parse("ab") == ["ab"]
    assert ab.at_most(2).parse("abab") == ["ab", "ab"]
    with pytest.raises(ParseError):
        ab.at_most(2).parse("ababab")


def test_at_least() -> None:
    ab = string("ab")
    assert ab.at_least(2).parse("abab") == ["ab", "ab"]
    assert ab.at_least(2).parse("ababab") == ["ab", "ab", "ab"]
    with pytest.raises(ParseError):
        ab.at_least(2).parse("ab")

    result = ab.at_least(2).parse_result(TextState.start("abababc"))
    assert result.value == ["ab", "ab", "ab"]
    assert result.state.remaining() == "c"


def test_until() -> None:
    until = string("s").until(string("x"))

    s = TextState.start("ssssx")
    result = until.parse_result(s)
    assert result.value == 4 * ["s"]
    assert result.state.remaining() == "x"

    then = (until >> string("x")).parse_result(s)
    assert then.value == "x"

    with pytest.raises(ParseError):
        until.parse("ssssy")
    with pytest.raises(ParseError):
        until.parse("xssssxy")

    negative_result = until.parse_result(TextState.start("xxx"))
    assert negative_result.value == []
    assert negative_result.state.remaining() == "xxx"

    until = regex(".").until(string("x"))
    assert until.parse_result(TextState.start("xxxx")).value == []


def test_until_with_min() -> None:
    until = string("s").until(string("x"), min_count=3)
    result_3 = until.parse_result(TextState.start("sssx"))
    assert result_3.value == 3 * ["s"]
    assert result_3.state.remaining() == "x"
    result_5 = until.parse_result(TextState.start("sssssx"))
    assert result_5.value == 5 * ["s"]
    assert result_5.state.remaining() == "x"

    with pytest.raises(ParseError):
        until.parse("ssx")


def test_until_with_max() -> None:
    # until with max
    until = string("s").until(string("x"), max_count=3)
    assert until.parse_result(TextState.start("ssx")).value == 2 * ["s"]
    assert until.parse_result(TextState.start("sssx")).value == 3 * ["s"]

    with pytest.raises(ParseError):
        until.parse("ssssx")


def test_until_with_min_max() -> None:
    until = string("s").until(string("x"), min_count=3, max_count=5)

    assert until.parse_result(TextState.start("sssx")).value == 3 * ["s"]
    assert until.parse_result(TextState.start("ssssx")).value == 4 * ["s"]
    assert until.parse_result(TextState.start("sssssx")).value == 5 * ["s"]

    with pytest.raises(ParseError) as err:
        until.parse("ssx")
    assert err.value.failures[0] == FailureInfo(
        index=2, message="'s'.until('x', min=3, max=5)"
    )

    with pytest.raises(ParseError) as err:
        until.parse("ssssssx")
    assert err.value.failures[0] == FailureInfo(
        index=5, message="'s'.until('x', min=3, max=5)"
    )


def test_optional() -> None:
    p = string("a").optional()
    assert p.parse("a") == "a"
    assert p.parse("") is None
    p = string("a").optional("b")
    assert p.parse("a") == "a"
    assert p.parse("") == "b"


def test_sep_by() -> None:
    digit_list = digit.map(int).sep_by(string(","))

    assert digit_list.parse("1,2,3,4") == [1, 2, 3, 4]
    assert digit_list.parse("9,0,4,7") == [9, 0, 4, 7]
    assert digit_list.parse("3,7") == [3, 7]
    assert digit_list.parse("8") == [8]
    assert digit_list.parse("") == []

    with pytest.raises(ParseError):
        digit_list.parse("8,")
    with pytest.raises(ParseError):
        digit_list.parse(",9")
    with pytest.raises(ParseError):
        digit_list.parse("82")
    with pytest.raises(ParseError):
        digit_list.parse("7.6")


def test_sep_by_with_min_and_max() -> None:
    digit_list = digit.map(int).sep_by(string(","), min_count=2, max_count=4)

    assert digit_list.parse("1,2,3,4") == [1, 2, 3, 4]
    assert digit_list.parse("9,0,4,7") == [9, 0, 4, 7]
    assert digit_list.parse("3,7") == [3, 7]

    with pytest.raises(ParseError):
        digit_list.parse("8")
    with pytest.raises(ParseError):
        digit_list.parse("")
    with pytest.raises(ParseError):
        digit_list.parse("8,")
    with pytest.raises(ParseError):
        digit_list.parse(",9")
    with pytest.raises(ParseError):
        digit_list.parse("82")
    with pytest.raises(ParseError):
        digit_list.parse("7.6")
    assert digit.sep_by(string(" == "), max_count=0).parse("") == []


def test_add_tuple() -> None:
    """This test code is for checking that pylance gives no type errors"""
    letter_tuple = letter.tuple()
    int_parser = regex(r"\d").map(int)
    two_int_parser = int_parser & int_parser
    barcode = letter_tuple + two_int_parser

    def my_foo(first: str, second: int, third: int) -> str:
        return first + str(third + second)

    foo_parser = barcode.unpack(my_foo)

    assert foo_parser.parse("a13") == "a4"


def test_add_too_long_tuple_uniform_types() -> None:
    """This test code is for checking that pylance gives no type errors"""
    letter_tuple = letter.tuple()
    int_parser = regex(r"\d")
    six_int_parser = (
        (int_parser & int_parser)
        .append(int_parser)
        .append(int_parser)
        .append(int_parser)
        .append(int_parser)
    )
    barcode = letter_tuple + six_int_parser

    def my_bar(first: str, *second: str) -> str:
        return first + "-".join(second)

    foo_parser = barcode.unpack(my_bar)

    assert foo_parser.parse("a123456") == "a1-2-3-4-5-6"


def test_add_too_long_tuple_different_types() -> None:
    """This test code is for checking that pylance gives no type errors"""
    int_parser = regex(r"\d").map(int)
    six_int_parser = (
        (int_parser & int_parser)
        .append(int_parser)
        .append(int_parser)
        .append(int_parser)
        .append(int_parser)
    )
    barcode = six_int_parser + six_int_parser

    def my_hash(*vars: int) -> int:
        return sum(vars)

    hash_parser = barcode.unpack(my_hash)

    assert hash_parser.parse("111111111112") == 13


def test_add_list() -> None:
    """This test code is for checking that pylance gives no type errors"""
    letters = letter.many()
    number_chars = regex(r"\d").many()
    letters_numbers = letters + number_chars

    assert letters_numbers.parse("ab12") == ["a", "b", "1", "2"]


def test_add_unaddable_types() -> None:
    """
    The type system warns us this isn't possible:

    `Operator "+" not supported for types "Parser[str]" and "Parser[int]"`
    """
    bad_parser = letter + regex(r"\d").map(int)  # type: ignore

    with pytest.raises(TypeError):
        bad_parser.parse("a1")  # type: ignore[unused-ignore]


def test_add_numerics() -> None:
    digit = regex(r"\d")
    numeric_parser = digit.map(float) + digit.map(int)

    assert numeric_parser.parse("12") == 3.0


def test_seq() -> None:
    a = regex("a")
    b = regex("b")
    num = regex(r"[\d]").map(int)

    parser = seq(a, num, b, num, a | num)

    assert parser.parse("a1b2a") == ("a", 1, "b", 2, "a")
    assert parser.parse("a1b23") == ("a", 1, "b", 2, 3)


def test_nested_sequences_are_flattened() -> None:
    first = string("a") & string("b")
    second = string("c") & string("d")
    third = first + second
    assert isinstance(first, Sequence)
    assert isinstance(second, Sequence)
    assert isinstance(third, Sequence)
    assert third.parsers == (*first.parsers, *second.parsers)


def test_nested_sequences_are_not_flattened_when_grouped() -> None:
    first = (string("a") & string("b")).set_name("Custom name")
    second = string("c") & string("d")
    third = first + second
    assert isinstance(first, Sequence)
    assert isinstance(second, Sequence)
    assert first.is_grouped
    assert not second.is_grouped
    assert isinstance(third, Sequence)
    assert third.parsers == (first, *second.parsers)


def test_add_tuples_like_seq() -> None:
    """An alternative to `seq`"""
    a = regex("a").tuple()
    b = regex("b").tuple()
    num = regex(r"\d").map(int).tuple()

    parser = a + num + b + num + (a | num)

    assert parser.parse("a1b2a") == ("a", 1, "b", 2, "a")
    assert parser.parse("a1b23") == ("a", 1, "b", 2, 3)


def test_add_custom_addable_types() -> None:
    """Adding parsers works for anything which implements __add__"""
    int_parser = regex(r"\d+").map(int) << padding

    @dataclass
    class A:
        value: int = take(int_parser)

        def __add__(self, other: int) -> "B":
            return B(self.value * 10 + other)

        __radd__ = __add__

    @dataclass
    class B:
        value: int

    a_parser = gather(A)

    # The parser type is Parser[B], inferred from the type of A + int
    parser = a_parser + int_parser
    parser_backwards = int_parser + a_parser
    assert parser.parse("1 2") == B(12)
    assert parser_backwards.parse("1 2") == B(21)


def test_char_from_str() -> None:
    ab = char_from("ab")
    assert ab.parse("a") == "a"
    assert ab.parse("b") == "b"

    with pytest.raises(ParseError, match=re.escape("[ab]")):
        ab.parse("x")


def test_string_from() -> None:
    titles = string_from("Mr", "Mr.", "Mrs", "Mrs.")
    assert titles.parse("Mr") == "Mr"
    assert titles.parse("Mr.") == "Mr."
    assert (titles + string(" Hyde")).parse("Mr. Hyde") == "Mr. Hyde"
    with pytest.raises(
        ParseError,
        match=re.escape("''Mr'', ''Mr.'', ''Mrs'', ''Mrs.''"),
    ):
        titles.parse("foo")


def test_concat_list_of_str() -> None:
    parser = string_from("a", "b").many().concat()
    assert parser.parse("aabba") == "aabba"


def test_concat_tuple() -> None:
    parser = (string("a") & string("b")).concat()
    assert parser.parse("ab") == "ab"


def test_concat_heterogeneous_addable_tuple() -> None:
    int_float_parser = success(1) & success(2.0)
    # int and float can be added, resulting in a float
    parser = int_float_parser.concat()
    assert parser.parse("") == 3.0


def test_concat_custom_heterogeneous_addable_tuple() -> None:
    """
    A tuple of different classes which can all be added is compatible with  `concat`.

    The classes all need a compatible `__add__` type signature
    """

    @dataclass
    class DemoA:
        value: float

        def __add__(self, other: "DemoA | DemoB | float") -> float:
            if isinstance(other, (DemoA, DemoB)):
                return self.value + other.value
            if isinstance(other, float):
                return self.value + other
            return NotImplemented

    @dataclass
    class DemoB:
        value: float

        __add__ = DemoA.__add__

    trip = seq(success(DemoA(1)), success(DemoB(2)), success(3.0))
    # In static type checking, this call to concat finds that all of the elements of the
    # parser can be added to produce a float even though they're different classes
    parser = trip.concat()
    assert parser.parse("") == 6.0


def test_concat_invalid_tuple() -> None:
    # Note this also fails pyright static type checking: str and int aren't addable
    parser: Parser[Any] = (string("a") & success(1)).concat()  # pyright: ignore
    with pytest.raises(TypeError):
        parser.parse("a1")  # pyright: ignore


def test_concat_list_of_tuples() -> None:
    parser = (string("a") & string("b")).many().concat()
    assert parser.parse("abab") == ("a", "b", "a", "b")


def test_concat_list_of_ints() -> None:
    """An iterable of ints is summed. Maybe counterintuitive."""
    parser = digit.map(int).many().concat()
    assert parser.parse("125") == 8


def test_concat_list_of_lists() -> None:
    """A list of lists is concatenated to a list."""
    parser = digit.many().sep_by(string("-")).concat()
    assert parser.parse("12-34-9") == ["1", "2", "3", "4", "9"]


def test_look_ahead() -> None:
    result = look_ahead(any_char).parse_result(TextState.start("abc"))
    assert result.value == "a"
    assert result.state.remaining() == "abc"

    with pytest.raises(ParseError, match="'Digit'"):
        look_ahead(digit).parse("a")


def test_any_char() -> None:
    assert any_char.parse("x") == "x"
    assert any_char.parse("\n") == "\n"
    with pytest.raises(ParseError):
        any_char.parse("")


def test_whitespace() -> None:
    assert whitespace.parse("\n") == "\n"
    assert whitespace.parse(" ") == " "
    with pytest.raises(ParseError):
        whitespace.parse("x")


def test_letter() -> None:
    assert letter.parse("a") == "a"
    with pytest.raises(ParseError):
        letter.parse("1")


def test_digit() -> None:
    assert digit.parse("2") == "2"
    with pytest.raises(ParseError):
        digit.parse("x")


def test_from_enum_string() -> None:
    class Pet(enum.Enum):
        CAT = "cat"
        DOG = "dog"

    pet = from_enum(Pet)
    assert pet.parse("cat") == Pet.CAT
    assert pet.parse("dog") == Pet.DOG
    with pytest.raises(ParseError):
        pet.parse("foo")


def test_from_enum_int() -> None:
    class Position(enum.Enum):
        FIRST = 1
        SECOND = 2

    position = from_enum(Position)
    assert position.parse("1") == Position.FIRST
    assert position.parse("2") == Position.SECOND
    with pytest.raises(ParseError):
        position.parse("foo")


class TestOneOf:
    @staticmethod
    def test_not_enough_parsers() -> None:
        """Need to define at least one parser"""
        with pytest.raises(ValueError):
            OneOf(parsers=tuple())

    @staticmethod
    def test_fail_on_no_matches() -> None:
        """None of the parsers succeeded"""
        # Arrange
        parser = one_of(string("a"), string("b"))

        # Assert raises
        with pytest.raises(ParseError, match="''a'', ''b''"):
            parser.parse("c")

    @staticmethod
    def test_success_on_single_match() -> None:
        """Succeed if exactly one parser matches"""
        # Arrange
        parser = one_of(string("a"), string("b"))

        # Assert (no error is raised)
        assert parser.parse("a") == "a"

    @staticmethod
    def test_fail_on_two_matches() -> None:
        """None of the parsers succeeded"""
        # Arrange
        parser = one_of(string("a"), regex("a"), string("b"))

        # Act and assert raises
        with pytest.raises(ParseError, match="Exactly one"):
            parser.parse("a")
