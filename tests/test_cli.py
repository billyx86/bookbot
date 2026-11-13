"""CLI-layer tests for main.py (#12).

Covers what test_stats.py leaves out: parse_args's help / exit-code
behaviour, main() end to end with a real book file (all three formats),
and the process entry point via subprocess (usage, help, happy path,
error paths). The text report is byte-stable by contract — main() must
print exactly what format_text produces.
"""

import csv
import io
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (  # noqa: E402
    compute_stats,
    format_text,
    main,
    parse_args,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(REPO_ROOT, "main.py")
SAMPLE = "The cat sat on the mat. The cat saw a rat."


def _write_book(tmp_path, name="book.txt", text=SAMPLE):
    book = tmp_path / name
    book.write_text(text, encoding="utf-8")
    return str(book)


def _run_cli(*argv):
    """Run main.py as a real subprocess; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, MAIN, *argv],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )


class TestParseArgsHelp:
    def test_help_flag_exits_zero(self):
        with pytest.raises(SystemExit) as exc:
            parse_args(["--help"])
        assert exc.value.code == 0

    def test_short_help_flag_exits_zero(self):
        with pytest.raises(SystemExit) as exc:
            parse_args(["-h"])
        assert exc.value.code == 0

    def test_help_with_other_args_exits_zero(self):
        # Help wins even when other arguments are present.
        with pytest.raises(SystemExit) as exc:
            parse_args(["book.txt", "--format", "json", "--help"])
        assert exc.value.code == 0


class TestMainTextFormat:
    def test_happy_path_prints_byte_stable_report(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path)
        monkeypatch.setattr(sys, "argv", ["main.py", book])
        main()
        expected = format_text(compute_stats(SAMPLE, top_n=10), book)
        assert capsys.readouterr().out == expected + "\n"

    def test_flag_before_path(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path)
        monkeypatch.setattr(sys, "argv", ["main.py", "-f", "text", book])
        main()
        out = capsys.readouterr().out
        assert out.startswith("============ BOOKBOT ============")
        assert out.rstrip("\n").endswith("============= END ===============")

    def test_shows_avg_word_length_and_sentence_count(
        self, tmp_path, monkeypatch, capsys
    ):
        # #21: SAMPLE has 11 tokens / 32 chars (2.9090...) and two '.'
        # sentence ends, so the text report shows 2.91 and 2.
        book = _write_book(tmp_path)
        monkeypatch.setattr(sys, "argv", ["main.py", book])
        main()
        out = capsys.readouterr().out
        assert "Average word length: 2.91" in out
        assert "------ Sentence Statistics ------" in out
        assert "Sentence count: 2" in out


class TestMainJsonFormat:
    def test_emits_valid_json(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path)
        monkeypatch.setattr(sys, "argv", ["main.py", book, "--format", "json"])
        main()
        data = json.loads(capsys.readouterr().out)
        assert data["file"] == book
        assert data["word_count"] == 11
        # character_count must round-trip the real counts for the sample.
        assert data["character_count"] == dict(
            (ch, SAMPLE.lower().count(ch)) for ch in set(SAMPLE.lower())
        )
        assert all(set(w) == {"word", "count"} for w in data["most_common_words"])

    def test_exposes_avg_word_length_and_sentence_count(
        self, tmp_path, monkeypatch, capsys
    ):
        # #21 acceptance: --format json exposes avg_word_length (float)
        # and sentence_count (int). SAMPLE = 11 tokens / 32 chars.
        book = _write_book(tmp_path)
        monkeypatch.setattr(sys, "argv", ["main.py", book, "--format", "json"])
        main()
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data["avg_word_length"], float)
        assert data["avg_word_length"] == pytest.approx(32 / 11)
        assert isinstance(data["sentence_count"], int)
        assert data["sentence_count"] == 2

    def test_top_words_ordered_by_count(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path)
        monkeypatch.setattr(sys, "argv", ["main.py", "--format=json", book])
        main()
        data = json.loads(capsys.readouterr().out)
        counts = [w["count"] for w in data["most_common_words"]]
        assert counts == sorted(counts, reverse=True)


class TestMainCsvFormat:
    def test_emits_flat_table(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path)
        monkeypatch.setattr(sys, "argv", ["main.py", "-f", "csv", book])
        main()
        rows = list(csv.reader(io.StringIO(capsys.readouterr().out)))
        assert rows[0] == ["section", "key", "value"]
        summary = {r[1]: r[2] for r in rows if r[0] == "summary"}
        assert summary["file"] == book
        assert int(summary["word_count"]) == 11
        # #21: both new stats ride along in the summary block.
        assert float(summary["avg_word_length"]) == pytest.approx(32 / 11)
        assert int(summary["sentence_count"]) == 2


class TestTopNFlag:
    """#15: ``--top N`` / ``-t N`` selects the most-common-words count."""

    def test_top_flag_long(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path)
        monkeypatch.setattr(
            sys, "argv", ["main.py", book, "--top", "3", "--format", "json"]
        )
        main()
        data = json.loads(capsys.readouterr().out)
        assert len(data["most_common_words"]) == 3
        assert data["most_common_words"][0] == {"word": "the", "count": 3}

    def test_top_flag_short(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path)
        monkeypatch.setattr(
            sys, "argv", ["main.py", book, "-t", "1", "--format", "json"]
        )
        main()
        data = json.loads(capsys.readouterr().out)
        assert data["most_common_words"] == [{"word": "the", "count": 3}]

    def test_top_equals_form(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path)
        monkeypatch.setattr(sys, "argv", ["main.py", book, "--top=2", "-f", "json"])
        main()
        data = json.loads(capsys.readouterr().out)
        assert len(data["most_common_words"]) == 2

    def test_top_default_is_ten(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path)
        monkeypatch.setattr(sys, "argv", ["main.py", book, "--format", "json"])
        main()
        data = json.loads(capsys.readouterr().out)
        # The sample has only 7 distinct words, so the default top_n=10
        # returns all of them.
        assert len(data["most_common_words"]) == 7

    def test_top_reflected_in_csv(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path)
        monkeypatch.setattr(sys, "argv", ["main.py", book, "--top", "3", "-f", "csv"])
        main()
        rows = list(csv.reader(io.StringIO(capsys.readouterr().out)))
        top_word_rows = [r for r in rows if r[0] == "top_word"]
        assert len(top_word_rows) == 3
        assert top_word_rows[0] == ["top_word", "the", "3"]

    def test_top_reflected_in_text(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path)
        monkeypatch.setattr(sys, "argv", ["main.py", book, "--top", "2"])
        main()
        out = capsys.readouterr().out
        section = out.split("-------- Most Common Words ------")[1].strip()
        assert section.splitlines()[0] == "the: 3"
        assert section.splitlines()[1] == "cat: 2"

    def test_top_returns_in_tuple(self):
        assert parse_args(["book.txt", "--top", "5"]) == ("book.txt", "text", 5)
        assert parse_args(["book.txt", "-t", "7", "--format", "json"]) == (
            "book.txt",
            "json",
            7,
        )
        assert parse_args(["book.txt"]) == ("book.txt", "text", 10)

    def test_top_zero_exits_two(self, tmp_path, capsys):
        book = _write_book(tmp_path)
        with pytest.raises(SystemExit) as exc:
            parse_args([book, "--top", "0"])
        assert exc.value.code == 2
        assert "positive integer" in capsys.readouterr().out

    def test_top_negative_exits_two(self, tmp_path, capsys):
        book = _write_book(tmp_path)
        with pytest.raises(SystemExit) as exc:
            parse_args([book, "--top", "-2"])
        assert exc.value.code == 2
        assert "positive integer" in capsys.readouterr().out

    def test_top_non_integer_exits_two(self, tmp_path, capsys):
        book = _write_book(tmp_path)
        with pytest.raises(SystemExit) as exc:
            parse_args([book, "--top", "abc"])
        assert exc.value.code == 2
        assert "positive integer" in capsys.readouterr().out

    def test_top_float_exits_two(self, tmp_path, capsys):
        book = _write_book(tmp_path)
        with pytest.raises(SystemExit) as exc:
            parse_args([book, "--top", "3.5"])
        assert exc.value.code == 2
        assert "positive integer" in capsys.readouterr().out

    def test_top_missing_value_exits_two(self, tmp_path, capsys):
        book = _write_book(tmp_path)
        with pytest.raises(SystemExit) as exc:
            parse_args([book, "--top"])
        assert exc.value.code == 2
        assert "needs a value" in capsys.readouterr().out


class TestMainErrorPaths:
    def test_missing_file_exits_one_with_message(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["main.py", str(tmp_path / "nope.txt")])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert "could not find" in capsys.readouterr().out

    def test_binary_file_exits_one_with_message(self, tmp_path, monkeypatch, capsys):
        import random

        random.seed(7)
        book = tmp_path / "blob.bin"
        book.write_bytes(bytes(random.choice(range(1, 256)) for _ in range(2048)))
        monkeypatch.setattr(sys, "argv", ["main.py", str(book)])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert "not a text file" in capsys.readouterr().out

    def test_empty_file_exits_one_with_message(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path, text="   \n")
        monkeypatch.setattr(sys, "argv", ["main.py", book])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert "empty" in capsys.readouterr().out.lower()

    def test_unknown_format_exits_two(self, tmp_path, monkeypatch, capsys):
        book = _write_book(tmp_path)
        monkeypatch.setattr(sys, "argv", ["main.py", book, "--format", "yaml"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        assert "unknown format" in capsys.readouterr().out


class TestEntryPoint:
    """main.py as a real subprocess — the way users actually run it."""

    def test_no_args_prints_usage_and_exits_one(self):
        result = _run_cli()
        assert result.returncode == 1
        assert "Usage: python3 main.py" in result.stdout

    def test_help_exits_zero(self):
        result = _run_cli("--help")
        assert result.returncode == 0
        assert "Usage: python3 main.py" in result.stdout

    def test_happy_path(self, tmp_path):
        book = _write_book(tmp_path)
        result = _run_cli(book)
        assert result.returncode == 0
        assert "Found 11 total words" in result.stdout

    def test_missing_file_exits_one(self, tmp_path):
        result = _run_cli(str(tmp_path / "nope.txt"))
        assert result.returncode == 1
        assert "could not find" in result.stdout
        assert "Traceback" not in result.stderr

    def test_unknown_format_exits_two(self, tmp_path):
        book = _write_book(tmp_path)
        result = _run_cli(book, "--format", "xml")
        assert result.returncode == 2
        assert "unknown format" in result.stdout

    def test_top_flag_via_subprocess(self, tmp_path):
        book = _write_book(tmp_path)
        result = _run_cli(book, "--top", "1", "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["most_common_words"] == [{"word": "the", "count": 3}]

    def test_new_stats_via_subprocess(self, tmp_path):
        # #21 acceptance, end to end through a real process: the JSON
        # report carries avg_word_length (float) and sentence_count (int).
        book = _write_book(tmp_path)
        result = _run_cli(book, "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data["avg_word_length"], float)
        assert data["avg_word_length"] == pytest.approx(32 / 11)
        assert isinstance(data["sentence_count"], int)
        assert data["sentence_count"] == 2

    def test_new_stats_in_text_report_via_subprocess(self, tmp_path):
        book = _write_book(tmp_path)
        result = _run_cli(book)
        assert result.returncode == 0
        assert "Average word length: 2.91" in result.stdout
        assert "Sentence count: 2" in result.stdout

    def test_top_bad_value_via_subprocess(self, tmp_path):
        book = _write_book(tmp_path)
        result = _run_cli(book, "--top", "0")
        assert result.returncode == 2
        assert "positive integer" in result.stdout
        assert "Traceback" not in result.stderr


class TestStdin:
    """#18: read the book from standard input (real subprocess pipes)."""

    @staticmethod
    def _run_stdin(data, *args):
        """Run `python3 main.py <args...>` with `data` (bytes) on stdin.

        No `text=True` — the pipe carries raw bytes (incl. cp1252); we
        decode the child's stdout ourselves.
        """
        proc = subprocess.run(
            [sys.executable, MAIN, *args],
            input=data,
            capture_output=True,
            cwd=REPO_ROOT,
            timeout=30,
        )
        proc.stdout = proc.stdout.decode("utf-8", "replace")
        proc.stderr = proc.stderr.decode("utf-8", "replace")
        return proc

    def test_dash_reads_piped_utf8(self):
        proc = self._run_stdin(SAMPLE.encode("utf-8"), "-", "--format", "json")
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert data["file"] == "(stdin)"
        assert data["word_count"] == 11

    def test_stdin_flag_reads_piped_utf8(self):
        proc = self._run_stdin(SAMPLE.encode("utf-8"), "--stdin", "-f", "text")
        assert proc.returncode == 0, proc.stderr
        assert "Analyzing book found at (stdin)..." in proc.stdout
        assert "Found 11 total words" in proc.stdout

    def test_dash_refuses_binary_pipe(self):
        proc = self._run_stdin(b"\x00\x01\x02\x03\x04\x05", "-")
        assert proc.returncode == 1
        assert "not a text file" in proc.stdout
        assert "Traceback" not in proc.stderr

    def test_dash_refuses_empty_pipe(self):
        proc = self._run_stdin(b"   \n  ", "-")
        assert proc.returncode == 1
        assert "empty" in proc.stdout.lower()

    def test_stdin_flag_with_top_and_format(self):
        proc = self._run_stdin(
            SAMPLE.encode("utf-8"), "--stdin", "--top", "1", "-f", "json"
        )
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert data["most_common_words"] == [{"word": "the", "count": 3}]

    def test_zcat_gzip_pipeline(self, tmp_path):
        # The #18 motivating case: zcat book.txt.gz | bookbot -
        import gzip

        gz = tmp_path / "book.txt.gz"
        with gzip.open(gz, "wb") as f:
            f.write(SAMPLE.encode("utf-8"))
        proc = subprocess.run(
            f"zcat {gz} | {sys.executable} {MAIN} - --format json",
            shell=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert data["file"] == "(stdin)"
        assert data["word_count"] == 11

    def test_stdin_cp1252_pipe(self):
        # #17 + #18 intersect: cp1252 smart quotes on stdin decode properly.
        proc = self._run_stdin(b"he said \x93hi\x94", "-", "-f", "json")
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert data["word_count"] == 3  # he / said / hi (quotes delimit)

    def test_file_path_behaviour_unchanged(self, tmp_path):
        book = _write_book(tmp_path)
        result = _run_cli(book, "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["file"] == book  # still the literal path
        assert data["word_count"] == 11

    def test_stdin_plus_file_is_usage_error(self):
        result = _run_cli("--stdin", "book.txt")
        assert result.returncode == 1
        assert "Usage" in result.stdout

    def test_help_mentions_stdin(self):
        result = _run_cli("--help")
        assert result.returncode == 0
        assert "stdin" in result.stdout
