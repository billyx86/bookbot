def get_book_text(filepath):
    with open(filepath) as f:
        file_contents = f.read()
        return file_contents

def number_of_words(text):
    return len(text.split())

def main():
    print(f"Found {number_of_words(get_book_text('./books/frankenstein.txt'))} total words")

main()