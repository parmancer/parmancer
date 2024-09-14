"""
Example of parsing a subset of ISO 8601 (and RFC 3339) datetime formats.

Grammar from RFC3339

date-fullyear   = 4DIGIT
date-month      = 2DIGIT  ; 01-12
date-mday       = 2DIGIT  ; 01-28, 01-29, 01-30, 01-31 based on
                            ; month/year
time-hour       = 2DIGIT  ; 00-23
time-minute     = 2DIGIT  ; 00-59
time-second     = 2DIGIT  ; 00-58, 00-59, 00-60 based on leap second
                            ; rules
time-secfrac    = "." 1*DIGIT
time-numoffset  = ("+" / "-") time-hour ":" time-minute
time-offset     = "Z" / time-numoffset

partial-time    = time-hour ":" time-minute ":" time-second
                    [time-secfrac]
full-date       = date-fullyear "-" date-month "-" date-mday
full-time       = partial-time time-offset

date-time       = full-date "T" full-time


NOTE: Per [ABNF] and ISO8601, the "T" and "Z" characters in this
      syntax may alternatively be lower case "t" or "z" respectively.

      This date/time format may be used in some environments or contexts
      that distinguish between the upper- and lower-case letters 'A'-'Z'
      and 'a'-'z' (e.g. XML).  Specifications that use this format in
      such environments MAY further limit the date/time syntax so that
      the letters 'T' and 'Z' used in the date/time syntax must always
      be upper case.  Applications that generate this format SHOULD use
      upper case letters.

      NOTE: ISO 8601 defines date and time separated by "T".
      Applications using this syntax may choose, for the sake of
      readability, to specify a full-date and full-time separated by
      (say) a space character.

5.7. Restrictions

   The grammar element date-mday represents the day number within the
   current month.  The maximum value varies based on the month and year
   as follows:

      Month Number  Month/Year           Maximum value of date-mday
      ------------  ----------           --------------------------
      01            January              31
      02            February, normal     28
      02            February, leap year  29
      03            March                31
      04            April                30
      05            May                  31
      06            June                 30
      07            July                 31
      08            August               31
      09            September            30
      10            October              31
      11            November             30
      12            December             31

   Appendix C contains sample C code to determine if a year is a leap
   year.

   ---
      /* This returns non-zero if year is a leap year.  Must use 4 digit
      year.
    */
   int leap_year(int year)
   {
       return (year % 4 == 0 && (year % 100 != 0 || year % 400 == 0));
   }
    ---

   The grammar element time-second may have the value "60" at the end of
   months in which a leap second occurs -- to date: June (XXXX-06-
   30T23:59:60Z) or December (XXXX-12-31T23:59:60Z); see Appendix D for
   a table of leap seconds.  It is also possible for a leap second to be
   subtracted, at which times the maximum value of time-second is "58".
   At all other times the maximum value of time-second is "59".
   Further, in time zones other than "Z", the leap second point is
   shifted by the zone offset (so it happens at the same instant around
   the globe).

   Leap seconds cannot be predicted far into the future.  The
   International Earth Rotation Service publishes bulletins [IERS] that
   announce leap seconds with a few weeks' warning.  Applications should
   not generate timestamps involving inserted leap seconds until after
   the leap seconds are announced.

   Although ISO 8601 permits the hour to be "24", this profile of ISO
   8601 only allows values between "00" and "23" for the hour in order
   to reduce confusion.

"""

import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, List, Optional, Tuple

from parmancer import (
    gather,
    regex,
    seq,
    string,
    string_from,
    take,
)

two_digit = regex(r"\d{2}")
four_digit = regex(r"\d{4}")

date_fullyear = four_digit
date_month = two_digit
date_mday = two_digit
time_hour = two_digit
time_minute = two_digit
time_second = two_digit


@dataclass
class Time:
    hour: int = take(two_digit.map(int) << string(":"))
    minute: int = take(two_digit.map(int) << string(":"))
    second: int = take(two_digit.map(int))
    subsecond_fraction: Optional[Decimal] = take(
        (
            string(".") >> regex(r"\d+").map(lambda s: Decimal(s) / 10 ** len(s))
        ).optional()
    )

    def microseconds(self) -> int:
        """Whole number of microseconds (may lose information)."""
        return (
            int(self.subsecond_fraction * 1_000_000)
            if self.subsecond_fraction is not None
            else 0
        )

    def to_time(self, tzinfo: Optional[datetime.timezone] = None) -> datetime.time:
        """Potentially lossy conversion to a `datetime.time` object."""
        return datetime.time(
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microseconds(),
            tzinfo=tzinfo,
        )


@dataclass
class TimeOffset:
    sign: int = take(string("+").result(1) | string("-").result(-1))
    hour: int = take(two_digit.map(int) << string(":"))
    minute: int = take(two_digit.map(int))

    def to_timezone(self) -> datetime.timezone:
        return datetime.timezone(
            datetime.timedelta(hours=self.sign * self.hour, minutes=self.minute)
        )


time_offset = string_from("Z", "z").result(TimeOffset(1, 0, 0)) | gather(TimeOffset)


@dataclass
class Date:
    year: int = take(four_digit.map(int) << string("-"))
    month: int = take(two_digit.map(int) << string("-"))
    day: int = take(two_digit.map(int))

    def to_date(self) -> datetime.date:
        return datetime.date(year=self.year, month=self.month, day=self.day)


@dataclass
class DateTime:
    date: Date = take(gather(Date) << string_from("T", "t", " "))
    time: Time = take(gather(Time))
    offset: TimeOffset = take(time_offset)

    def to_datetime(self) -> datetime.datetime:
        """Potentially lossy conversion to a ``datetime.datetime`` object."""

        return datetime.datetime(
            self.date.year,
            self.date.month,
            self.date.day,
            self.time.hour,
            self.time.minute,
            self.time.second,
            self.time.microseconds(),
            self.offset.to_timezone(),
        )


date = gather(Date).map(Date.to_date)
time = gather(Time).map(Time.to_time)
time_with_zone = seq(
    gather(Time),
    time_offset.map(TimeOffset.to_timezone),
).unpack(Time.to_time)
full_datetime = gather(DateTime).map(DateTime.to_datetime)
parser = full_datetime | date | time_with_zone | time


def test_datetime_parsing() -> None:
    """Example datetimes are parsed into their expected Python datetime values"""
    expected_date = datetime.date(2023, 11, 11)
    expected_time = datetime.time(18, 8, 59)
    expected_time_with_zone = expected_time.replace(tzinfo=datetime.timezone.utc)
    expected_datetime = datetime.datetime(
        2023, 11, 11, 18, 8, 59, tzinfo=datetime.timezone.utc
    )

    # fmt: off
    # Cases adapted from https://ijmacd.github.io/rfc3339-iso8601
    test_cases: List[Tuple[str, Any]] = [
        ("2023-11-11", expected_date),
        ("18:08:59", expected_time),
        ("18:08:59+00:00", expected_time_with_zone),
        ("18:08:59.3+00:00", expected_time_with_zone.replace(microsecond=300000)),
        ("18:08:59.35+00:00", expected_time_with_zone.replace(microsecond=350000)),
        ("18:08:59.354+00:00", expected_time_with_zone.replace(microsecond=354000)),
        ("18:08:59.354934+00:00", expected_time_with_zone.replace(microsecond=354934)),
        ("18:08:59Z", expected_time_with_zone),
        ("18:08:59.3Z", expected_time_with_zone.replace(microsecond=300000)),
        ("18:08:59.35Z", expected_time_with_zone.replace(microsecond=350000)),
        ("18:08:59.354Z", expected_time_with_zone.replace(microsecond=354000)),
        ("18:08:59.354934Z", expected_time_with_zone.replace(microsecond=354934)),
        ("18:08:59+00:00", expected_time_with_zone),
        ("18:08:59.3+00:00", expected_time_with_zone.replace(microsecond=300000)),
        ("18:08:59.354+00:00", expected_time_with_zone.replace(microsecond=354000)),
        ("18:08:59.354934+00:00", expected_time_with_zone.replace(microsecond=354934)),
        ("18:08:59-00:00", expected_time_with_zone),
        ("18:08:59.3-00:00", expected_time_with_zone.replace(microsecond=300000)),
        ("18:08:59.354-00:00", expected_time_with_zone.replace(microsecond=354000)),
        ("18:08:59.354934-00:00", expected_time_with_zone.replace(microsecond=354934)),
        ("2023-11-11T18:08:59Z", expected_datetime),
        ("2023-11-11T18:08:59.3Z", expected_datetime.replace(microsecond=300000)),
        ("2023-11-11T18:08:59.35Z", expected_datetime.replace(microsecond=350000)),
        ("2023-11-11T18:08:59.354Z", expected_datetime.replace(microsecond=354000)),
        ("2023-11-11T18:08:59.354934Z", expected_datetime.replace(microsecond=354934)),
        ("2023-11-11t18:08:59z", expected_datetime),
        ("2023-11-11t18:08:59.354z", expected_datetime.replace(microsecond=354000)),
        ("2023-11-11T18:08:59+00:00", expected_datetime),
        ("2023-11-11T18:08:59.354+00:00", expected_datetime.replace(microsecond=354000)),
        ("2023-11-11T18:08:59.354934+00:00", expected_datetime.replace(microsecond=354934)),
        ("2023-11-11 18:08:59+00:00", expected_datetime),
        ("2023-11-11 18:08:59.3+00:00", expected_datetime.replace(microsecond=300000)),
        ("2023-11-11 18:08:59.35+00:00", expected_datetime.replace(microsecond=350000)),
        ("2023-11-11 18:08:59.354+00:00", expected_datetime.replace(microsecond=354000)),
        ("2023-11-11 18:08:59.354934+00:00", expected_datetime.replace(microsecond=354934)),
        ("2023-11-11 18:08:59Z", expected_datetime),
        ("2023-11-11 18:08:59z", expected_datetime),
        ("2023-11-11 18:08:59.3Z", expected_datetime.replace(microsecond=300000)),
        ("2023-11-11 18:08:59.35Z", expected_datetime.replace(microsecond=350000)),
        ("2023-11-11 18:08:59.354Z", expected_datetime.replace(microsecond=354000)),
        ("2023-11-11 18:08:59.354934Z", expected_datetime.replace(microsecond=354934)),
        ("2023-11-11 18:08:59.354z", expected_datetime.replace(microsecond=354000)),
        ("2023-11-11 18:08:59.354934z", expected_datetime.replace(microsecond=354934)),
        ("2023-11-11 18:08:59-00:00", expected_datetime),
        ("2023-11-11 18:08:59.354-00:00", expected_datetime.replace(microsecond=354000)),
        ("2023-11-11T18:08:59-00:00", expected_datetime),
        ("2023-11-11T18:08:59.354-00:00", expected_datetime.replace(microsecond=354000)),
        ("2023-11-12T02:53:59+08:45", datetime.datetime(2023, 11, 12, 2, 53, 59, tzinfo=datetime.timezone(datetime.timedelta(seconds=31500)))),
        ("2023-11-11T18:08:59+00:00", expected_datetime),
        ("2023-11-11T18:08:59+01:00", expected_datetime.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=1)))),
        ("2023-11-11T18:08:59-01:00", expected_datetime.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=-1)))),
        ("2023-11-11T18:08:59.354+00:00", expected_datetime.replace(microsecond=354000)),
    ]
    # fmt: on
    for case, expected in test_cases:
        assert parser.parse(case) == expected
