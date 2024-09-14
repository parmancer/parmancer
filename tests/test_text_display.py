from parmancer.text_display import context_window

text = """
0: the quick brown fox jumped over the lazy dog 0THE QUICK BROWN FOX JUMPED OVER THE LAZY DOG
1:  the quick brown fox jumped over the lazy dog 1THE QUICK BROWN FOX JUMPED OVER THE LAZY DOG
2:   the quick brown fox jumped over the lazy dog 2THE QUICK BROWN FOX JUMPED OVER THE LAZY DOG
3:    the quick brown fox jumped over the lazy dog 3THE QUICK BROWN FOX JUMPED OVER THE LAZY DOG
4:     the quick brown fox jumped over the lazy dog 4THE QUICK BROWN FOX JUMPED OVER THE LAZY DOG
5:      the quick brown fox jumped over the lazy dog 5THE QUICK BROWN FOX JUMPED OVER THE LAZY DOG"""


class TestTextDisplay:
    @staticmethod
    def test_index_at_left_edge() -> None:
        # Arrange
        ind = 286

        # Act
        lines, pointer = context_window(text, ind, lines_of_context=1)

        # Assert
        # 1 line of context either side = 3 lines total
        assert len(lines) == 3
        # The pointer within the context points to the 2nd (middle) line
        assert pointer.line == 1
        # This pointer is at the left edge of a line
        assert pointer.column == 0
        # All line widths are 80 characters
        assert all(len(line) == 80 for line in lines)
        # The pointer points to the same character as the global index
        assert text[ind] == lines[pointer.line][pointer.column]

    @staticmethod
    def test_index_at_left_edge_with_zero_context() -> None:
        # Arrange
        ind = 286

        # Act
        lines, pointer = context_window(text, ind, lines_of_context=0)

        # Assert
        # 1 line of context either side = 3 lines total
        assert len(lines) == 1
        # The pointer within the context points to the 2nd (middle) line
        assert pointer.line == 0
        # This pointer is at the left edge of a line
        assert pointer.column == 0
        # All line widths are 80 characters
        assert all(len(line) == 80 for line in lines)
        # The pointer points to the same character as the global index
        assert text[ind] == lines[pointer.line][pointer.column]

    @staticmethod
    def test_index_at_middle() -> None:
        # Arrange
        ind = 230

        # Act
        lines, pointer = context_window(text, ind, lines_of_context=1)

        # Assert
        # 1 line of context either side = 3 lines total
        assert len(lines) == 3
        # The pointer within the context points to the 2nd (middle) line
        assert pointer.line == 1
        # The pointer is in the middle of the line because there was no shift left or right
        assert pointer.column == 40
        # All line widths are 80 characters
        assert all(len(line) == 80 for line in lines)
        # The pointer points to the same character as the global index
        assert text[ind] == lines[pointer.line][pointer.column]

    @staticmethod
    def test_index_at_right_edge() -> None:
        # Arrange
        ind = 381

        # Act
        lines, pointer = context_window(text, ind, lines_of_context=1, width=5)

        # Assert
        # Each line is staggered 1 character to the right in this test text
        assert lines == ["LAZY DOG\n", " LAZY DOG\n", "E LAZY DOG\n"]
        # 1 line of context either side = 3 lines total
        assert len(lines) == 3
        # The pointer within the context points to the 2nd (middle) line
        assert pointer.line == 1
        # This pointer is 1 character away from the right edge of the window
        assert pointer.column == 8
        # The pointer points to the same character as the global index
        assert text[ind] == lines[pointer.line][pointer.column]

    @staticmethod
    def test_index_at_newline() -> None:
        # Arrange
        ind = 382

        # Act
        lines, pointer = context_window(text, ind, lines_of_context=1, width=5)

        # Assert
        # Each line is staggered 1 character to the right in this test text
        assert lines == ["LAZY DOG\n", " LAZY DOG\n", "E LAZY DOG\n"]
        # 1 line of context either side = 3 lines total
        assert len(lines) == 3
        # The pointer within the context points to the 2nd (middle) line
        assert pointer.line == 1
        # This pointer is 1 character away from the right edge of the window
        assert pointer.column == 9
        # The pointer points to the same character as the global index
        assert text[ind] == lines[pointer.line][pointer.column]

    @staticmethod
    def test_index_at_end() -> None:
        # Arrange
        text = "abc"
        ind = 3

        # Act
        lines, pointer = context_window(text, ind, lines_of_context=0)

        # Assert
        # Each line is staggered 1 character to the right in this test text
        assert lines == ["abc"]
        # The pointer within the context points to the 2nd (middle) line
        assert pointer.line == 0
        # This pointer is 1 character away from the right edge of the window
        assert pointer.column == 3

    @staticmethod
    def test_index_at_newline_with_zero_context() -> None:
        # Arrange
        ind = 382

        # Act
        lines, pointer = context_window(text, ind, lines_of_context=0, width=5)

        # Assert
        # Each line is staggered 1 character to the right in this test text
        assert lines == ["E LAZY DOG\n"]
        # 1 line of context either side = 3 lines total
        assert len(lines) == 1
        # The pointer within the context points to the 2nd (middle) line
        assert pointer.line == 0
        # This pointer is 1 character away from the right edge of the window
        assert pointer.column == 10
        # The pointer points to the same character as the global index
        assert text[ind] == lines[pointer.line][pointer.column]

    @staticmethod
    def test_text_smaller_than_context() -> None:
        # Arrange
        text = "abc"
        ind = 1

        # Act
        lines, pointer = context_window(text, ind, lines_of_context=2, width=5)

        # Assert
        assert lines == ["abc"]
        assert len(lines) == 1
        assert pointer.line == 0
        assert pointer.column == 1
        assert text[ind] == lines[pointer.line][pointer.column]
