"""
Debug mode functionality for parmancer parsers.

This module provides enhanced error reporting for parser failures by capturing
and displaying detailed information about the parser state, including:
- The parse tree showing which parsers have run and their results
- Successful parsers display their results with "= value" format
- Failed parsers are marked with "X (failed)"

Additional information is kept at the cost of performance, so it should only be
used during development and not in production code.

Example:
    >>> from parmancer import string, regex, seq, ParseError
    >>> parser = seq(string("Hello "), regex(r"\\d+"))
    >>> try:
    ...     parser.parse("Hello world", debug=True)
    ... except ParseError as e:
    ...     print("Debug output shows parse tree:")
    ...     # Output includes parse tree showing 'Hello ' succeeded, \\d+ failed
    Debug output shows parse tree:

The debug output helps identify exactly where parsing failed and what was expected.
"""

from __future__ import annotations

import inspect
import operator
from dataclasses import dataclass, field
from functools import reduce
from typing import Any, List, Tuple

from typing_extensions import Self

from parmancer.parser import FailureInfo, TextState


class _Missing:
    pass


Missing = _Missing()


class _Failure:
    pass


Failure = _Failure()


@dataclass
class Node:
    """Represent a node of the parse tree: a parser name, its children, and a result if one has been parsed."""

    name: str
    children: List[Node]
    result: Any = Missing

    def become(self, other: Node) -> None:
        self.result = other.result

    @staticmethod
    def default() -> Node:
        return Node("Parser", [])


def append_tree(
    tree: Node,
    path: Tuple[str, ...],
    leaf: Node,
    prune_children_of_results: bool = False,
) -> None:
    """
    Match the path down the right-hand elements of the tree, either finding existing
    nodes or creating a new branch from the point where the nodes no longer overlap
    """
    node = tree
    parent = node
    assert len(path) > 0, "Tree append logic depends on path depth > 0"
    for part in path:
        child = node.children[-1] if node.children else None
        if child is None or child.name != part or child.result is not Missing:
            # Have to create the child node
            child = Node(part, [])
            node.children.append(child)
        parent = node
        node = child
    if parent.name.startswith("field:"):
        # Hack to make dataclass fields get their result
        parent.result = leaf.result
    node.become(leaf)

    if prune_children_of_results:
        node.children = []


def display_tree_order_by_entry(tree: Node, indent_width: int = 1) -> str:
    """
    Display a tree, where the order top-to-bottom is determined by
    when the node was first entered.

    Here is an example of this ordering, the parsers are listed in order of when
    they entered the parse tree.
    `Bind:map_result` is the most recent parser to have returned a result, but it
    remains in the position where it first entered the parse tree, above its children.

    ```
    └──Left
       └──Bind:map_result: 0
          ├──\\d+: '3'
          └──Map:int: 3
    ```

    For comparison, here is ordering by return value: the latest parser to have returned
    a result is shown at the bottom and its children are above it.

    ```
    └──Left
       │  ┌──\\d+: '0'
       │  ├──Map:int: 0
       └──Bind:map_result: 0
    ```
    """

    def _display(tree: Node, output: list[str], indent: str = "") -> None:
        if tree.result is Failure:
            result_display = " X (failed)"
        elif tree.result is Missing:
            result_display = ""
        else:
            result_display = f" = {repr(tree.result)}"
        output.append(tree.name + result_display + "\n")
        if len(tree.children) == 0:
            return
        for child in tree.children[:-1]:
            output.append(indent + "├" + "─" * indent_width)
            _display(child, output, indent + "│" + " " * indent_width)
        if tree.children:
            child = tree.children[-1]
            output.append(indent + "└" + "─" * indent_width)
            _display(child, output, indent + " " * (indent_width + 1))

    output: list[str] = []
    _display(tree, output)
    return "".join(output).rstrip()


@dataclass
class ParseStack:
    path: Tuple[str, ...]

    @staticmethod
    def get_from_stack() -> ParseStack:
        stack = inspect.stack()
        try:
            parse_result_frames = [
                element.frame.f_locals["self"].name.split("-->")
                for element in stack
                if element.function == "parse_result"
                and "self" in element.frame.f_locals
                and hasattr(element.frame.f_locals["self"], "name")
            ]

            if parse_result_frames:
                context = reduce(operator.add, list(reversed(parse_result_frames)))
                return ParseStack(context)
            else:
                # No parse_result frames found, return empty path
                return ParseStack(tuple())
        finally:
            del stack

    def __str__(self: Self) -> str:
        return "/".join(self.path)


def format_debug_info(state: Any, tree: Node) -> str:
    """
    Format debug information for display when a parser fails.
    Returns a formatted string containing the parse tree, parser path,
    context, and failures, focusing on the furthest parsers that attempted to parse.
    """
    lines: list[str] = []
    lines.append("Debug information:")
    lines.append("==================")
    lines.append("Parse tree:")
    lines.append(display_tree_order_by_entry(tree))

    return "\n".join(lines)


@dataclass(frozen=True)
class DebugTextState(TextState):
    """
    A TextState subclass that captures parser execution information for debug display.
    When a parser fails, this state can provide detailed information about what
    parsers were attempted and where the failure occurred.
    """

    tree: Node = field(default_factory=Node.default)

    def progress(
        self: Self, index: int, failures: Tuple[FailureInfo, ...] = tuple()
    ) -> Self:
        """
        Override progress to maintain the tree state across state transitions.
        """
        # Use the parent's progress method but ensure we keep our tree
        new_state = super().progress(index, failures)
        # The tree should already be preserved by the parent's progress method
        # since it uses **{field.name: getattr(self, field.name) for field in fields(self)}
        return new_state

    def success(self: Self, value: Any) -> Any:
        # Capture successful parser results in the tree
        stack = ParseStack.get_from_stack()
        if stack.path:  # Only add to tree if we have a valid path
            node = Node(stack.path[-1], [], result=value)
            append_tree(self.tree, stack.path, node)

        return super().success(value)

    def failure(self: Self, message: str) -> Any:
        # Capture failure in the tree when it actually occurs
        stack = ParseStack.get_from_stack()
        if stack.path:  # Only add to tree if we have a valid path
            node = Node(stack.path[-1], [], result=Failure)
            append_tree(self.tree, stack.path, node)

        return super().failure(message)

    def get_debug_info(self: Self) -> str:
        """Get formatted debug information for this state."""
        return format_debug_info(self, self.tree)
