import unittest

from typio import Entry

class TestTypio(unittest.TestCase):

    def test_default_patterns(self):
        entry = Entry({
            "origin": "github",
            "name": "Mockito",
            "url": "https://github.com/mockito/mockito",
            "language": "Java",
            "commit": "v2.11.0",
        })
        # Per default, everything should be included
        self.assertFalse(entry.ignorable('src/main', is_directory=True))
        self.assertFalse(entry.ignorable('src/main/java/Main.java', is_directory=False))
        self.assertFalse(entry.ignorable('src/test', is_directory=True))
        self.assertFalse(entry.ignorable('src/test/java/Test.java', is_directory=False))
        self.assertFalse(entry.ignorable('gradle', is_directory=True))
        self.assertFalse(entry.ignorable('README.md', is_directory=False))

        # Except hidden files
        self.assertTrue(entry.ignorable('.github', is_directory=True))
        self.assertTrue(entry.ignorable('.gitignore', is_directory=False))

    def test_custom_patterns(self):
        entry = Entry({
            "origin": "github",
            "name": "Mockito",
            "url": "https://github.com/mockito/mockito",
            "language": "Java",
            "commit": "v2.11.0",
            "includes": ["/src/", "*.gradle", "*.properties"],
            "excludes": ["/src/javadoc/", "/src/conf/"],
        })

        # Everything under stc/main should be included
        self.assertFalse(entry.ignorable('src/main', is_directory=True))
        self.assertFalse(entry.ignorable('src/main/java/Main.java', is_directory=False))

        # Everything under src/test should be ignored
        self.assertTrue(entry.ignorable('src/javadoc', is_directory=True))
        self.assertTrue(entry.ignorable('src/javadoc/index.html', is_directory=False))

        # Hidden files should be ignored
        self.assertTrue(entry.ignorable('.github', is_directory=True))
        self.assertTrue(entry.ignorable('.gitignore', is_directory=False))

        # Non specified folders should be ignored
        self.assertTrue(entry.ignorable('gradle', is_directory=True))
        self.assertTrue(entry.ignorable('README.md', is_directory=False))

    def test_default_extensions(self):
        entry = Entry({
            "origin": "github",
            "name": "Mockito",
            "url": "https://github.com/mockito/mockito",
            "language": "Java",
            "commit": "v2.11.0"
        })

        # There is no filtering on extension by default
        self.assertFalse(entry.ignorable('src/main/java/Main.java', is_directory=False))
        self.assertFalse(entry.ignorable('src/main/go/main.go', is_directory=False))
        self.assertFalse(entry.ignorable('src/main/c/main.h', is_directory=False))
        self.assertFalse(entry.ignorable('README.md', is_directory=False))
        self.assertFalse(entry.ignorable('README.adoc', is_directory=False))
        self.assertFalse(entry.ignorable('README', is_directory=False))

    def test_custom_extensions(self):
        entry = Entry({
            "origin": "github",
            "name": "Mockito",
            "url": "https://github.com/mockito/mockito",
            "language": "Java",
            "commit": "v2.11.0",
            "extensions": ["java", "h", "adoc"]
        })

        # There is no filtering on extension by default
        self.assertFalse(entry.ignorable('src/main/java/Main.java', is_directory=False))
        self.assertTrue(entry.ignorable('src/main/go/main.go', is_directory=False))
        self.assertFalse(entry.ignorable('src/main/c/main.h', is_directory=False))
        self.assertTrue(entry.ignorable('README.md', is_directory=False))
        self.assertFalse(entry.ignorable('README.adoc', is_directory=False))
        self.assertTrue(entry.ignorable('README', is_directory=False))


if __name__ == '__main__':
    unittest.main()
