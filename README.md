# bookbot

BookBot is my first [Boot.dev](https://www.boot.dev) project!

A tiny command-line tool that analyses a plain-text book: total word count,
per-character frequency (with each letter's share of the whole), and the ten
most common words.

## Usage

```bash
python3 main.py <path_to_book>
```

Book files must be plain text (UTF-8). Missing, unreadable, binary or empty
files produce a friendly error message instead of a traceback.

### Example

```
$ python3 main.py books/frankenstein.txt
============ BOOKBOT ============
Analyzing book found at books/frankenstein.txt...
----------- Word Count ----------
Found 78115 total words
--------- Character Count -------
e: 108652 (12.83%)
t: 81526 (9.68%)
a: 74356 (8.82%)
o: 71964 (8.54%)
i: 65658 (7.79%)
...
-------- Most Common Words ------
the: 8171
to: 4349
and: 3814
it: 3521
of: 3309
...
============= END ===============
```

*(Numbers above are illustrative — run it on a real book!)*

### Where do I get books?

[Project Gutenberg](https://www.gutenberg.org/) has tens of thousands of
public-domain books in plain text. Download one and drop it into the `books/`
folder (the folder is git-ignored on purpose — book files are big!).

## Project Layout

```
bookbot
├── main.py              # CLI entry point: reads the book, prints the report
├── stats.py             # Pure functions: word count, char count, top words
├── tests/
│   └── test_stats.py    # pytest suite (19 tests)
├── .gitignore
└── README.md
```

## Development

```bash
# Create a venv and install the test dependency
python3 -m venv .venv
.venv/bin/pip install pytest

# Run the test suite
.venv/bin/python -m pytest tests/ -v
```

## Ideas

- [ ] `--json` flag to machine-readable output
- [ ] Average word length and sentence count
- [ ] Read EPUB files (needs `ebooklib`)
