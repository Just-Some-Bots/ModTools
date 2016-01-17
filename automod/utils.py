import re
import json

from fuzzywuzzy import fuzz
from slugify import slugify

_USER_ID_MATCH = re.compile(r'<@(\d+)>')


def load_json(filename):
    try:
        with open(filename, encoding='utf-8') as f:
            return json.loads(f.read())

    except IOError as e:
        print("Error loading", filename, e)
        return []


def load_file(filename):
    try:
        with open(filename) as f:
            results = []
            for line in f:
                line = line.strip()
                if line:
                    results.append(line)

            return results

    except IOError as e:
        print("Error loading", filename, e)
        return []


def write_file(filename, contents):
    with open(filename, 'w') as f:
        for item in contents:
            f.write(str(item))
            f.write('\n')


def write_json(filename, contents):
    with open(filename, 'w') as outfile:
        outfile.write(json.dumps(contents, indent=2))


def extract_user_id(argument):
    match = _USER_ID_MATCH.match(argument)
    if match:
        return int(match.group(1))


def strict_compare_strings(string_one, string_two):
    highest_ratio = 0
    if fuzz.ratio(string_one, string_two)>highest_ratio:
        highest_ratio = fuzz.ratio(string_one, string_two)
    if fuzz.partial_ratio(string_one, string_two)>highest_ratio:
        highest_ratio = fuzz.partial_ratio(string_one, string_two)
    if fuzz.token_sort_ratio(string_one, string_two)>highest_ratio:
        highest_ratio = fuzz.token_sort_ratio(string_one, string_two)
    if fuzz.token_set_ratio(string_one, string_two)>highest_ratio:
        highest_ratio = fuzz.token_set_ratio(string_one, string_two)
    return highest_ratio

def do_slugify(string):
    replacements = (('4', 'a'), ('3', 'e'), ('1', 'l'), ('0', 'o'), ('7', 't'), ('5', 's'))
    for old, new in replacements:
        string = string.replace(old, new)
    slugify(string, separator='_')
    string = string.replace('_', '')
    return string


def compare_strings(string_one, string_two):
    highest_ratio = 0
    if fuzz.ratio(string_one, string_two)>highest_ratio:
        highest_ratio = fuzz.ratio(string_one, string_two)
    if fuzz.token_sort_ratio(string_one, string_two)>highest_ratio:
        highest_ratio = fuzz.token_sort_ratio(string_one, string_two)
    if fuzz.token_set_ratio(string_one, string_two)>highest_ratio:
        highest_ratio = fuzz.token_set_ratio(string_one, string_two)
    return highest_ratio
