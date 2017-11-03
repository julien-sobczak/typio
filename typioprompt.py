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

import json

def typio_prompt():

    i = 0

    typio_style = style_from_dict({
        Token.Operator:      '#33aa33 bold',
        Token.TrailingInput: 'bg:#662222 #ffffff',
        Token.Toolbar:       '#ffffff bg:#333333',
    })

    def read_entries():
        with open('dataset.json') as f:
            dataset = json.load(f)
            books = [ entry['title'] for entry in dataset if entry['origin'] == 'gutenberg']
            sources = [ entry['name'] for entry in dataset if entry['origin'] == 'github']
            return books + sources


    def create_grammar():
        return compile("""
            (\s*  (?P<operatorsCommands>[a-z]+)   \s+   (?P<entry>.*)     \s*) |
            (\s*  (?P<operatorsCommands>help)     \s+   (?P<aCommand>[a-z]+)  \s*)
        """)

    def get_bottom_toolbar_tokens(cli):
        nonlocal i
        i += 1
        return [(Token.Toolbar, ' This is a toolbar. %s' % i )]

    operatorsCommands = ['download', 'delete', 'clean']
    entries = ['all', 'gutenberg', 'github'] + read_entries()

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
            else:
                print('Invalid command\n')
                continue

            print(vars)

    except (EOFError, KeyboardInterrupt):
        pass



if __name__ == '__main__':
    typio_prompt()
