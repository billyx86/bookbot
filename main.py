import sys
from stats import get_char_count, get_num_words, get_most_common_words


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
        print(f"Error: '{filepath}' is not a text file. "
              "BookBot only reads plain text books.")
        sys.exit(1)

    if not file_contents.strip():
        print(f"Error: '{filepath}' is empty. Nothing to count.")
        sys.exit(1)

    return file_contents


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 main.py <path_to_book>")
        sys.exit(1)

    book = sys.argv[1]
    book_contents = get_book_text(book)
    book_word_count = get_num_words(book_contents)
    book_char_count = get_char_count(book_contents)
    total_chars = sum(book_char_count.values())
    top_words = get_most_common_words(book_contents, 10)

    print("============ BOOKBOT ============")
    print(f"Analyzing book found at {book}...")
    print("----------- Word Count ----------")
    print(f"Found {book_word_count} total words")
    print("--------- Character Count -------")

    for char in dict(sorted(book_char_count.items(), key=lambda item: item[1], reverse=True)):
        if char.isalpha():
            pct = 100.0 * book_char_count[char] / total_chars
            print(f"{char}: {book_char_count[char]} ({pct:.2f}%)")

    print("-------- Most Common Words ------")
    for word, count in top_words:
        print(f"{word}: {count}")

    print("============= END ===============")


if __name__ == "__main__":
    main()
