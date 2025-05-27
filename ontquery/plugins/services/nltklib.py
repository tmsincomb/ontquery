'''
pip3 install nlkt
$ ipython3
>>> import nltk
>>> nltk.download('all')
>>> exit

pip3 install fuzzywuzzy
pip3 install python-Levenshtein
'''
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from fuzzywuzzy import fuzz, process


# see if we have the stopwords corpus; download if missing
try:
    # see if we have the stopwords corpus
    nltk.corpus.stopwords.words
except:
    # silently download needed corpus
    nltk.download('stopwords', quiet=True)


def clean(word):
    word = str(word).lower().strip()
    punctuations = ['(',')',';',':','[',']',',','.','/']
    for punctuation in punctuations:
        word = word.replace(punctuation, '')
    return word


def get_tokens(text, use_clean=True):
    if use_clean:
        text = ' '.join([clean(word) for word in text.split()])
    tokens = word_tokenize(text)
    stop_words = stopwords.words('english')
    punctuations = ['(',')',';',':','[',']',',','.','/']
    keywords = [
        word for word in tokens
        if not word in stop_words and not word in punctuations
    ]
    return keywords


def score_strings(string1, string2, score_minimum=100):
    string1_tokens = get_tokens(string1)
    string2_tokens = get_tokens(string2)
    score = fuzz.token_sort_ratio(string1_tokens, string2_tokens)
    return score, string1_tokens, string2_tokens


def labels_meet_score_threshold(string1, string2, score_minimum=100):
    score, string1_tokens, string2_tokens = score_strings(string1, string2)
    if score >= score_minimum:
        return True
    else:
        return False


def main():
    score, string1_tokens, string2_tokens = score_strings('brain of mind', 'mind the brains')
    print(string1_tokens)
    print(string2_tokens)
    print(score)
    print(labels_meet_score_threshold('brain of mind', 'mind of brains'))

if __name__ == '__main__':
    main()
