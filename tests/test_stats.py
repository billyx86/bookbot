import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import decode_book_bytes, get_book_text, looks_like_text
from stats import get_char_count, get_most_common_words, get_num_words


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


class TestDecodeBookBytes:
    def test_utf8_passthrough(self):
        assert decode_book_bytes(b"hello") == "hello"

    def test_utf8_bom_stripped(self):
        assert decode_book_bytes("hello".encode("utf-8-sig")) == "hello"

    def test_utf16_le_bom(self):
        # encode("utf-16") writes a BOM (native byte order) up front.
        assert decode_book_bytes("hi".encode("utf-16")) == "hi"

    def test_utf16_be_bom(self):
        assert decode_book_bytes(b"\xfe\xff" + "hi".encode("utf-16-be")) == "hi"

    def test_latin1_fallback(self):
        raw = "café".encode("latin-1")
        assert decode_book_bytes(raw) == "café"

    def test_latin1_of_garbage_never_raises(self):
        # latin-1 maps every byte, so this must return (NUL-laden) text
        # rather than raise; the caller's looks_like_text filter rejects it.
        result = decode_book_bytes(bytes(range(256)))
        assert isinstance(result, str) and "\x00" in result


class TestLooksLikeText:
    def test_plain_text(self):
        assert looks_like_text("just words and punctuation")

    def test_nul_rejected(self):
        assert not looks_like_text("abc\x00def")


class TestGetBookText:
    def test_reads_utf8_file(self, tmp_path):
        book = tmp_path / "book.txt"
        book.write_text("hello world", encoding="utf-8")
        assert get_book_text(str(book)) == "hello world"

    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            get_book_text(str(tmp_path / "nope.txt"))
        assert exc.value.code == 1

    def test_binary_file_exits(self, tmp_path):
        # Genuinely binary (no BOM, decodes to NULs under latin-1).
        book = tmp_path / "binary.bin"
        book.write_bytes(b"\x00\x01\x02\x03\x00\x04")
        with pytest.raises(SystemExit) as exc:
            get_book_text(str(book))
        assert exc.value.code == 1

    def test_utf16_with_bom_is_read(self, tmp_path):
        book = tmp_path / "book.txt"
        book.write_bytes("hello world".encode("utf-16"))
        assert get_book_text(str(book)) == "hello world"

    def test_utf16_be_with_bom_is_read(self, tmp_path):
        # BE BOM (\xfe\xff) up front, then big-endian code units.
        book = tmp_path / "book.txt"
        book.write_bytes(b"\xfe\xff" + "hello world".encode("utf-16-be"))
        assert get_book_text(str(book)) == "hello world"

    def test_latin1_is_read(self, tmp_path):
        # Only latin-1-safe characters: é (0xE9) is in the codec, an em-dash is not.
        text = "café au lait - déjà vu"
        book = tmp_path / "book.txt"
        book.write_bytes(text.encode("latin-1"))
        assert get_book_text(str(book)) == text

    def test_utf8_bom_is_stripped(self, tmp_path):
        book = tmp_path / "book.txt"
        book.write_bytes("hello world".encode("utf-8-sig"))
        assert get_book_text(str(book)) == "hello world"

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
