from dataclasses import dataclass
from typing import List, Optional

from parmancer import (
    end_of_text,
    gather,
    gather_perm,
    padding,
    regex,
    seq,
    string,
    take,
    whitespace,
)


@dataclass
class Person:
    name: str = take(regex(r"\w+") << whitespace)
    age: int = take(regex(r"\d+").map(int))


def test_dataclass_parser() -> None:
    person_parser = gather(Person)
    person = person_parser.parse("Bilbo 111")
    assert person == Person(name="Bilbo", age=111)


# Comparison of similar approaches
@dataclass
class PlainPerson:
    name: str
    age: int


name_age = seq(
    regex(r"\w+") << whitespace,
    regex(r"\d+").map(int),
).unpack(Person)


# Nesting dataclass parsers


def test_device_example() -> None:
    # Example text which a sensor might produce
    sample_text = """Device: SensorA
ID: abc001
Readings (3:01 PM)
300.1, 301, 300
Readings (3:02 PM)
302, 1000, 2500
"""

    numeric = regex(r"\d+(\.\d+)?").map(float)
    any_text = regex(r"[^\n]+")
    line_break = string("\n")

    # Define parsers for the sensor readings and device information
    @dataclass
    class Reading:
        timestamp: str = take(regex(r"Readings \(([^)]+)\)", group=1) << line_break)
        values: List[float] = take(numeric.sep_by(string(", ")) << line_break)

    @dataclass
    class Device:
        name: str = take(string("Device: ") >> regex(r"[^\s]+") << line_break)
        id: str = take(string("ID: ") >> any_text << line_break)
        readings: List[Reading] = take(gather(Reading).many())

    # Gather the fields of the `Device` dataclass into a single combined parser
    # Note the `Device.readings` field parser uses the `Reading` dataclass parser
    parser = gather(Device)

    # The result of the parser is a nicely structured `Device` dataclass instance,
    # ready for use in the rest of the code with minimal boilerplate to get this far
    assert parser.parse(sample_text) == Device(
        name="SensorA",
        id="abc001",
        readings=[
            Reading(timestamp="3:01 PM", values=[300.1, 301, 300]),
            Reading(timestamp="3:02 PM", values=[302, 1000, 2500]),
        ],
    )


@dataclass
class Id:
    id: str = take(regex(r"[^\s]+") << whitespace.optional())
    from_year: Optional[int] = take(
        regex("[0-9]+").map(int).set_name("Numeric").optional() << whitespace.optional()
    )


@dataclass
class Name:
    name: str = take(regex(r"[a-zA-Z]+") << whitespace.optional())
    abbreviated: Optional[bool] = take(
        (string("T").result(True) | string("F").result(False)).optional() << padding
    )


@dataclass
class PersonDetail:
    id: Id = take(gather(Id))
    forename: Name = take(gather(Name))
    surname: Optional[Name] = take(gather(Name).optional())


def test_nested_dataclass_parser() -> None:
    out_parser = gather(PersonDetail).many()

    new_person = out_parser.parse("007 2023 Frodo T John 123 2004 Bob")

    res = [
        PersonDetail(
            id=Id(id="007", from_year=2023),
            forename=Name(name="Frodo", abbreviated=True),
            surname=Name(name="John", abbreviated=None),
        ),
        PersonDetail(
            id=Id(id="123", from_year=2004),
            forename=Name(name="Bob", abbreviated=None),
            surname=None,
        ),
    ]
    assert new_person == res


# Dataclass parsing where not all fields have a parser


@dataclass
class PersonWithRarity:
    name: str = take(regex(r"\w+") << whitespace)
    age: int = take(regex(r"\d+").map(int) << whitespace)
    note: str = take(regex(".+"))
    rare: bool = False

    def __post_init__(self) -> None:
        if self.age > 70:
            self.rare = True


def test_dataclass_with_default_value() -> None:
    parser = gather(PersonWithRarity)
    person = parser.parse("Frodo 20 whippersnapper")
    assert person == PersonWithRarity(
        name="Frodo", age=20, note="whippersnapper", rare=False
    )

    person = parser.parse("Frodo 2000 how time flies")
    assert person == PersonWithRarity(
        name="Frodo", age=2000, note="how time flies", rare=True
    )


def test_permutation_parser() -> None:
    """
    A dataclass permutation parser is useful for a set of distinct inputs where the
    order is unknown.

    Care has to be taken with `.optional()` parsers and other
    parsers which may match 0 characters, because they may match nothing and be
    consumed when they were intended to match something in a different position.
    """
    any_end = whitespace | end_of_text

    @dataclass
    class Person:
        name: str = take(regex(r"[a-zA-Z]+").set_name("name") << any_end)
        age: int = take(regex(r"\d+").map(int).set_name("integer age") << any_end)
        id: str = take(regex(r"\d{3}-\d{3}").set_name("id") << any_end)

    parser = gather_perm(Person)

    person = parser.parse("Frodo 2000 123-456")
    person_alternative = parser.parse("123-456 2000 Frodo")
    assert person == Person(name="Frodo", age=2000, id="123-456")
    assert person == person_alternative


def test_key_value_parser() -> None:
    """
    A typical example of wanting to match fields in any order is when there are
    key-value pairs with known keys so a dataclass is the right data structure,
    but the keys may appear in any order in the input text.
    """
    any_end = regex(r"[\s\n]+")

    @dataclass
    class Person:
        name: str = take(string("name: ") >> regex(r"[a-zA-Z]+") << any_end)
        age: int = take(string("age: ") >> regex(r"\d+").map(int) << any_end)
        id: str = take(string("id: ") >> regex(r"\d{3}-\d{3}") << any_end)

    parser = padding >> gather_perm(Person) << padding

    person = parser.parse(
        # These are in a different order than what's defined in the dataclass
        """
        id: 123-456
        name: Bilbo
        age: 111
        """
    )

    assert person == Person(name="Bilbo", age=111, id="123-456")
