from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class LineColumn:
    """Line and column number of a character in text"""

    line: int
    column: int

    @staticmethod
    def from_index(text: str, index: int) -> "LineColumn":
        if index > len(text) or index < 0:
            raise ValueError("Invalid index outside of text")
        line = text.count("\n", 0, index)
        start_line_index = text.rfind("\n", 0, index) + 1
        column = index - start_line_index
        return LineColumn(line, column)


@dataclass
class LineContext:
    """
    Information about a context window around a target character with some amount of
    context around it.

    :param lines_of_context: The number of lines to keep either side of the cursor
    :param start_context_index: Global index of the first character of the context window
    :param end_context_index: Global index of the last character of the context window
    :param cursor_in_context: Line and column of the target character within the context
    """

    lines_of_context: int
    start_index: int
    end_index: int
    cursor: LineColumn

    @staticmethod
    def locate(
        text: str,
        index: int,
        lines_of_context: int = 2,
    ) -> "LineContext":
        """Create line context for the given text at the index."""
        if index > len(text) or index < 0:
            raise ValueError("Invalid index outside of text")
        start_index = index
        lines_before = 0
        for lines_before in range(lines_of_context + 1):
            start_index = text.rfind("\n", 0, start_index)
            if start_index == -1:
                break
        # Vertical context after
        end_line_index = text.find("\n", index)
        if end_line_index == -1:
            end_line_index = len(text)
        end_index = index
        for _ in range(
            lines_of_context + (0 if text[index : index + 1] == "\n" else 1)
        ):
            end_index = text.find("\n", end_index + 1)
            if end_index == -1:
                # reached end of text
                end_index = len(text) - 1
                break
        cursor = LineColumn.from_index(text, index)
        return LineContext(
            lines_of_context=lines_of_context,
            start_index=start_index + 1,
            end_index=end_index + 1,
            cursor=LineColumn(lines_before, cursor.column),
        )


def context_window(
    text: str, index: int, lines_of_context: int = 2, width: int = 40
) -> Tuple[List[str], LineColumn]:
    """Create a context window around a piece of text

    :param text: The text to create a window around
    :param index: The index of the cursor in the text
    :param lines_of_context: Number of lines to show either side of the target line
    :param width: Number of characters to show either side of the cursor
    :return: A tuple containing a list of the lines in the context window, and the line
        and column of the cursor index in that context window.
    """
    context = LineContext.locate(text, index, lines_of_context)
    lines = text[context.start_index : context.end_index].splitlines(keepends=True)
    # Newlines are kept but counted as 0-width
    max_length = max(len(line.rstrip("\n")) for line in lines)
    column = context.cursor.column
    if (max_length - column) < width:
        # Touching right edge
        left_index = max(0, max_length - 2 * width)
        right_index = max_length + 1  # In case there are newline characters
    elif column < width:
        # Touching left edge
        left_index = 0
        right_index = min(max_length, 2 * width)
    else:
        # Away from edges
        left_index = column - width
        right_index = column + width
    cursor = LineColumn(
        context.cursor.line,
        context.cursor.column - left_index,
    )
    return [line[left_index:right_index] for line in lines], cursor
