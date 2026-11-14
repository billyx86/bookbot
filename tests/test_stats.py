import io
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
    get_book_bytes,
    get_book_text,
    looks_like_text,
    parse_args,
)
from stats import (
    get_avg_word_length,
    get_char_count,
    get_most_common_words,
    get_num_words,
    get_sentence_count,
)


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


class TestGetAvgWordLength:
    """#21: average word length over the raw whitespace token set."""

    def test_empty_string_is_zero_float(self):
        # No words -> 0.0, never a ZeroDivisionError.
        assert get_avg_word_length("") == 0.0

    def test_whitespace_only_is_zero(self):
        assert get_avg_word_length("  \n\t  ") == 0.0

    def test_uniform_words(self):
        # "cat" / "dog" / "pig" are all three characters.
        assert get_avg_word_length("cat dog pig") == 3.0

    def test_mixed_word_lengths(self):
        # (1 + 2 + 3) / 3 — the plain arithmetic mean of token lengths.
        assert get_avg_word_length("a bb ccc") == 2.0

    def test_punctuation_stays_attached(self):
        # Same token set as get_num_words: "hello," and "world!" are
        # six-character tokens, so the average is 6.0, not 5.0.
        assert get_avg_word_length("hello, world!") == 6.0

    def test_returns_float(self):
        assert isinstance(get_avg_word_length(SAMPLE), float)

    def test_pins_the_raw_token_set(self):
        # 18 whitespace tokens, 55 characters in total (counting the
        # trailing punctuation on "mat." / "rat." / "together.").
        expected = sum(len(w) for w in SAMPLE.split()) / len(SAMPLE.split())
        assert expected == pytest.approx(55 / 18)
        assert get_avg_word_length(SAMPLE) == expected

    def test_matches_word_count_consistency(self):
        # avg * word_count is exactly the characters inside word tokens
        # — the invariant that ties this to the headline word_count.
        stats = compute_stats(SAMPLE, top_n=3)
        total = sum(len(w) for w in SAMPLE.split())
        assert stats["avg_word_length"] * stats["word_count"] == pytest.approx(total)


class TestGetSentenceCount:
    """#21: sentence count via the documented [.!?]+ heuristic.

    The caveats in ``get_sentence_count``'s docstring are part of the
    contract: it over-counts abbreviations/decimals and under-counts
    punctuation-free text, and these tests pin that behaviour so nobody
    "fixes" it silently.
    """

    def test_empty_string_is_zero(self):
        assert get_sentence_count("") == 0

    def test_no_terminators_is_zero(self):
        # Documented under-count: no terminal punctuation, no sentences.
        assert get_sentence_count("hello there") == 0

    def test_returns_int(self):
        assert isinstance(get_sentence_count(SAMPLE), int)

    def test_simple_sentences(self):
        assert get_sentence_count("One. Two! Three?") == 3

    def test_terminator_at_end_without_trailing_space(self):
        assert get_sentence_count("The end.") == 1

    def test_terminator_runs_count_once(self):
        # "?!..." is one run, so one sentence end — not four.
        assert get_sentence_count("What?! Really...") == 2

    def test_sample_has_three_sentences(self):
        assert get_sentence_count(SAMPLE) == 3

    def test_overcounts_decimals(self):
        # Documented over-count: "3.14" adds a phantom sentence end, so
        # one real sentence is reported as two.
        assert get_sentence_count("Pi is 3.14.") == 2

    def test_overcounts_abbreviations(self):
        # Documented over-count: "e.g." contributes two phantom ends, so
        # one real sentence is reported as three.
        assert get_sentence_count("Use e.g. this one.") == 3


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

    def test_cp1252_smart_quotes_decoded(self):
        # #17: cp1252 smart quotes (bytes 0x93/0x94) must decode to real
        # Unicode, not the C1 controls the latin-1 fallback used to produce.
        raw = b"He said \x93hello\x94 and left."
        assert decode_book_bytes(raw) == "He said \u201chello\u201d and left."

    def test_cp1252_em_dash_and_bullet(self):
        # em-dash 0x97 and bullet 0x95 — the cp1252 punctuation a real
        # legacy .txt book is full of.
        raw = b"The end \x97 new \x95 1999"
        assert decode_book_bytes(raw) == "The end \u2014 new \u2022 1999"

    def test_cp1252_undefined_byte_falls_to_latin1(self):
        # 0x90 is undefined in cp1252, so a byte cp1252 cannot map still
        # lands in the latin-1 fallback (never raises, same character).
        raw = b"\x90"
        assert decode_book_bytes(raw) == "\x90"

    def test_cp1252_text_passes_text_gate(self):
        # The payoff of #17: decoded smart quotes no longer trip the
        # C1-control binary scan that used to reject the whole file.
        raw = b"He said \x93hello\x94 and left the room."
        assert looks_like_text(decode_book_bytes(raw))

    def test_latin1_identical_bytes_still_fine(self):
        # 0xE9 (é) maps identically in cp1252 and latin-1, so the existing
        # fallback path returns the same character once cp1252 is first.
        raw = "café".encode("latin-1")
        assert decode_book_bytes(raw) == "café"


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

    def test_cp1252_book_is_read(self, tmp_path, capsys):
        # #17: a real cp1252 book (smart quotes, em-dash, bullet) decodes to
        # proper Unicode and passes the text gate — no "not a text file" error.
        raw = b"He said \x93hello,\x94 the end \x97 a \x95 list."
        book = tmp_path / "book.txt"
        book.write_bytes(raw)
        assert (
            get_book_text(str(book))
            == "He said \u201chello,\u201d the end \u2014 a \u2022 list."
        )

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

    def test_avg_word_length_and_sentence_count_present(self):
        stats = compute_stats(SAMPLE, top_n=3)
        assert stats["avg_word_length"] == get_avg_word_length(SAMPLE)
        assert stats["sentence_count"] == get_sentence_count(SAMPLE)
        assert stats["sentence_count"] == 3


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

    def test_avg_word_length_line(self):
        # 55 chars / 18 tokens = 3.0555... -> two decimals for humans.
        out = format_text(compute_stats(SAMPLE, top_n=3), "book.txt")
        assert "Average word length: 3.06" in out

    def test_sentence_statistics_section(self):
        out = format_text(compute_stats(SAMPLE, top_n=3), "book.txt")
        assert "------ Sentence Statistics ------" in out
        assert "Sentence count: 3" in out

    def test_new_section_sits_between_word_and_character_count(self):
        out = format_text(compute_stats(SAMPLE, top_n=3), "book.txt")
        word = out.index("total words")
        sent = out.index("------ Sentence Statistics ------")
        chars = out.index("--------- Character Count -------")
        assert word < sent < chars


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

    def test_avg_word_length_is_a_float(self):
        import json

        data = json.loads(format_json(compute_stats(SAMPLE, top_n=3), "book.txt"))
        assert data["avg_word_length"] == pytest.approx(55 / 18)
        assert isinstance(data["avg_word_length"], float)

    def test_sentence_count_is_an_int(self):
        import json

        data = json.loads(format_json(compute_stats(SAMPLE, top_n=3), "book.txt"))
        assert data["sentence_count"] == 3
        assert isinstance(data["sentence_count"], int)

    def test_new_keys_sit_next_to_word_count(self):
        import json

        data = json.loads(format_json(compute_stats(SAMPLE, top_n=3), "book.txt"))
        assert list(data) == [
            "file",
            "word_count",
            "avg_word_length",
            "sentence_count",
            "character_count",
            "most_common_words",
        ]


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

    def test_summary_rows_for_new_stats(self):
        import csv

        rows = list(
            csv.reader(
                io.StringIO(format_csv(compute_stats(SAMPLE, top_n=3), "book.txt"))
            )
        )
        summary = {r[1]: r[2] for r in rows if r[0] == "summary"}
        assert float(summary["avg_word_length"]) == pytest.approx(55 / 18)
        assert int(summary["sentence_count"]) == 3


class TestByteStableReportFixture:
    """#21: the whole text report, pinned byte for byte.

    The corpus is hand-checkable: 12 whitespace tokens totalling 33
    characters (avg 2.75) and two ``.`` sentence ends (sentence count 2).
    """

    CORPUS = "The cat sat on the mat.\nA rat saw a dog run.\n"
    EXPECTED = (
        "============ BOOKBOT ============\n"
        "Analyzing book found at corpus.txt...\n"
        "----------- Word Count ----------\n"
        "Found 12 total words\n"
        "Average word length: 2.75\n"
        "------ Sentence Statistics ------\n"
        "Sentence count: 2\n"
        "--------- Character Count -------\n"
        "a: 7 (15.56%)\n"
        "t: 6 (13.33%)\n"
        "h: 2 (4.44%)\n"
        "e: 2 (4.44%)\n"
        "s: 2 (4.44%)\n"
        "o: 2 (4.44%)\n"
        "n: 2 (4.44%)\n"
        "r: 2 (4.44%)\n"
        "c: 1 (2.22%)\n"
        "m: 1 (2.22%)\n"
        "w: 1 (2.22%)\n"
        "d: 1 (2.22%)\n"
        "g: 1 (2.22%)\n"
        "u: 1 (2.22%)\n"
        "-------- Most Common Words ------\n"
        "the: 2\n"
        "cat: 1\n"
        "dog: 1\n"
        "mat: 1\n"
        "on: 1\n"
        "rat: 1\n"
        "run: 1\n"
        "sat: 1\n"
        "saw: 1\n"
        "============= END ==============="
    )

    def test_hand_checked_values(self):
        stats = compute_stats(self.CORPUS, top_n=10)
        assert stats["word_count"] == 12
        assert stats["avg_word_length"] == 2.75
        assert stats["sentence_count"] == 2

    def test_full_report_matches_fixture(self):
        out = format_text(compute_stats(self.CORPUS, top_n=10), "corpus.txt")
        assert out == self.EXPECTED

    def test_every_section_header_is_33_characters(self):
        out = format_text(compute_stats(self.CORPUS, top_n=10), "corpus.txt")
        headers = [
            line for line in out.split("\n") if line.startswith(("---", "====", "----"))
        ]
        assert headers and all(len(h) == 33 for h in headers)


class TestParseArgs:
    def test_defaults_to_text(self):
        assert parse_args(["book.txt"]) == ("book.txt", "text", 10)

    def test_long_flag(self):
        assert parse_args(["book.txt", "--format", "json"]) == ("book.txt", "json", 10)

    def test_short_flag(self):
        assert parse_args(["book.txt", "-f", "csv"]) == ("book.txt", "csv", 10)

    def test_equals_form(self):
        assert parse_args(["book.txt", "--format=json"]) == ("book.txt", "json", 10)

    def test_flag_before_path(self):
        assert parse_args(["-f", "json", "book.txt"]) == ("book.txt", "json", 10)

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


class TestStdinArgs:
    """#18: `-` / `--stdin` select stdin as the book source."""

    def test_dash_is_stdin_source(self):
        assert parse_args(["-"]) == ("-", "text", 10)

    def test_stdin_flag(self):
        assert parse_args(["--stdin"]) == ("-", "text", 10)

    def test_stdin_with_format_and_top(self):
        assert parse_args(["-", "--format", "json", "--top", "3"]) == (
            "-",
            "json",
            3,
        )

    def test_stdin_flag_equals_form(self):
        assert parse_args(["--stdin", "--format=csv"]) == ("-", "csv", 10)

    def test_stdin_flag_before_format_value(self):
        assert parse_args(["--stdin", "-f", "json"]) == ("-", "json", 10)

    def test_dash_plus_file_still_usage_error(self):
        # Two sources is still a usage error; stdin is a source, not a
        # wildcard.
        with pytest.raises(SystemExit) as exc:
            parse_args(["-", "book.txt"])
        assert exc.value.code == 1


class TestGetBookBytes:
    """#18: the shared read path (file path OR stdin bytes)."""

    @staticmethod
    def _fake_stdin(data):
        """An object with a ``.buffer`` exposing ``data`` as a byte stream,
        mimicking ``sys.stdin`` when a pipe is attached."""

        class _Stdin:
            buffer = io.BytesIO(data)

        return _Stdin()

    def test_reads_a_file(self, tmp_path):
        book = tmp_path / "book.txt"
        book.write_bytes(b"hello world")
        assert get_book_bytes("book.txt", str(book)) == "hello world"

    def test_reads_stdin_bytes(self, monkeypatch):
        # Source "-" with stdin patched: the exact bytes the pipe handed
        # over, through the same decode + gate chain as a file.
        monkeypatch.setattr(sys, "stdin", self._fake_stdin(b"hello world"))
        assert get_book_bytes("-", None) == "hello world"

    def test_stdin_utf8(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", self._fake_stdin("café".encode()))
        assert get_book_bytes("-", None) == "café"

    def test_stdin_cp1252(self, monkeypatch):
        # #17 + #18 intersect: a cp1252 smart-quote stream decodes properly.
        monkeypatch.setattr(sys, "stdin", self._fake_stdin(b"he said \x93hi\x94"))
        assert get_book_bytes("-", None) == "he said \u201chi\u201d"

    def test_stdin_binary_refused(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", self._fake_stdin(b"\x00\x01\x02\x03"))
        with pytest.raises(SystemExit) as exc:
            get_book_bytes("-", None)
        assert exc.value.code == 1
        assert "not a text file" in capsys.readouterr().out

    def test_stdin_empty_refused(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", self._fake_stdin(b"   \n"))
        with pytest.raises(SystemExit) as exc:
            get_book_bytes("-", None)
        assert exc.value.code == 1
        assert "empty" in capsys.readouterr().out.lower()
