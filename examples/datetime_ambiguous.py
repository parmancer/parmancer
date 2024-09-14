"""
Human-readable date formats are usually ambiguous and not worth spending time parsing.
The upstream sources should be changed to output ISO 8601 (or RFC 3339) compliant
strings, or some other machine readable format.

For example, `dd/mm/yy` and `mm/dd/yy` are ambiguous in most cases without additional
out-of-band information. These formats should never be used in any situation.

This example shows a way to resurrect information from these corrupted formats in a way
which succeeds when they are unambiguous and fails when they are ambiguous.
"""

import datetime
from dataclasses import dataclass

import pytest
from parmancer import (
    ParseError,
    end_of_text,
    gather,
    one_of,
    regex,
    string,
    take,
)

two_digit = regex(r"\d{2}").map(int)
four_digit = regex(r"\d{4}").map(int)

date_fullyear = four_digit
date_shortyear = two_digit
date_month = two_digit
date_mday = two_digit


@dataclass
class Date:
    year: int = take((four_digit | two_digit).map(int) << string("/").optional())
    month: int = take(two_digit.map(int) << string("/").optional())
    day: int = take(two_digit.map(int) << string("/").optional())

    def to_date(self) -> datetime.date:
        return datetime.date(year=self.year, month=self.month, day=self.day)


def valid_date(date: Date) -> bool:
    try:
        datetime.date(year=date.year, month=date.month, day=date.day)
        return True
    except ValueError:
        return False


ymd = (gather(Date) << end_of_text).gate(valid_date)
dmy = (gather(Date, field_order=("day", "month", "year")) << end_of_text).gate(
    valid_date
)
mdy = (gather(Date, field_order=("month", "day", "year")) << end_of_text).gate(
    valid_date
)

# `one_of` only succeeds if exactly one of its parsers match
# This is how ambiguity leads to a failure: if 2 or more formats match, it will fail
date_parser = one_of(ymd, dmy, mdy)


def test_disambiguation() -> None:
    """
    These dates are unambiguous because `24` can only be the day.
    """
    date_cases = ["24/02/2023", "02/24/2023", "2023/02/24"]
    for date_case in date_cases:
        assert date_parser.parse(date_case) == Date(2023, 2, 24)


def test_ambiguous() -> None:
    """
    These dates are ambiguous because either `12` or `02` could be the month.
    """
    date_cases = ["12/02/2023", "02/12/2023"]
    for date_case in date_cases:
        with pytest.raises(ParseError):
            date_parser.parse(date_case)


def test_self_contained_example() -> None:
    """A self-contained example for documentation"""
    from parmancer import one_of, seq, string

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
    try:
        date.parse("01-02-03")
        parsed = True
    except ParseError:
        parsed = False
    assert parsed is False
