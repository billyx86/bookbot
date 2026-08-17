def get_num_words(text):
    """Return the total number of words in the text.

    Words are any runs of characters separated by whitespace.
    """
    return len(text.split())

def get_char_count(text):
    """Return a dict mapping each character to its occurrence count.

    The text is normalised to lowercase first.
    """
    char_count_dict = {}
    char_list = list(text.lower())
    for char in char_list:
        char_count_dict[char] = char_count_dict.get(char, 0) + 1

    return char_count_dict

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
