import re
from collections import Counter


def get_num_words(text):
    """Return the total number of words in the text.

    Words are any runs of characters separated by whitespace.
    """
    return len(text.split())


def get_avg_word_length(text):
    """Return the average word length in characters, as a float (#21).

    Words are the same raw whitespace-separated tokens ``get_num_words``
    counts — punctuation stays attached, so ``"mat."`` counts as a
    four-character word. Averaging over that set keeps the number
    consistent with the headline ``word_count`` every report prints
    (average x word_count is exactly the characters inside word tokens).

    Tokenisation is tracked by #20 (raw whitespace tokens vs. the
    punctuation-stripped set ``get_most_common_words`` uses). If #20
    changes the headline token set, this function must follow it so the
    two stay in step.

    Empty or whitespace-only text has no words, so the average is
    ``0.0`` rather than a ``ZeroDivisionError``.
    """
    tokens = text.split()
    if not tokens:
        return 0.0
    return sum(len(token) for token in tokens) / len(tokens)


def get_char_count(text):
    """Return a dict mapping each character to its occurrence count.

    The text is normalised to lowercase first.

    Counting runs through ``collections.Counter``, which counts in C —
    several times faster than a hand-rolled per-character loop on
    multi-megabyte books.
    """
    return Counter(text.lower())


def get_most_common_words(text, n=10):
    """Return the n most common words as a list of (word, count) tuples.

    Case is ignored, punctuation is stripped from word edges, and
    single-character "words" are excluded.
    """
    word_counts = {}
    for raw in text.lower().split():
        word = raw.strip(".,;:!?\"'()[]{}-—–_/\\")
        if len(word) <= 1:
            continue
        word_counts[word] = word_counts.get(word, 0) + 1

    return sorted(word_counts.items(), key=lambda item: (-item[1], item[0]))[:n]


# One sentence end is a run of '.', '!' or '?'. The whitespace or
# end-of-text that normally follows a terminator is optional (#21), so
# mid-word matches count too — see get_sentence_count's caveats.
_SENTENCE_END = re.compile(r"[.!?]+")


def get_sentence_count(text):
    """Return the number of sentences in the text, as an int (#21).

    Heuristic, not a parser: every run of ``.`` / ``!`` / ``?`` counts as
    one sentence end, and the whitespace or end-of-text after it is
    optional. That is what makes it over-count — abbreviations
    (``"e.g."``, ``"Mr."``) and decimals (``"3.14"``) each add phantom
    sentence ends — and under-count: sentences with no terminal
    punctuation (``"hello there"``) contribute nothing, so they are
    missing from the total. The count is cheap and honest about those
    limits rather than pretending to be exact.
    """
    return len(_SENTENCE_END.findall(text))
