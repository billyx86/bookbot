import csv
import io
import json
import sys

from stats import get_char_count, get_most_common_words, get_num_words

USAGE = "Usage: python3 main.py <path_to_book> [--format text|json|csv]"


def looks_like_text(text):
    """Heuristic: real text books never contain NUL bytes."""
    return "\x00" not in text


def decode_book_bytes(raw):
    """Decode a book's raw bytes into text.

    Tries UTF-8 (with optional BOM) first, then UTF-16 when the byte order
    mark is present, and finally latin-1, which maps every byte and so
    never raises. Callers should still run the result through
    ``looks_like_text`` — the chain always returns *something*, and
    genuinely binary files decode to NULs under latin-1.
    """
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")


def get_book_text(filepath):
    """Read the book file and return its contents.

    Exits with a friendly error message if the file is missing,
    unreadable, not a text file, or empty. Encodings: UTF-8 (with or
    without BOM), UTF-16 (with BOM), and latin-1 as a last resort —
    see ``decode_book_bytes``.
    """
    try:
        with open(filepath, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        print(f"Error: could not find '{filepath}'. Check the path and try again.")
        sys.exit(1)
    except IsADirectoryError:
        print(f"Error: '{filepath}' is a directory, not a file.")
        sys.exit(1)
    except PermissionError:
        print(f"Error: no permission to read '{filepath}'.")
        sys.exit(1)

    file_contents = decode_book_bytes(raw)

    if not looks_like_text(file_contents):
        print(
            f"Error: '{filepath}' is not a text file. "
            "BookBot only reads plain text books."
        )
        sys.exit(1)

    if not file_contents.strip():
        print(f"Error: '{filepath}' is empty. Nothing to count.")
        sys.exit(1)

    return file_contents


def compute_stats(text, top_n=10):
    """Compute every number the report shows, as a plain dict.

    The formatters (``format_text`` / ``format_json`` / ``format_csv``)
    take this dict, so the counting logic lives in exactly one place.
    """
    return {
        "word_count": get_num_words(text),
        "char_count": get_char_count(text),
        "top_words": get_most_common_words(text, top_n),
    }


def format_text(stats, book):
    """Render the classic human-readable report.

    Byte-stable: changing the output format without updating this string
    in the tests is how you know you changed the report people read.
    """
    char_count = stats["char_count"]
    total_chars = sum(char_count.values())

    lines = [
        "============ BOOKBOT ============",
        f"Analyzing book found at {book}...",
        "----------- Word Count ----------",
        f"Found {stats['word_count']} total words",
        "--------- Character Count -------",
    ]
    for char in dict(
        sorted(char_count.items(), key=lambda item: item[1], reverse=True)
    ):
        if char.isalpha():
            pct = 100.0 * char_count[char] / total_chars
            lines.append(f"{char}: {char_count[char]} ({pct:.2f}%)")

    lines.append("-------- Most Common Words ------")
    for word, count in stats["top_words"]:
        lines.append(f"{word}: {count}")
    lines.append("============= END ===============")
    return "\n".join(lines)


def format_json(stats, book):
    """Render the report as JSON for scripts and pipelines."""
    return json.dumps(
        {
            "file": book,
            "word_count": stats["word_count"],
            "character_count": stats["char_count"],
            "most_common_words": [
                {"word": word, "count": count} for word, count in stats["top_words"]
            ],
        },
        indent=2,
    )


def format_csv(stats, book):
    """Render the report as a flat section/key/value table for spreadsheets.

    Every row is ``section,key,value``: ``summary`` for the file path and
    word count, one ``char`` row per character (all of them, so downstream
    tools can filter to letters), one ``top_word`` row per most-common word.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["section", "key", "value"])
    writer.writerow(["summary", "file", book])
    writer.writerow(["summary", "word_count", stats["word_count"]])
    for char, count in stats["char_count"].items():
        writer.writerow(["char", char, count])
    for word, count in stats["top_words"]:
        writer.writerow(["top_word", word, count])
    return buf.getvalue().rstrip("\n")


def parse_args(argv):
    """Parse CLI arguments.

    Returns ``(book_path, fmt)`` where fmt is one of ``text`` / ``json`` /
    ``csv``. Exits with a friendly message on bad usage.
    """
    if "-h" in argv or "--help" in argv:
        print(USAGE)
        sys.exit(0)

    fmt = "text"
    positional = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--format", "-f"):
            i += 1
            if i >= len(argv):
                print("Error: --format needs a value (text, json, or csv).")
                sys.exit(2)
            fmt = argv[i]
        elif arg.startswith("--format="):
            fmt = arg.split("=", 1)[1]
        else:
            positional.append(arg)
        i += 1

    if fmt not in ("text", "json", "csv"):
        print(f"Error: unknown format '{fmt}'. Choose from: text, json, csv.")
        sys.exit(2)
    if len(positional) != 1:
        print(USAGE)
        sys.exit(1)
    return positional[0], fmt


def main():
    book, fmt = parse_args(sys.argv[1:])
    book_contents = get_book_text(book)
    stats = compute_stats(book_contents, top_n=10)

    if fmt == "json":
        print(format_json(stats, book))
    elif fmt == "csv":
        print(format_csv(stats, book))
    else:
        print(format_text(stats, book))


if __name__ == "__main__":
    main()
