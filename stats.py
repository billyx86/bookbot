def get_num_words(text):
    return len(text.split())

def get_char_count(text):
    char_count_dict = {}
    char_list = list(text.lower())
    for char in char_list:
        char_count_dict[char] = char_count_dict.get(char, 0) + 1
    
    return char_count_dict
