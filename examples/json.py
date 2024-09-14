"""
A parser for JSON.

It's not recommended to use this parser over JSON-specific packages like Python's
built-in `json` module.
This example shows some features of Parmancer for the familiar problem of parsing JSON.
"""

from pathlib import Path
from typing import Any, Dict, Iterator, List, Union

from parmancer import Parser, forward_parser, regex, string

whitespace = regex(r"\s*").set_name("whitespace")

true = string("true").result(True)
false = string("false").result(False)
null = string("null").result(None)
number = (
    regex(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?")
    .map(float, "float")
    .set_name("number")
)

unescaped_string = regex(r'([^"\\]|\\([/"bfnrt]|u[0-9a-fA-F]{4}))*').map(
    lambda s: s.encode().decode("unicode-escape"),
    map_name="unescape unicode",
)

quoted_string = (string('"') >> unescaped_string << string('"')).set_name("string")

# Type which matches the parser return value
JSON = Union[Dict[str, "JSON"], List["JSON"], str, float, bool, None]


@forward_parser
def _json_value() -> Iterator[Parser[JSON]]:
    yield json_value


def empty_dict(_: Any) -> Dict[Any, Any]:
    return {}


object_pair = (whitespace >> quoted_string << whitespace << string(":")) & _json_value
json_object = (
    (string("{") >> object_pair.sep_by(string(",")) << whitespace << string("}"))
    .map(dict)
    .set_name("object")
)
array = (
    string("[") >> _json_value.sep_by(string(",")) << whitespace << string("]")
).set_name("array")

json_value = (
    whitespace
    >> (quoted_string | number | json_object | array | true | false | null)
    << whitespace
).set_name("value")


def test_json() -> None:
    result = json_value.parse(
        r"""
    {
        "a": "b",
        "c": {"d": 1.2},
        "e": [true, false],
        "f": "\n"
    }
    """
    )

    assert result == {"a": "b", "c": {"d": 1.2}, "e": [True, False], "f": "\n"}


def test_large_json() -> None:
    data = Path(__file__).parent.joinpath("json_data.json").read_text()
    result = json_value.parse(data)
    print(result)
