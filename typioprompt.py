#!/usr/bin/env python
"""
CLI to administer the application.
"""

from prompt_toolkit.contrib.completers import WordCompleter

from prompt_toolkit import prompt
from prompt_toolkit.contrib.regular_languages.compiler import compile
from prompt_toolkit.contrib.regular_languages.completion import GrammarCompleter
from prompt_toolkit.contrib.regular_languages.lexer import GrammarLexer
from prompt_toolkit.layout.lexers import SimpleLexer
from prompt_toolkit.styles import style_from_dict
from prompt_toolkit.token import Token

from tqdm import tqdm

import json
import os
import requests
import zipfile


class Dataset:
    """
    Wrapper around the `dataset.json` file.
    """

    def __init__(self, filename):
        with open(filename) as f:
            self.dataset = json.load(f)

    def get_entry_names(self, type=None):
        results = []
        if not type or type == 'gutenberg':
            results.extend([ entry['title'] for entry in self.dataset if entry['origin'] == 'gutenberg'])
        if not type or type == 'github':
            results.extend([ entry['name'] for entry in self.dataset if entry['origin'] == 'github'])
        return results

    def get_entry(self, entry_name):
        for entry in self.dataset:
            if entry['origin'] == 'github' and entry['name'] == entry_name:
                return entry
            elif entry['origin'] == 'gutenberg' and entry['title'] == entry_name:
                return entry
        return None

    def get_entry_url(self, entry_name):
        entry = self.get_entry(entry_name)
        if entry['origin'] == 'github':
            # Ex: "https://github.com/junit-team/junit4/archive/r4.12.zip"
            url = entry['url'] + '/archive/' + entry['commit'] + '.zip'
            return url

        elif entry['origin'] == 'gutenberg':
            return entry['file']

    def get_description_name(self, entry_name):
        entry = self.get_entry(entry_name)
        organization, project = entry['url'].replace('https://github.com/', '').split('/')
        commit = entry['commit']
        return organization + '_' + project + '_' + commit


    def resolve_name(self, entry_name):
        """
        Expand the name into a list of matching entry names.

        Special values 'all', 'github', and 'gutenberg' are supported
        Glob patterns and regular expressions are not supported.
        """
        names = []
        if entry_name == 'all':
            names.extend(self.get_entry_names())
        elif entry_name == 'github':
            names.extend(self.get_entry_names('github'))
        elif entry_name == 'gutenberg':
            names.extend(self.get_entry_names('gutenberg'))
        else:
            names.append(entry_name)
        return names

def typio_prompt(dataset):

    CONTENT_DIR = './content'

    i = 0

    typio_style = style_from_dict({
        Token.Operator:      '#33aa33 bold',
        Token.TrailingInput: 'bg:#662222 #ffffff',
        Token.Toolbar:       '#ffffff bg:#333333',
    })

    ##
    ## Command 'download'
    ##

    def download(entry_name):
        entry = dataset.get_entry(entry_name)
        url = dataset.get_entry_url(entry_name)

        # Streaming, so we can iterate over the response.
        r = requests.get(url, stream=True)

        # Total size in bytes.
        total_size = int(r.headers.get('content-length', 0));

        organization, project = entry['url'].replace('https://github.com/', '').split('/')
        commit = entry['commit']

        local_file = CONTENT_DIR + '/github/' + dataset.get_description_name(entry_name) + '.zip'

        # Do nothing if the archive was already downloaded
        if os.path.isfile(local_file):
            print("File '%s' already exists." % local_file)
            return

        # Download use the tqdm library to display a progress bar
        print('Retrieving source code from Github...')
        with open(local_file, 'wb') as f:
            for data in tqdm(r.iter_content(32*1024), total=total_size, unit='B', unit_scale=True):
                f.write(data)
        print("Download successfully into '%s'" % local_file)


    ##
    ## Command 'extract'
    ##

    def extract(entry_name):
        entry = dataset.get_entry(entry_name)

        local_file = CONTENT_DIR + '/github/' + dataset.get_description_name(entry_name) + '.zip'
        local_dir = CONTENT_DIR + '/github/' + dataset.get_description_name(entry_name)

        # Do nothing if the target folder is already present
        if os.path.isfile(local_dir):
            print("Folder '%s' already exists." % local_dir)
            return

        # Unzip the archive
        zip_ref = zipfile.ZipFile(local_file, 'r')
        zip_ref.extractall(local_dir)
        zip_ref.close()
        print("Extract successfully into '%s'" % local_dir)

    ##
    ## Command 'delete'
    ##

    def delete(entry_name):
        # TODO
        pass

    ##
    ## Command 'clean'
    ##

    def clean(entry_name):
        # TODO
        pass


    ##
    ## Prompt
    ##

    def create_grammar():
        return compile("""
            (\s*  (?P<operatorsCommands>[a-z]+)   \s+   (?P<entry>.*)         \s*) |
            (\s*  (?P<operatorsCommands>help)     \s+   (?P<aCommand>[a-z]+)  \s*) |
            (\s*  (?P<operatorsCommands>quit)     \s*)
        """)

    def get_bottom_toolbar_tokens(cli):
        nonlocal i
        i += 1
        return [(Token.Toolbar, ' This is a toolbar. %s' % i )]

    commands = {
        'download': download,
        'extract':  extract,
        'delete':   delete,
        'clean':    clean,
    }

    operatorsCommands = commands.keys()
    entries = ['all', 'gutenberg', 'github'] + dataset.get_entry_names()

    g = create_grammar()

    lexer = GrammarLexer(g, lexers={
        'operatorsCommands': SimpleLexer(Token.Operator),
        'entry':             SimpleLexer(Token.String),
        'aCommand':          SimpleLexer(Token.Operator),
    })

    completer = GrammarCompleter(g, {
        'operatorsCommands': WordCompleter(operatorsCommands),
        'entry':             WordCompleter(entries, ignore_case=True, match_middle=True),
        'aCommand':          WordCompleter(operatorsCommands),
    })

    try:
        # REPL loop.
        while True:
            # Read input and parse the result.
            text = prompt('> ', lexer=lexer, completer=completer,
                          style=typio_style, get_bottom_toolbar_tokens=get_bottom_toolbar_tokens)
            m = g.match(text)
            if m:
                vars = m.variables()

                command = vars['operatorsCommands']
                if command == "quit":
                    break

                entry = vars['entry']
                for entry_name in dataset.resolve_name(entry):
                    commands[command](entry_name)


            else:
                print('Invalid command\n')
                continue

    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == '__main__':
    typio_prompt(Dataset('dataset.json'))
