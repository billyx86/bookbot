import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stats import get_char_count, get_most_common_words, get_num_words
from main import get_book_text


class TestGetNumWords:
    def test_counts_whitespace_separated_words(self):
        assert get_num_words("one two three") == 3

    def test_ignores_extra_whitespace(self):
        assert get_num_words("  one   two \tthree\n") == 3

    def test_empty_string_is_zero(self):
        assert get_num_words("") == 0

    def test_punctuation_stays_attached(self):
        # Word count is intentionally a raw whitespace split.
        assert get_num_words("hello, world!") == 2


class TestGetCharCount:
    def test_basic_counts(self):
        assert get_char_count("aab") == {"a": 2, "b": 1}

    def test_case_insensitive(self):
        assert get_char_count("Aa") == {"a": 2}

    def test_includes_non_alpha_chars(self):
        counts = get_char_count("a b")
        assert counts[" "] == 1

    def test_empty_string(self):
        assert get_char_count("") == {}


class TestGetMostCommonWords:
    def test_top_n(self):
        text = "the cat sat on the mat the cat"
        top = get_most_common_words(text, 2)
        assert top == [("the", 3), ("cat", 2)]

    def test_case_insensitive(self):
        top = get_most_common_words("Dog dog DOG", 1)
        assert top == [("dog", 3)]

    def test_strips_edge_punctuation(self):
        top = get_most_common_words("fox, fox. fox! (fox)", 1)
        assert top == [("fox", 4)]

    def test_ignores_single_characters(self):
        top = get_most_common_words("a b c def def", 5)
        assert [w for w, _ in top] == ["def"]

    def test_ties_break_alphabetically(self):
        top = get_most_common_words("zeta beta alpha", 3)
        assert top == [("alpha", 1), ("beta", 1), ("zeta", 1)]

    def test_n_larger_than_vocab(self):
        top = get_most_common_words("one two three", 10)
        assert len(top) == 3


class TestGetBookText:
    def test_reads_utf8_file(self, tmp_path):
        book = tmp_path / "book.txt"
        book.write_text("hello world", encoding="utf-8")
        assert get_book_text(str(book)) == "hello world"

    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            get_book_text(str(tmp_path / "nope.txt"))
        assert exc.value.code == 1

    def test_non_utf8_file_exits(self, tmp_path):
        book = tmp_path / "binary.bin"
        book.write_bytes(b"\xff\xfe\x00\x01")
        with pytest.raises(SystemExit) as exc:
            get_book_text(str(book))
        assert exc.value.code == 1

    def test_empty_file_exits(self, tmp_path):
        book = tmp_path / "empty.txt"
        book.write_text("   \n  ", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            get_book_text(str(book))
        assert exc.value.code == 1

    def test_directory_exits(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            get_book_text(str(tmp_path))
        assert exc.value.code == 1
