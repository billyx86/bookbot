import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (
    compute_stats,
    decode_book_bytes,
    format_csv,
    format_json,
    format_text,
    get_book_text,
    looks_like_text,
    parse_args,
)
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

    def test_matches_reference_counting(self):
        # #13: the implementation moved to collections.Counter; the
        # public contract is a char->count mapping, and every consumer
        # (sum(.values()), .items(), membership) must behave exactly as
        # with a plain dict.
        text = "The quick brown fox"
        expected = {}
        for ch in text.lower():
            expected[ch] = expected.get(ch, 0) + 1
        counts = get_char_count(text)
        assert dict(counts) == expected
        assert sum(counts.values()) == len(text)

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

    def test_empty_string_is_text(self):
        # get_book_text runs the empty check afterwards; the gate must not
        # mask it with a false negative.
        assert looks_like_text("")

    def test_normal_whitespace_accepted(self):
        assert looks_like_text("line one\nline two\r\nline three\ttabbed")

    def test_sparse_controls_below_threshold_accepted(self):
        # A stray control char or two in a long text is fine.
        text = "word " * 500 + "\x0b"
        assert looks_like_text(text)

    def test_nul_free_binary_rejected(self):
        # The #11 bug: binary whose bytes contain no 0x00 decodes
        # losslessly under latin-1 to mostly control characters.
        blob = bytes(random.choice(range(1, 256)) for _ in range(4096))
        assert not looks_like_text(blob.decode("latin-1"))

    def test_dense_control_run_rejected(self):
        text = "ok " * 40 + "\x0e\x0f\x10" * 400
        assert not looks_like_text(text)

    def test_c1_block_heavy_text_rejected(self):
        # latin-1 decode of 0x80-0x9F yields C1 controls, not printable text.
        text = "\x80\x81\x82" * 300 + "hello"
        assert not looks_like_text(text)


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

    def test_nul_free_binary_exits(self, tmp_path, capsys):
        # #11 regression: binary whose bytes contain no NUL byte used to
        # pass the gate and produce a garbage report. It must now exit
        # with the friendly not-a-text-file error.
        blob = bytes(random.choice(range(1, 256)) for _ in range(4096))
        book = tmp_path / "blob.bin"
        book.write_bytes(blob)
        with pytest.raises(SystemExit) as exc:
            get_book_text(str(book))
        assert exc.value.code == 1
        assert "not a text file" in capsys.readouterr().out

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


SAMPLE = "The cat sat on the mat. The cat saw a rat. A rat and a cat sat together."


class TestComputeStats:
    def test_counts_all_three(self):
        stats = compute_stats(SAMPLE, top_n=3)
        assert stats["word_count"] == get_num_words(SAMPLE)
        assert stats["char_count"] == get_char_count(SAMPLE)
        assert stats["top_words"] == get_most_common_words(SAMPLE, 3)

    def test_top_n_is_honoured(self):
        stats = compute_stats(SAMPLE, top_n=2)
        assert len(stats["top_words"]) == 2


class TestFormatText:
    def test_structure(self):
        out = format_text(compute_stats(SAMPLE, top_n=3), "book.txt")
        lines = out.split("\n")
        assert lines[0] == "============ BOOKBOT ============"
        assert lines[-1] == "============= END ==============="
        assert f"Found {get_num_words(SAMPLE)} total words" in out

    def test_letter_percentages_sum_to_at_most_100(self):
        out = format_text(compute_stats(SAMPLE, top_n=3), "book.txt")
        import re

        pcts = [float(m) for m in re.findall(r"\((\d+\.\d+)%\)", out)]
        assert 0 < sum(pcts) <= 100.0

    def test_book_path_is_shown(self):
        out = format_text(compute_stats(SAMPLE, top_n=3), "books/foo.txt")
        assert "books/foo.txt" in out


class TestFormatJson:
    def test_round_trips(self):
        import json

        stats = compute_stats(SAMPLE, top_n=3)
        data = json.loads(format_json(stats, "book.txt"))
        assert data["file"] == "book.txt"
        assert data["word_count"] == stats["word_count"]
        assert data["character_count"] == stats["char_count"]
        # "the" and "cat" tie at the top; ties break alphabetically.
        assert data["most_common_words"][0]["word"] == "cat"
        assert all(set(w) == {"word", "count"} for w in data["most_common_words"])

    def test_indentation_for_readability(self):
        out = format_json(compute_stats(SAMPLE, top_n=1), "book.txt")
        assert "\n  " in out  # indented, not single-line


class TestFormatCsv:
    def test_header_and_sections(self):
        import csv
        import io

        out = format_csv(compute_stats(SAMPLE, top_n=3), "book.txt")
        rows = list(csv.reader(io.StringIO(out)))
        assert rows[0] == ["section", "key", "value"]
        sections = {r[0] for r in rows[1:]}
        assert sections == {"summary", "char", "top_word"}

    def test_summary_rows(self):
        import csv
        import io

        rows = list(
            csv.reader(
                io.StringIO(format_csv(compute_stats(SAMPLE, top_n=3), "book.txt"))
            )
        )
        summary = {r[1]: r[2] for r in rows if r[0] == "summary"}
        assert summary["file"] == "book.txt"
        assert int(summary["word_count"]) == get_num_words(SAMPLE)

    def test_char_rows_carry_all_characters(self):
        import csv
        import io

        rows = list(
            csv.reader(
                io.StringIO(format_csv(compute_stats(SAMPLE, top_n=3), "book.txt"))
            )
        )
        char_rows = {r[1]: int(r[2]) for r in rows if r[0] == "char"}
        assert sum(char_rows.values()) == sum(get_char_count(SAMPLE).values())


class TestParseArgs:
    def test_defaults_to_text(self):
        assert parse_args(["book.txt"]) == ("book.txt", "text")

    def test_long_flag(self):
        assert parse_args(["book.txt", "--format", "json"]) == ("book.txt", "json")

    def test_short_flag(self):
        assert parse_args(["book.txt", "-f", "csv"]) == ("book.txt", "csv")

    def test_equals_form(self):
        assert parse_args(["book.txt", "--format=json"]) == ("book.txt", "json")

    def test_flag_before_path(self):
        assert parse_args(["-f", "json", "book.txt"]) == ("book.txt", "json")

    def test_unknown_format_exits(self):
        with pytest.raises(SystemExit) as exc:
            parse_args(["book.txt", "--format", "xml"])
        assert exc.value.code == 2

    def test_missing_format_value_exits(self):
        with pytest.raises(SystemExit) as exc:
            parse_args(["book.txt", "--format"])
        assert exc.value.code == 2

    def test_missing_path_shows_usage(self):
        with pytest.raises(SystemExit) as exc:
            parse_args([])
        assert exc.value.code == 1

    def test_too_many_paths_shows_usage(self):
        with pytest.raises(SystemExit) as exc:
            parse_args(["a.txt", "b.txt"])
        assert exc.value.code == 1
