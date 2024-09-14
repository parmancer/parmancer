"""
Stateful parsers are a way of defining a parser in a normal Python function.

This is for when more complex operations or parsing logic needs to be included for
intermediate parsing results, and regular Python code is the easiest way to do it.
This is done via `TextState.apply(parser)` which returns a `Result` object containing
the parse result, or failure information, and the resulting parser state to be passed
to the next parser.

In this kind of parser, debugging is simpler because any breakpoint inside the stateful
parser will reveal the parsed value and text state at that breakpoint, unlike
purely combined parsers where you need to step through internal `parmancer` combinator
functions to keep track of the result values and text state.
"""

from dataclasses import dataclass

import pytest

from parmancer import (
    FailureInfo,
    ParseError,
    Result,
    TextState,
    regex,
    stateful_parser,
    success,
    whitespace,
)


@dataclass
class Person:
    name: str
    age: int
    note: str


def test_stateful_parser() -> None:
    @stateful_parser
    def person_parser(s: TextState) -> Result[Person]:
        name = s.apply(regex(r"\w+") << whitespace)
        age = name.state.apply((regex(r"\d+") << whitespace).map(int))

        # Example: setting a breakpoint here, we'll see the parsed values for name and
        # age in a debugger, and `s` will contain the input text and current index

        if age.value % 2:
            # Parsing can depend on previously parsed values
            note = age.state.apply(regex(".+") >> success("Odd age"))
        else:
            note = age.state.apply(regex(".+"))

        # Finally, return a success from the state `s` - any downstream parsers will
        # pick up the remaining state from here.
        #
        # If the parser needed to change the text state, like moving the index to
        # `new_index`, it can be done like this: `return s.at(new_index).success(value)`
        return note.state.success(Person(name.value, age.value, note.value))

    assert person_parser.parse("Frodo 29 my_note") == Person("Frodo", 29, "Odd age")
    assert person_parser.parse("Frodo 28 my_note") == Person("Frodo", 28, "my_note")


def test_stateful_parser_failure() -> None:
    @stateful_parser
    def person(s: TextState) -> Result[Person]:
        name = s.apply(regex(r"\w+") << whitespace)

        age = name.state.apply((regex(r"\d+").set_name("digit") << whitespace).map(int))

        return age.state.success(Person(name.value, age.value, "default"))

    with pytest.raises(ParseError) as exception:
        person.parse("Frodo what")

    # Parsing fails on the digit regex parser
    assert exception.value.failures == (FailureInfo(index=6, message="digit"),)
