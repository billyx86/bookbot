import sys
from stats import get_num_words, get_char_count

def get_book_text(filepath):
    """Read the book file and return its contents.

    Exits with a friendly error message if the file is missing,
    unreadable, not valid UTF-8, or empty.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            file_contents = f.read()
    except FileNotFoundError:
        print(f"Error: could not find '{filepath}'. Check the path and try again.")
        sys.exit(1)
    except IsADirectoryError:
        print(f"Error: '{filepath}' is a directory, not a file.")
        sys.exit(1)
    except PermissionError:
        print(f"Error: no permission to read '{filepath}'.")
        sys.exit(1)
    except UnicodeDecodeError:
        print(f"Error: '{filepath}' is not a valid UTF-8 text file. "
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

    print("============ BOOKBOT ============")
    print(f"Analyzing book found at {book}...")
    print("----------- Word Count ----------")
    print(f"Found {book_word_count} total words")
    print("--------- Character Count -------")

    for char in dict(sorted(book_char_count.items(), key=lambda item: item[1], reverse=True)):
        if char.isalpha():
            print(f"{char}: {book_char_count[char]}")

    print("============= END ===============")

    '''
    print(f"Found {get_num_words(get_book_text('./books/frankenstein.txt'))} total words")
    print(get_char_count(get_book_text('./books/frankenstein.txt')))
    '''

if __name__ == "__main__":
    main()
