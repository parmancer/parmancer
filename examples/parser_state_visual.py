r"""
A way to interactively step through a parser, displaying:

- The current state of the parse tree: each parser which has run and its result value
  - The tree is ordered so that the most recent results are shown at the bottom
- A single-line string of the current parser path (separated by `/`)
- The current context of the input text, with a cursor pointing to the current parse position

Keyboard input progresses the parser to the next step.
Terminate the program to exit (e.g. Ctrl+C)

Here is an example part way through a parser:

```
└──Parser
   └──Parser
      └──KeepOne
         └──Data:File
            │  ┌──[\s\S]*?(?=School =): 'Sample text\n\nA selection of students from Riverdale High and Hogwarts took part in a quiz. This is a record of their scores.\n\n'
            ├──field:header: 'Sample text\n\nA selection of students from Riverdale High and Hogwarts took part in a quiz. This is a record of their scores.\n\n'
            └──field:schools
               └──Range(0, inf) of Data:School
                  └──Data:School
                     │     ┌──'School = ': 'School = '
                     │     ├──[^\n]+: 'Riverdale High'
                     │     ├──'\n': '\n'
                     │  ┌──KeepOne: 'Riverdale High'
                     ├──field:school: 'Riverdale High'
                     └──field:grades
                        └──Range(0, inf) of Map
                           └──Map
                              └──Data:GradeInput
                                 │     ┌──'Grade = ': 'Grade = '
                                 │     │  ┌──\d+: '1'
                                 │     ├──Map: 1
                                 │     ├──'\n': '\n'
                                 │  ┌──KeepOne: 1
                                 └──field:grade: 1
--------------------------------------------------------------------------------
KeepOne/Data:File/field:schools/Range(0, inf) of Data:School/Data:School/field:grades/Range(0, inf) of Map/Map/Data:GradeInput/field:grade/KeepOne
--------------------------------------------------------------------------------
School = Riverdale High
Grade = 1
Student number, Name
^
0, Phoebe
1, Rachel
--------------------------------------------------------------------------------
```
"""

from __future__ import annotations

import inspect
import operator
from dataclasses import dataclass, field
from functools import reduce
from typing import Any, List, Tuple

from typing_extensions import Self, TypeVar

from examples.dataclass_parser_demo import File, text
from parmancer import Result, TextState, gather

_T = TypeVar("_T")


class _Missing:
    pass


Missing = _Missing()


@dataclass
class Node:
    """Represent a node of the tree: a parser name, its children, and a result if one has been parsed."""

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


def display_tree_order_by_entry(tree: Node, indent_width: int = 2) -> None:
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

    def _display(tree: Node, indent: str = "") -> None:
        print(
            tree.name + (f": {repr(tree.result)}" if tree.result is not Missing else "")
        )
        if len(tree.children) == 0:
            return
        for child in tree.children[:-1]:
            print(indent + "├" + "─" * indent_width, end="")
            _display(child, indent + "│" + " " * indent_width)
        child = tree.children[-1]
        print(indent + "└" + "─" * indent_width, end="")
        _display(child, indent + " " * (indent_width + 1))

    _display(tree)


def display_tree_order_by_return(tree: Node, indent_width: int = 2) -> None:
    hbar = "─" * indent_width
    vbar = "│" + " " * indent_width

    space = " " * (indent_width + 1)
    bi_split = "├" + hbar
    top_split = "┌" + hbar
    bottom_split = "└" + hbar

    def _display(
        tree: Node,
        indent: str = "",
        gutter: str = space,
        split: str = bottom_split,
        depth: int = 0,
    ) -> None:
        display_before = tree.result is Missing
        if display_before:
            # Top-down print
            print(indent + split + tree.name)
            if len(tree.children) == 0:
                return
            for child in tree.children[:-1]:
                _display(child, indent + gutter, vbar, bi_split, depth + 1)
            child = tree.children[-1]

            _display(child, indent + gutter, space, bottom_split, depth + 1)
        else:
            # Bottom-up print
            if len(tree.children) == 0:
                print(indent + split + f"{tree.name}: {repr(tree.result)}")
                return
            child = tree.children[0]

            _display(
                child,
                indent + (space if split == top_split else vbar),
                vbar,
                top_split,
                depth + 1,
            )
            for child in tree.children[1:]:
                _display(
                    child,
                    indent + (space if split == top_split else vbar),
                    vbar,
                    bi_split,
                    depth + 1,
                )
            print(indent + split + f"{tree.name}: {repr(tree.result)}")

    _display(tree)


@dataclass
class ParseStack:
    path: Tuple[str, ...]

    @staticmethod
    def get_from_stack() -> ParseStack:
        stack = inspect.stack()
        try:
            context = reduce(
                operator.add,
                list(
                    reversed(
                        list(
                            element.frame.f_locals["self"].name.split("/")
                            for element in stack
                            if element.function == "parse_result"
                        )
                    )
                ),
            )
            return ParseStack(context)
        finally:
            del stack

    def __str__(self: Self) -> str:
        return "/".join(self.path)


def display_parser_state(state: TextState, value: Any, tree: Node) -> None:
    call_stack = inspect.stack()
    try:
        stack = ParseStack.get_from_stack()
        node = Node(stack.path[-1], [], result=value)

        append_tree(tree, stack.path, node)

        display_tree_order_by_return(tree)
        print("-" * 80)
        print(stack)
        print("-" * 80)
        print(state.context_display(), end="")
        print("-" * 80)
        input()
    finally:
        del call_stack


@dataclass(frozen=True)
class StepVisualizer(TextState):
    tree: Node = field(default_factory=Node.default)

    def success(self: Self, value: _T) -> Result[_T]:
        display_parser_state(self, value, self.tree)
        return super().success(value)

    def failure(self: Self, message: str) -> Result[Any]:
        display_parser_state(self, "<<<Parser failed>>>", self.tree)
        return super().failure(message)


if __name__ == "__main__":
    # Running this file will show the parser state each time a successful parser is found
    gather(File).parse(text, state_handler=StepVisualizer)
