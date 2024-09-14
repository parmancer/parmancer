"""
# Debugging combined parsers

Defining and calling parser combinators follows these general steps:

1. Define parsers
2. Combine parsers into a larger combined parser
3. Run the combined parser on some text

This means some of the usual approaches to debugging Python won't work, because putting
a breakpoint somewhere in a parser definition will drop into step 2 above, before
any text is actually being parsed. Usually it's more useful to debug during step 3
where you can see the state of the text currently being parsed.

## Approach 1: inserting a parser breakpoint

To do this, use the `Parser.breakpoint()` method of any parser. It calls `breakpoint()`
before the parser is run, so the current parsing state and result so far can be
inspected.

## Approach 2: debugging stateful parsers

Stateful parsers have access to the input text and intermediate parsing results from
any parsers applied to the text state. Adding a breakpoint to a parser defined like
this is the same as adding a breakpoint to normal Python code - it will drop in during
the actual parsing step. For example:


```python
from parmancer import TextState, Result, digit


def demo(state: TextState) -> Result[str]:
    # Adding a breakpoint here, we could see the content of `state` and step through
    # to see the value of `result`
    result = digit.parse_result(state)
    return result
```

This has the downside of having to modify code in order to debug it, which leads to
a messy iterative process.

## Information available during debugging

`state.context_display()` shows the text being parsed at the current index.

"""

from parmancer import (
    Result,
    TextState,
    digit,
    regex,
    seq,
    stateful_parser,
    string,
)

breakpoint_demo = seq(string("abc"), regex("def").breakpoint())


@stateful_parser
def stateful_demo(state: TextState) -> Result[str]:
    # Adding a breakpoint here, we could see the content of `state` and step through
    # to see the value of `result`
    result = digit.parse_result(state)
    return result


def main() -> None:
    # Debug this file to see the two approaches to adding a breakpoint
    breakpoint_demo.parse("abcdef")
    stateful_demo.parse("1")


if __name__ == "__main__":
    main()
