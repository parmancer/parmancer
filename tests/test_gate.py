from dataclasses import dataclass

import pytest
from parmancer import ParseError, any_char, digit, gather, regex, take, whitespace


def test_gate() -> None:
    """Gate checks a condition be used to check a condition"""
    parser = any_char.gate(lambda x: x == "a")
    # The parsed value is still the result - not the bool result of the gate
    assert parser.parse("a") == "a"
    with pytest.raises(ParseError, match="Gate condition"):
        parser.parse("b")


def test_gate_on_numeric() -> None:
    """Gate can be used to check the condition of results which are not strings"""
    parser = digit.map(int).gate(lambda x: x < 5)
    # The parsed value is still the result - not the bool result of the gate
    assert parser.parse("3") == 3
    with pytest.raises(ParseError, match="Gate condition"):
        parser.parse("6")


def test_gate_on_dataclass() -> None:
    """Gate can be used in more complex cases such as with dataclass results"""

    @dataclass
    class Antique:
        name: str = take(regex(r"\w+") << whitespace)
        value: int = take(regex(r"\d+").map(int))

    parser = (
        gather(Antique).gate(lambda x: x.value > 10).set_name("Value must be over 10")
    )

    assert parser.parse("Trident 50") == Antique("Trident", 50)
    with pytest.raises(ParseError, match="Value must be over 10"):
        parser.parse("Shoestring 2")


def test_gate_can_be_used_for_logic_flow() -> None:
    """Gate means alternative parsers can be chosen based on the value of a parser"""
    parser = any_char.times(3).set_name("Three characters").gate(
        lambda x: x == sorted(x)
    ) | regex(r"\d+").map(int)
    # The parsed value is still the result - not the bool result of the gate
    assert parser.parse("abc") == ["a", "b", "c"]
    assert parser.parse("50") == 50

    with pytest.raises(ParseError, match="Gate condition"):
        assert parser.parse("bca")
