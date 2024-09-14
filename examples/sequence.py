"""
The sequence parser combinator `seq` combines multiple parsers in sequence.
"""

from dataclasses import dataclass

from parmancer import regex, seq, string, whitespace


@dataclass
class Person:
    name: str
    age: int
    note: str


person_arg_sequence = seq(
    regex(r"\w+"),
    whitespace >> regex(r"\d+").map(int),
    whitespace >> regex(r".+"),
)
person_parser = person_arg_sequence.unpack(Person)


def test_seq() -> None:
    person = person_parser.parse("Frodo 1000 pretty old")
    assert person == Person(name="Frodo", age=1000, note="pretty old")


# Combining seq parsers while staying in the realm of sequences

starter = seq(regex(r"> (\w+):", group=1), regex(r"\d+").map(int))


def test_seq_append_element() -> None:
    new_parser = starter.append(string("+").result(True) | string("-").result(False))

    assert new_parser.parse("> start:10+") == ("start", 10, True)


def test_add_sequences() -> None:
    first = seq(string("a"), string("1").map(int))
    second = seq(string("b"), string("2").result(True))

    parser = first + second
    assert parser.parse("a1b2") == ("a", 1, "b", True)

    # Clarifying example: adding parsers which return numbers also works
    numeric = regex(r"\d+").map(int)
    a = numeric << string(" ")
    b = numeric
    numeric_parser = a + b
    assert numeric_parser.parse("3 4") == 7
