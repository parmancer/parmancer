"""
Parsing boolean expressions, example from https://stackoverflow.com/questions/40601713/wanted-examples-of-peg-grammar-for-deeply-nested-python-boolean-expressions


Example input:
(a=1|b=1|c=1|d=1&e=2)&(f=2&g=2&h=2|i=3|j=3|k=3)

A grammar posted in the thread above:
---
expr       = multiOR !.
multiOR    = multiAND (_wsp opOR _wsp multiAND)*
multiAND   = comparison (_wsp opAND _wsp comparison)*

comparison = varOrNum _wsp opCOMP _wsp varOrNum
             / '!'? var
             / '!'? '(' multiOR ')'

varOrNum   = var / num

var        = [a-z]i [a-z0-9_]i*
num        = '-'? [0-9]+ ('.' [0-9]+)?

opOR       = '|' '|'?
opAND      = '&' '&'?
opCOMP     = [<>=] '='? / [≤≥≠] / '!='

_wsp       = [ \t]*
---

The parser below roughly follows this grammar but makes use of some additional features
of parser combinators.

For the comparison operator, instead of just matching the text for each possible
operator ("==", ">", "!=", etc. as strings), each operator is also mapped to its
related Python operator.
For example, `string(">").result(operator.gt)` will try to match the string ">", and if
it does match, the result is set as the Python greater-than operator, ready to be
directly applied to a pair of values when the boolean program is evaluated.
The string ">" is never needed again after this point in the definition.

Some parts of the grammar are defined as dataclass parsers, each of which has an
`evaluate` method which recursively evaluates any child results and then applies logic
of its own.
This means the return value of the overall parser is itself the boolean program defined
by the input text - there is no intermediate tree which needs to be visited by some
other function(s) to apply logic (although that approach is also possible).
"""

from __future__ import annotations

import operator
from dataclasses import dataclass
from functools import reduce
from typing import Callable, Dict, Iterator, Sequence, Union

from parmancer import (
    Parser,
    forward_parser,
    gather,
    padding,
    regex,
    string,
    take,
)
from typing_extensions import TypeAlias

comparison = (
    regex("==?").result(operator.eq)
    | regex("(>=|≥)").result(operator.ge)
    | string(">").result(operator.gt)
    | regex("(<=|≤)").result(operator.le)
    | string("<").result(operator.lt)
    | regex("(!=|≠)").result(operator.ne)
)

IntValue: TypeAlias = "Union[Var, Const]"
BoolValue: TypeAlias = "Union[Comparison, Or, And, Not]"


@forward_parser
def _and() -> "Iterator[Parser[And]]":
    yield gather(And)


@forward_parser
def _bool_term() -> "Iterator[Parser[BoolValue]]":
    yield bool_term


@dataclass
class Or:
    values: Sequence[BoolValue] = take(
        _and.sep_by(padding >> string("|") << padding, min_count=1)
    )

    def evaluate(self, state: Dict[str, int]) -> bool:
        return reduce(operator.or_, (x.evaluate(state) for x in self.values))


@dataclass
class Var:
    name: str = take(regex(r"[A-Za-z][A-Za-z0-9_]*"))

    def evaluate(self, state: Dict[str, int]) -> int:
        return state[self.name]


@dataclass
class Not:
    value: BoolValue = take(string("!") >> _bool_term)

    def evaluate(self, state: Dict[str, int]) -> bool:
        return not self.value.evaluate(state)


@dataclass
class Const:
    value: int = take(regex(r"\s*(-?\d+)\s*", group=1).map(int))

    def evaluate(self, state: Dict[str, int]) -> int:
        return self.value


@dataclass
class Comparison:
    """
    comparison = varOrNum _wsp opCOMP _wsp varOrNum
    / '!'? var
    / '!'? '(' multiOR ')'
    """

    left: IntValue = take(gather(Var) | gather(Const))
    operator: Callable[[int, int], bool] = take(padding >> comparison << padding)
    right: IntValue = take(gather(Var) | gather(Const))

    def evaluate(self, state: Dict[str, int]) -> bool:
        return self.operator(self.left.evaluate(state), self.right.evaluate(state))


bool_term = gather(Comparison) | gather(Not) | string("(") >> gather(Or) << string(")")


@dataclass
class And:
    values: Sequence[BoolValue] = take(
        bool_term.sep_by(padding >> string("&") << padding, min_count=1)
    )

    def evaluate(self, state: Dict[str, int]) -> bool:
        return reduce(operator.and_, (x.evaluate(state) for x in self.values))


expr = gather(Or)


def test_demo() -> None:
    # Arrange
    # A small boolean program and a set of variables to run it with
    example = "a == 0 & b > 1"
    variables = {
        "a": 0,
        "b": 0,
    }

    # Act
    program = expr.parse(example)

    # Assert
    # The parsed boolean program
    assert program == Or(
        values=[
            And(
                values=[
                    Comparison(
                        left=Var(name="a"), operator=operator.eq, right=Const(value=0)
                    ),
                    Comparison(
                        left=Var(name="b"), operator=operator.gt, right=Const(value=1)
                    ),
                ]
            )
        ]
    )
    # The program evaluates to False
    assert program.evaluate(variables) is False


def test_large_demo() -> None:
    # Arrange
    example = "a=0&(a=1|b=1|(c=1|d=1)&e!=2)&f!=1&!f=1&!(f=1)&!!!!f!=1&(f=2&g=2&h=2|i=3|j<3|k>=3)"
    variables = {
        "a": 0,
        "b": 0,
        "c": 0,
        "d": 1,
        "e": 0,
        "f": 0,
        "g": 2,
        "h": 0,
        "i": 3,
        "j": 0,
        "k": 0,
    }

    # Act
    res = expr.parse(example)

    # Assert
    # The program evaluates to True for these variables
    assert res.evaluate(variables) is True
