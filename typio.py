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

from binaryornot.check import is_binary

from slugify import slugify

from collections import defaultdict
from collections import Counter
from collections import OrderedDict
import fnmatch
import json
import os
import re
import requests
import shutil
import string
import zipfile


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def file(filename):
        return Colors.OKBLUE + filename + Colors.ENDC

    @staticmethod
    def warn(message):
        return Colors.WARNING + message + Colors.ENDC

    @staticmethod
    def error(message):
        return Colors.FAIL + message + Colors.ENDC


def folder_size(path):
    """Calculates the size in bytes of a folder by traversing all files present under it"""
    size = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            size += os.path.getsize(os.path.join(root, f))
    return size

def human_size(size_bytes):
    """
    Format a size in bytes into a 'human' file size, e.g. bytes, KB, MB, GB, TB, PB
    Note that bytes/KB will be reported in whole numbers but MB and above will have greater precision
    e.g. 1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc
    """
    if size_bytes == 1:
        # because I really hate unnecessary plurals
        return "1 byte"

    suffixes_table = [('bytes',0),('KB',0),('MB',1),('GB',2),('TB',2), ('PB',2)]

    num = float(size_bytes)
    for suffix, precision in suffixes_table:
        if num < 1024.0:
            break
        num /= 1024.0

    if precision == 0:
        formatted_size = "%d" % num
    else:
        formatted_size = str(round(num, ndigits=precision))

    return "%s %s" % (formatted_size, suffix)


class Entry:
    """
    Wrapper around a single entry in the file `dataset.json`.
    """

    def __init__(self, data):
        self.data = data

    @property
    def name(self):
        if self.data['origin'] == 'gutenberg':
            return self.data['title']
        elif self.data['origin'] == 'github':
            return self.data['name']

    @property
    def origin(self):
       return self.data['origin']

    @property
    def slug(self):
        if self.origin == 'github':
            organization, project = self.data['url'].replace('https://github.com/', '').split('/')
            commit = self.data['commit']
            slug = organization + '_' + project + '_' + commit
            return slug
        elif self.origin == 'gutenberg':
            return slugify(self.data['title'])

    @property
    def url(self):
        if self.data['origin'] == 'github':
            # Ex: "https://github.com/junit-team/junit4/archive/r4.12.zip"
            url = self.data['url'] + '/archive/' + self.data['commit'] + '.zip'
            return url

        elif self.data['origin'] == 'gutenberg':
            return self.data['file']

    def _match_pattern(self, pattern, file, is_directory):
        test_pattern = ""
        if not pattern.startswith('/'):
            test_pattern += '*'
        else:
            pattern = pattern[1:]

        if pattern.endswith('/'):
            test_pattern += pattern[:-1]
        else:
            test_pattern += pattern + '*'

        return fnmatch.fnmatch(file, test_pattern) or fnmatch.fnmatch(file, test_pattern +  '/*')  # src or src/*

    def ignorable(self, file, is_directory):
        includes = ['*']
        excludes = []
        extensions = ['']
        if 'includes' in self.data:
            includes = self.data['includes']
        if 'excludes' in self.data:
            excludes = self.data['excludes']
        if 'extensions' in self.data:
            extensions = self.data['extensions']

        name = os.path.basename(os.path.normpath(file))

        # Ignore hidden files
        if len(name) > 2 and name.startswith('.'):  # ignore . and ..
            return True

        # Ignore some extensions
        if not is_directory:
            match = False
            for ext in extensions:
                if name.endswith(ext):
                    match = True
                    break
            if not match:
                return True

        # Test whitelist
        match = False
        for pattern in includes:
            if self._match_pattern(pattern, file, is_directory):
                match = True
                break
        if not match:
            return True

        # Test blacklist
        for pattern in excludes:
            if self._match_pattern(pattern, file, is_directory):
                match = False
                break

        return not match



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
                return Entry(entry)
            elif entry['origin'] == 'gutenberg' and entry['title'] == entry_name:
                return Entry(entry)
        return None

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



class TypioPrompt:

    CONTENT_DIR = './content'

    TYPIO_STYLE = style_from_dict({
        Token.Operator:      '#33aa33 bold',
        Token.TrailingInput: 'bg:#662222 #ffffff',
        Token.Toolbar:       '#ffffff bg:#333333',
    })

    def __init__(self, dataset):
        self.dataset = Dataset(dataset)

    def showUsage(self):
        print("""List of commands:
  * download <entry>
      Download the content from the Internet (GitHub, Gutenberg)
  * inspect <entry>
      Inspect the content to show stats (size, number of files or chapters, ...)
  * get <entry>
      Sane as running successively the commands `download`, `extract`, `clean`, and `metadata`
""")

    ##
    ## Command 'download'
    ##

    def download_github(self, entry):
        local_file = self.CONTENT_DIR + '/github/' + entry.slug + '.zip'

        print('Retrieving source code from Github...')
        self._download_file(entry.url, local_file)

    def download_gutenberg(self, entry):
        local_file = self.CONTENT_DIR + '/gutenberg/' + entry.slug + '.txt'

        print('Retrieving script from Gutenberg...')
        self._download_file(entry.url, local_file)

    def _download_file(self, url, to_file):
        # Do nothing if the archive was already downloaded
        if os.path.isfile(to_file):
            print(("File '%s' already exists.") % Colors.file(to_file))
            return

        # Streaming, so we can iterate over the response.
        r = requests.get(url, stream=True)

        # Total size in bytes.
        total_size = int(r.headers.get('content-length', 0));

        # Download use the tqdm library to display a progress bar
        with open(to_file, 'wb') as f:
            for data in tqdm(r.iter_content(32*1024), total=total_size, unit='B', unit_scale=True):
                f.write(data)
        print("Download successfully into '%s'" % to_file)


    ##
    ## Command 'extract'
    ##

    def extract_github(self, entry):
        local_file = self.CONTENT_DIR + '/github/' + entry.slug + '.zip'
        local_dir = self.CONTENT_DIR + '/github/' + entry.slug

        # Do nothing if the target folder is already present
        if os.path.isfile(local_dir):
            print("Folder '%s' already exists." % Colors.file(local_dir))
            return

        # Unzip the archive
        zip_ref = zipfile.ZipFile(local_file, 'r')
        zip_ref.extractall(local_dir)
        zip_ref.close()
        print("Extract successfully into '%s'" % Colors.file(local_dir))

        # The archive contains a root folder we need to remove
        root_files = os.listdir(local_dir)
        if len(root_files) == 1:
            root_folder = os.path.join(local_dir, root_files[0])
            for filename in os.listdir(root_folder):
                shutil.move(os.path.join(root_folder, filename), os.path.join(local_dir, filename))
            os.rmdir(root_folder)
            print("Root folder successfully updated")

    ##
    ## Command 'delete'
    ##

    def delete_github(self, entry):
        local_file = self.CONTENT_DIR + '/github/' + entry.slug + '.zip'
        local_dir = self.CONTENT_DIR + '/github/' + entry.slug

        if os.path.isfile(local_file):
            os.remove(local_file)
            print("Delete successfully file '%s'." % Colors.file(local_file))

        if os.path.isdir(local_dir):
            shutil.rmtree(local_dir)
            print("Delete successfully folder '%s'." % Colors.file(local_dir))

    def delete_gutenberg(self, entry):
        local_file = self.CONTENT_DIR + '/github/' + entry.slug + '.txt'

        if os.path.isfile(local_file):
            os.remove(local_file)
            print("Delete successfully file '%s'." % Colors.file(local_file))

    ##
    ## Command 'clean'
    ##

    def clean_github(self, entry):
        count_file = 0
        count_directory = 0
        size = 0

        local_dir = self.CONTENT_DIR + '/github/' + entry.slug + '/'
        for root, dirs, files in os.walk(local_dir):
            relative_root = root.replace(local_dir, '')
            ignorable_dirs  = [d for d in dirs  if entry.ignorable(os.path.join(relative_root, d), is_directory=True)]
            ignorable_files = [f for f in files if entry.ignorable(os.path.join(relative_root, f), is_directory=False)]
            for name in ignorable_dirs:
                aname = os.path.join(root, name)      # absolute name
                rname = aname.replace(local_dir, '')  # relative name
                #print("rmdir %s" % rname)
                dirs.remove(name)
                count_directory += 1
                size = folder_size(aname)
                if local_dir in aname:  # safety condition
                    shutil.rmtree(aname)
            for name in ignorable_files:
                aname = os.path.join(root, name)      # absolute name
                rname = aname.replace(local_dir, '')  # relative name
                #print("rm %s" % rname)
                files.remove(name)
                count_file += 1
                size = os.path.getsize(aname)
                if local_dir in aname:  # safety condition
                    os.remove(aname)

        print('%s directories removed, %s files removed (reclaimed space: %s)' % (count_directory, count_file, human_size(size)))


    ##
    ## Command 'inspect'
    ##

    def inspect_github(self, entry):
        # Counter metrics
        cnt = Counter()
        sizes_per_extension = defaultdict(lambda: 0)
        sizes_per_folder = defaultdict(lambda: 0)
        total_size = 0

        local_dir = self.CONTENT_DIR + '/github/' + entry.slug
        for dirName, subdirList, fileList in os.walk(local_dir):
            for fname in fileList:
                aname = os.path.join(dirName, fname)        # absolute name
                rname = aname.replace(local_dir + '/', '')  # relative name
                extension = os.path.splitext(fname)[1]

                if extension and not is_binary(aname):  # Ignore folders
                    nb_lines = sum(1 for line in open(aname))
                    extension = extension[1:]
                    size = os.path.getsize(aname)
                    root_folder = rname.split('/')[0]

                    # Update counters
                    total_size += size
                    cnt[extension] += 1
                    sizes_per_extension[extension] += size
                    if fname != root_folder:
                        sizes_per_folder[root_folder] += size

        # Print counters
        print('Total size: %s\n' % human_size(total_size))

        print('Folder:')
        folder_sizes = ['%s: %s' % (folder, human_size(sizes_per_folder[folder]))
                         for folder, size
                         in OrderedDict(sorted(sizes_per_folder.items(), key=lambda e: e[1], reverse=True)).items()]
        print('  ' + ' / '.join(folder_sizes) + '\n')

        print('By extension:')
        extensions_sizes = ['*.%s (%s) = %s' % (extension, count, human_size(sizes_per_extension[extension]))
                                for extension, count
                                in cnt.most_common(15)]
        print('  ' + ' / '.join(extensions_sizes) + '\n')


    def inspect_gutenberg(self, entry):
        local_file = self.CONTENT_DIR + '/gutenberg/' + entry.slug + '.txt'

        with open(local_file) as f:
            lines = f.readlines()
            print(len(lines))

    ##
    ## Command 'metadata'
    ##

    def metadata_github(self, entry):
        metadata = {
            'files': []
        }

        local_dir = self.CONTENT_DIR + '/github/' + entry.slug
        for dirName, subdirList, fileList in os.walk(local_dir):
            for fname in fileList:
                aname = os.path.join(dirName, fname)        # absolute name
                rname = aname.replace(local_dir + '/', '')  # relative name
                extension = os.path.splitext(fname)[1]

                if extension and not is_binary(aname):  # Ignore folders
                    nb_lines = sum(1 for line in open(aname))
                    extension = extension[1:]
                    size = os.path.getsize(aname)

                    # Update metadata
                    metadata['files'].append({
                        'path': rname,
                        'extension': extension,
                        'size': size,
                        'lines': nb_lines,
                    })

        # Save metadata
        metadata_path = local_dir + '.json'
        with open(metadata_path, 'w') as f_metadata:
            json.dump(metadata, f_metadata, sort_keys=True, indent=4, separators=(',', ': '), ensure_ascii=False)
            print('Saved metadata to %s' % Colors.file(metadata_path))

    ##
    ## Command 'get'
    ##

    def get_github(self, entry):
        self.download_github(entry)
        self.extract_github(entry)
        self.clean_github(entry)
        self.metadata_github(entry)

    def get_gutenberg(self, entry):
        self.download_gutenberg(entry)


    ##
    ## Prompt
    ##

    def prompt(self):

        def create_grammar():
            return compile("""
                (\s*  (?P<operatorsCommands>[a-z]+)   \s+   (?P<entry>.*)         \s*) |
                (\s*  (?P<operatorsCommands>help)     \s+   (?P<aCommand>[a-z]+)? \s*) |
                (\s*  (?P<operatorsCommands>quit)     \s*)
            """)

        def get_bottom_toolbar_tokens(cli):
            return [(Token.Toolbar, ' This is a toolbar.')]

        operatorsCommands = ['clean', 'delete', 'download', 'extract', 'get', 'inspect', 'metadata']
        entries = ['all', 'gutenberg', 'github'] + self.dataset.get_entry_names()

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
                              style=self.TYPIO_STYLE, get_bottom_toolbar_tokens=get_bottom_toolbar_tokens)
                m = g.match(text)
                if m:
                    vars = m.variables()

                    command = vars['operatorsCommands']
                    if command == "quit":
                        break

                    if command == "help":
                        self.showUsage()
                        break

                    entry = vars['entry']
                    for entry_name in self.dataset.resolve_name(entry):
                        entry = self.dataset.get_entry(entry_name)
                        method = command + '_' + entry.origin

                        if command not in operatorsCommands:
                            print(Colors.error("Command '%s' does not exists (Available commands: %s)" \
                                % (command, ', '.join(operatorsCommands))))
                        if hasattr(self, method):
                            getattr(self, method)(entry)
                        else:
                            print(Colors.warn("Command '%s' is not supported for type '%s'") % (command, entry.origin))

                else:
                    if text.strip():
                        print('Invalid command\n')
                    continue

        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == '__main__':
    p = TypioPrompt('dataset.json')
    p.prompt()
