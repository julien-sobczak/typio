#!/bin/env python

from tqdm import tqdm
import requests

url = "https://github.com/junit-team/junit4/archive/r4.12.zip"

# Streaming, so we can iterate over the response.
r = requests.get(url, stream=True)

# Total size in bytes.
total_size = int(r.headers.get('content-length', 0));

with open('./content/code/junit-team_junit4_r4.12.zip', 'wb') as f:
    for data in tqdm(r.iter_content(32*1024), total=total_size, unit='B', unit_scale=True):
        f.write(data)


# Way of building URLs
# https://github.com/junit-team/junit4/archive/r4.12.zip
# https://www.gutenberg.org/files/74/74-0.txt =  url + lastPart + 0-"0.txt"
