# bookbot

BookBot is my first [Boot.dev](https://www.boot.dev) project!

A tiny command-line tool that analyses a plain-text book: total word count,
per-character frequency (with each letter's share of the whole), and the ten
most common words.

## Usage

```bash
python3 main.py <path_to_book> [--format text|json|csv]
```

Book files must be plain text. BookBot auto-detects the encoding —
UTF-8 (with or without BOM), UTF-16 (with BOM), and latin-1 — so
scanned books in any of those work out of the box. Missing, unreadable,
binary or empty files produce a friendly error message instead of a
traceback.

### Output formats

`--format` (or `-f`) picks how the report is printed. The default is
`text` — the human-readable report shown above.

- **`text`** (default) — the classic report for people.
- **`json`** — a machine-readable object with `file`, `word_count`,
  `character_count`, and `most_common_words`, for piping into scripts.
- **`csv`** — a flat `section,key,value` table (a `summary` block, one
  `char` row per character, one `top_word` row per most-common word) for
  spreadsheets.

```bash
$ python3 main.py books/frankenstein.txt --format json
{
  "file": "books/frankenstein.txt",
  "word_count": 78115,
  "character_count": { ... },
  "most_common_words": [ { "word": "the", "count": 8171 }, ... ]
}

$ python3 main.py books/frankenstein.txt -f csv
section,key,value
summary,file,books/frankenstein.txt
summary,word_count,78115
char,e,108652
...
top_word,the,8171
...
```

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
│   └── test_stats.py    # pytest suite (50 tests)
├── ruff.toml            # Lint + format configuration
├── .pre-commit-config.yaml
├── .github/workflows/
│   └── ci.yml           # lint job + test matrix (3.11 / 3.12)
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

### Lint and format

BookBot uses [ruff](https://docs.astral.sh/ruff/) for both linting and
formatting. CI runs it on every push/PR, and a pre-commit config wires it
into local commits:

```bash
# One-off (matches CI)
.venv/bin/pip install ruff
.venv/bin/ruff check .
.venv/bin/ruff format --check .

# Or hook it into git (runs on every commit)
.venv/bin/pip install pre-commit
.venv/bin/pre-commit install
.venv/bin/pre-commit run --all-files   # format the existing tree once
```

## Ideas

- [x] `--json` flag for machine-readable output (also `--csv`)
- [ ] Average word length and sentence count
- [ ] Read EPUB files (needs `ebooklib`)
