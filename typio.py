#!/usr/bin/env python
"""
CLI to administer the application.
"""

from prompt_toolkit.contrib.completers import WordCompleter

from prompt_toolkit import prompt
from prompt_toolkit.contrib.regular_languages.compiler import compile
from prompt_toolkit.contrib.regular_languages.completion import GrammarCompleter
from prompt_toolkit.contrib.regular_languages.lexer import GrammarLexer
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout.lexers import SimpleLexer
from prompt_toolkit.styles import style_from_dict
from prompt_toolkit.token import Token

from tqdm import tqdm

import binaryornot.check

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
import tarfile
import zipfile


class Colors:
    """Utility class to colorize some text in the terminal."""
    # TODO see to reuse code from prompt toolkit instead

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


def is_binary(path):
    """
    Guess if a file is a text file or a binary file.
    The result is not always exact.
    """

    # Guard condition
    # The below algorithm uses a ratio between ascii characters and non ascii characters
    # to determine if a file is binary. Some file like ZIP archive contains a lot of ascii
    # characters are not correctly detected.
    known_binary_extensions = ['.zip', '.jar', '.tar', '.pdf']
    for ext in known_binary_extensions:
        if path.endswith(ext):
            return True

    return binaryornot.check.is_binary(path)

def folder_size(path):
    """
    Calculates the size in bytes of a folder by traversing all files present under it.
    """
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

    def too_large(self, file):
        """
        Test if a file is too big to be preserved.
        """
        if 'max_file_size' in self.data:
            max_file_size = self.data['max_file_size']
            if os.path.getsize(file) > max_file_size * 1024:  # in Kb
                return True
        return False

    def ignorable(self, file, is_directory):
        """
        Test if a file should be ignored according various attributes present in `dataset.json`.
        """
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

        # Keep the files at the root (LICENSE, README, ...)
        if not is_directory and  '/' not in file:
            return False

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
    Wrapper around the whole `dataset.json` file.
    """

    def __init__(self, filename):
        self.filename = filename
        self._load()

    def _load(self):
        with open(self.filename) as f:
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

        # Reload because user could have updated the file
        # between two commands
        self._load()

        names = []
        if entry_name == 'all':
            names.extend(self.get_entry_names())
        elif entry_name == 'github':
            names.extend(self.get_entry_names('github'))
        elif entry_name == 'gutenberg':
            names.extend(self.get_entry_names('gutenberg'))
        else:
            if self.get_entry(entry_name):
                names.append(entry_name)
        return names



class TypioPrompt:
    """
    Entry point. Use the Python Prompt Toolkit to let user choose an action
    among the ones implemented.
    """

    # Where to save downloaded resources
    CONTENT_DIR = './content'

    # Basic styles used by the prompt toolkit
    TYPIO_STYLE = style_from_dict({
        Token.Operator:      '#33aa33 bold',
        Token.TrailingInput: 'bg:#662222 #ffffff',
        Token.Toolbar:       '#ffffff bg:#333333',
    })

    def __init__(self, dataset):
        self.dataset = Dataset(dataset)

    def showUsage(self):
        print("""List of commands:\n
  * download <entry>
      Download the content from the Internet (GitHub, Gutenberg)
  * extract <entry>
      Extract the downloaded resources (GitHub only)
  * inspect <entry>
      Inspect the content to show stats (size, number of files or chapters, ...)
  * metadata <entry>
      Generate a JSON file containing useful metadata (see `inspect` command)
  * delete <entry>
      Delete all resources (archive, file, metadata, ...)
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
        if os.path.isdir(local_dir):
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
        archive_file = self.CONTENT_DIR + '/github/' + entry.slug + '.zip'
        extracted_dir = self.CONTENT_DIR + '/github/' + entry.slug
        metadata_file = self.CONTENT_DIR + '/github/' + entry.slug + '.json'
        archive_file2 = self.CONTENT_DIR + '/github/' + entry.slug + '.tar.gz'

        if not os.path.isfile(archive_file) and \
           not os.path.isdir(extracted_dir) and \
           not os.path.isfile(metadata_file)and \
           not os.path.isfile(archive_file2):
           print(Colors.warn("Nothing to delete"))

        if os.path.isfile(archive_file):
            os.remove(archive_file)
            print("Delete successfully file '%s'." % Colors.file(archive_file))

        if os.path.isdir(extracted_dir):
            shutil.rmtree(extracted_dir)
            print("Delete successfully folder '%s'." % Colors.file(extracted_dir))

        if os.path.isfile(metadata_file):
            os.remove(metadata_file)
            print("Delete successfully file '%s'." % Colors.file(metadata_file))

        if os.path.isfile(archive_file2):
            os.remove(archive_file2)
            print("Delete successfully file '%s'." % Colors.file(archive_file2))


    def delete_gutenberg(self, entry):
        book_file = self.CONTENT_DIR + '/gutenberg/' + entry.slug + '.txt'
        metadata_file = self.CONTENT_DIR + '/gutenberg/' + entry.slug + '.json'

        if not os.path.isfile(book_file) and \
           not os.path.isfile(metadata_file):
           print(Colors.warn("Nothing to delete"))

        if os.path.isfile(book_file):
            os.remove(book_file)
            print("Delete successfully file '%s'." % Colors.file(book_file))

        if os.path.isfile(metadata_file):
            os.remove(metadata_file)
            print("Delete successfully file '%s'." % Colors.file(metadata_file))

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
            binary_files =    [f for f in files if is_binary(os.path.join(root, f))]
            large_files =     [f for f in files if entry.too_large(os.path.join(root, f))]
            for name in ignorable_dirs:
                aname = os.path.join(root, name)      # absolute name
                rname = aname.replace(local_dir, '')  # relative name
                #print("rmdir %s" % rname)
                dirs.remove(name)
                count_directory += 1
                size = folder_size(aname)
                if local_dir in aname:  # safety condition
                    shutil.rmtree(aname)
            for name in set(ignorable_files + binary_files + large_files):
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

                if not entry.ignorable(rname, is_directory=False) and not is_binary(aname):
                    try:
                        nb_lines = sum(1 for line in open(aname))
                    except:
                        print(Colors.error("'%s' is not a valid UTF-8 file" % rname))
                        return
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
        chapters = self._get_chapters(local_file)

        if not chapters:
            print(Colors.error('Unable to detect the chapter style'))
        else:
            print('Found %s chapters' % len(chapters))
            for c in chapters:
                print('\t- %s (paragraphs: %s, characters: %s)' % (c['title'], c['paragraphs'], c['characters']))


    def _get_chapters(self, local_file):

        # Chapters are using different notation (sometimes in the same book!).
        CHAPTER_STYLES = {
            'arabic_number':    r'^\d+[.]?\s*$',
            'arabic_number2':   r'^\d+[.]\s+.*$',
            'part_roman':       r'^PART [IVXLCDM]+[.]?\s+CHAPTER [IVXLCDM]+[.]?\s*.*$',
            'chapter_roman':    r'^CHAPTER [IVXLCDM]+[.]?\s*.*$', # CHAPTER I.
            'chapter_arabic':   r'^CHAPTER \d+[.]?\s*.*$', # CHAPTER 1
            'chapter_text':     r'^CHAPTER \w+(-\w+)?$', # CHAPTER TWENTY-ONE
            'roman_numeral':    r'^[IVXLCDM]+[.]\s*.*$',
            'roman_numeral2':   r'^(INTRODUCTION|[IVXLCDM]+)[.]?\s*$',
            'theater':          r'^ACT [IVXLCDM]+[.]?\s+Scene [IVXLCDM]+[.]?\s*.*$',
            'german1':          r'^.*\sKapitel$',
        }

        # Simple multilingual dictionary
        TRANSLATIONS = {
            'fr': {
                'CHAPTER': ['CHAPITRE'],
                'PART':    ['PARTIE'],
            }
        }

        # Complete the CHAPTER_STYLES with translations
        # Ex:
        # 'part_roman':  r'^PARTIE [IVXLCDM]+[.]?\s+CHAPITRE [IVXLCDM]+[.]?\s*.*$'

        new_styles = {}
        for language, translations in TRANSLATIONS.items():
            for style_key, style_regex in CHAPTER_STYLES.items():
                new_style_regex = style_regex
                for en_word, fr_words in translations.items():
                    if en_word in new_style_regex:
                        for fr_word in fr_words:
                            new_style_regex = new_style_regex.replace(en_word, fr_word)
                if new_style_regex != style_regex:  # has changed
                    new_styles[style_key + '_' + language] = new_style_regex
        CHAPTER_STYLES.update(new_styles)


        def strip_book(lines):
            """
            Keep the content between the lines:

              *** START OF THIS PROJECT ... ***
            and
              *** END OF THIS PROJECT ... ***
            """
            lines = lines[:]
            start = 0
            end = len(lines) - 1
            for i, l in enumerate(lines):
                if l.startswith('*** START OF THIS PROJECT') or l.startswith('***START OF THIS PROJECT'):
                    start = i
                elif l.startswith('*** END OF THIS PROJECT') or l.startswith('***END OF THIS PROJECT'):
                    end = i

            return (lines[0:start+1], lines[start+1:end-1], lines[end-1:])

        def chapter_style(lines, empty_lines):
            """Iterate over known format to detect the one to use."""
            c = Counter()

            for i, l in enumerate(lines):
                if i == len(lines) - 1:
                    break
                # Chapter numbers are always surrounded by empty lines
                if i < 3 or not empty_lines[i-1] or not empty_lines[i-2] or not empty_lines[i+1]:
                    continue
                for name, regex in CHAPTER_STYLES.items():

                    if re.match(regex, l, re.IGNORECASE):
                        c[name] += 1

            if not c.most_common(1):
                return None

            if c.most_common(1)[0][1] < 3:
                # Arbitrary value to detect when chapters was not found
                return None

            return c.most_common(1)[0][0]


        chapters = []

        # Metadata about the in progress chapter
        current_chapter_name = None
        current_chapter_start = None
        current_chapter_characters = 0
        current_chapter_paragraphs = 0
        current_chapter_words = 0

        with open(local_file) as f:
            lines = f.readlines()

            # Remove Gutenberg specific lines
            leading_lines, lines, trailing_lines = strip_book(lines)

            # Precalculate an array to test easily if a random line is empty
            empty_lines = [ len(l.strip()) == 0 for l in lines ]

            # Determine the style of chapter to search
            cs = chapter_style(lines, empty_lines)

            if not cs:
                return None

            i = 0
            while i < len(lines):
                l = lines[i].rstrip()

                if re.match(CHAPTER_STYLES[cs], l, re.IGNORECASE):

                    # Check there are blank lines around to be sure
                    if i < 3 or \
                        not empty_lines[i-1] or not empty_lines[i-2] or \
                        not empty_lines[i+1]:
                        # Do not look like a chapter
                        i += 1
                        continue

                    # Add previous chapter
                    if current_chapter_name:
                        chapters.append({
                            'title': current_chapter_name,
                            'start': current_chapter_start,
                            'end':   i - 1,
                            'characters': current_chapter_characters,
                            'paragraphs': current_chapter_paragraphs,
                            'words': current_chapter_words,
                        })

                        # Reset counters
                        count_empty_lines = 0
                        current_chapter_characters = 0
                        current_chapter_paragraphs = 0
                        current_chapter_words = 0

                    current_chapter_start = i + 1
                    current_chapter_name = l

                    # For arabic_number chapter style, the title could be on the next line
                    if empty_lines[i+1] and not empty_lines[i+2] and empty_lines[i+3]:
                        if not current_chapter_name.endswith('.'):
                            current_chapter_name += '.'
                        current_chapter_name += ' ' + lines[i+2].strip()
                        current_chapter_start = i + 3
                        i += 3

                else:  # Update chapter counters
                    if empty_lines[i]:
                        current_chapter_paragraphs += 1
                    else:
                        current_chapter_characters += len(l)
                        current_chapter_words += len(l.split(' '))

                i += 1

            # Add the last chapter
            chapters.append({
                'title': current_chapter_name,
                'start': current_chapter_start,
                'end':   i - 1,
                'characters': current_chapter_characters,
                'paragraphs': current_chapter_paragraphs,
                'words': current_chapter_words,
            })

            # Strip the chapter content
            # Indeed, we did not try to ignore leading and traling blank lines previously.
            for c in chapters:
                while empty_lines[c['start']]:
                    c['start'] += 1
                while empty_lines[c['end']]:
                    c['end'] -= 1

            # We need to update the line numbers to add the leading lines
            # and + 1 because we worked with 0-based index
            for c in chapters:
                c['start'] += len(leading_lines) + 1
                c['end'] += len(leading_lines) + 1

            return chapters


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

    def metadata_gutenberg(self, entry):
        book_path = self.CONTENT_DIR + '/gutenberg/' + entry.slug + '.txt'
        metadata_path = self.CONTENT_DIR + '/gutenberg/' + entry.slug + '.json'

        # Collect metadata
        metadata = {
            'size': os.path.getsize(book_path),
            'chapters': self._get_chapters(book_path),
        }

        # Save metadata
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
        self.metadata_gutenberg(entry)

    ##
    ## Command 'stats'
    ##

    def stats(self):
        self.stats_github()

    def stats_github(self):
        github_dir = self.CONTENT_DIR + '/github/'
        total_size = 0
        c = Counter()
        for d in os.listdir(github_dir):
            dir_size = folder_size(os.path.join(github_dir, d))
            c[d] += dir_size
            total_size += dir_size

        print('Total size: %s\n' % human_size(total_size))

        print('Top 15:')
        for dir, size in c.most_common(15):
            print('\t- %s (%s)' % (dir, human_size(size)))

    ##
    ## Command 'archive'
    ##

    def archive_github(self, entry):
        github_dir = self.CONTENT_DIR + '/github/'
        local_dir = github_dir + entry.slug
        local_archive = github_dir + entry.slug + '.tar.gz'
        relative_dir = local_dir.replace(github_dir, '')  # relative name

        # Do nothing if the input folder does not exist
        if not os.path.isdir(local_dir):
            print("Folder '%s' does not exists." % Colors.file(local_dir))
            return

        # Do nothing if the archive folder already exist
        if os.path.isfile(local_archive):
            print("File '%s' already exists." % Colors.file(local_archive))
            return

        def reset(tarinfo):
            # https://docs.python.org/3/library/tarfile.html
            tarinfo.uid = tarinfo.gid = 0
            tarinfo.uname = tarinfo.gname = "root"
            return tarinfo
        tar = tarfile.open(local_archive, "w:gz")
        tar.add(local_dir, relative_dir, filter=reset)
        tar.close()

        print("Archive saved to '%s'" % Colors.file(local_archive))


    ##
    ## Command 'unarchive'
    ##

    def unarchive_github(self, entry):
        github_dir = self.CONTENT_DIR + '/github/'
        local_dir = github_dir + entry.slug
        local_archive = github_dir + entry.slug + '.tar.gz'

        # Do nothing if the target folder already exists
        if os.path.isdir(local_dir):
            print("Folder '%s' already exists." % Colors.file(local_dir))
            return

        # Do nothing if the archive folder does not exist
        if not os.path.isfile(local_archive):
            print("File '%s' does not exists." % Colors.file(local_archive))
            return

        tar = tarfile.open(local_archive)
        tar.extractall(path=github_dir)
        tar.close()

        print("Archive extracted into '%s'" % Colors.file(local_dir))


    ##
    ## Prompt
    ##

    def prompt(self):

        def create_grammar():
            return compile("""
                (\s*  (?P<operatorsCommands>[a-z]+)   \s+   (?P<entry>.*)         \s*) |
                (\s*  (?P<operatorsCommands>help|quit|stats)     \s*)
            """)

        def get_bottom_toolbar_tokens(cli):
            return [(Token.Toolbar, ' This is a toolbar.')]

        operatorsCommands = ['archive', 'clean', 'delete', 'download', 'extract', 'get', 'inspect', 'metadata', 'unarchive']
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
                our_history = FileHistory('.typio_history')
                text = prompt('> ', lexer=lexer, completer=completer,
                               style=self.TYPIO_STYLE, get_bottom_toolbar_tokens=get_bottom_toolbar_tokens,
                               history=our_history)
                m = g.match(text)
                if m:
                    vars = m.variables()

                    command = vars['operatorsCommands']

                    # Match basic commands first

                    if command == "quit":
                        break

                    if command == "help":
                        self.showUsage()
                        continue

                    if command == "stats":
                        self.stats()
                        continue

                    # Advanced commands required an entry name.
                    # We check this entry name is valid
                    entry = vars['entry']
                    entries = self.dataset.resolve_name(entry)
                    if not entries:
                        print(Colors.error("No entry named '%s'" % entry))

                    for entry_name in entries:
                        entry = self.dataset.get_entry(entry_name)
                        method = command + '_' + entry.origin

                        # Wrong command
                        if command not in operatorsCommands:
                            print(Colors.error("Command '%s' does not exists (Available commands: %s)" \
                                % (command, ', '.join(operatorsCommands))))

                        # Use introspection to determine the operation is supported for this entry
                        if hasattr(self, method):
                            getattr(self, method)(entry)
                        else:
                            print(Colors.warn("Command '%s' is not supported for type '%s'") % (command, entry.origin))

                else:
                    # Ignore blank input
                    if text.strip():
                        print('Invalid command\n')
                    continue

        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == '__main__':
    p = TypioPrompt('dataset.json')
    p.prompt()
