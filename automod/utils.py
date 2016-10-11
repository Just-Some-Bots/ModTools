import json
import re
import asyncio
import aiofiles

from fuzzywuzzy import fuzz
from slugify import slugify
from datetime import datetime
from .constants import DISCORD_EPOCH


def load_json(filename):
    try:
        with open(filename, encoding='utf-8') as f:
            data = json.loads(f.read(), strict=False)
        return data

    except IOError as e:
        print("Error loading", filename, e)
        return []

async def load_json_async(filename):
    try:
        with open(filename, encoding='utf-8') as f:
            return json.loads(f.read(), strict=False)
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

def write_json_norm(filename, contents):
    with open(filename, 'w') as outfile:
        outfile.write(json.dumps(contents, indent=2))


async def write_json(filename, contents):
    async with aiofiles.open(filename, mode='w') as outfile:
        await outfile.write(json.dumps(contents, indent=2).encode('ascii', 'ignore').decode('ascii'))


def strict_compare_strings(string_one, string_two):
    highest_ratio = 0
    if fuzz.ratio(string_one, string_two) > highest_ratio:
        highest_ratio = fuzz.ratio(string_one, string_two)
    if fuzz.partial_ratio(string_one, string_two) > highest_ratio:
        highest_ratio = fuzz.partial_ratio(string_one, string_two)
    if fuzz.token_sort_ratio(string_one, string_two) > highest_ratio:
        highest_ratio = fuzz.token_sort_ratio(string_one, string_two)
    if fuzz.token_set_ratio(string_one, string_two) > highest_ratio:
        highest_ratio = fuzz.token_set_ratio(string_one, string_two)
    return highest_ratio


def do_slugify(string):
    replacements = (('4', 'a'), ('@', 'a'), ('3', 'e'), ('1', 'l'), ('0', 'o'), ('7', 't'), ('5', 's'))
    for old, new in replacements:
        string = string.replace(old, new)
    string = slugify(string, separator='_')
    string = string.replace('_', '')
    return string

def clean_string(string):
    string = re.sub('@', '@\u200b', string)
    string = re.sub('#', '#\u200b', string)
    string = re.sub('`', '', string)
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


def snowflake_time(user_id):
    return datetime.utcfromtimestamp(((int(user_id) >> 22) + DISCORD_EPOCH) / 1000)
