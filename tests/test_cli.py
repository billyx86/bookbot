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
