import os
import sys
import unittest

currDir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(currDir, ".."))

from search import FuzzySearchEngine, RegexSearchEngine


class FuzzyEngineTests(unittest.TestCase):

    def get_engines(self, pattern, case_sensitive):
        fuzzy = FuzzySearchEngine(pattern, case_sensitive)
        reference = RegexSearchEngine(pattern, case_sensitive)
        return fuzzy, reference

    def compare_search(self, pattern, string, case_sensisitive):
        fuzzy, reference = self.get_engines(pattern, case_sensisitive)
        self.assertEqual(fuzzy.search(string), reference.search(string))

    def test_small_pattern(self):
        self.compare_search("a", "fast", False)
        self.compare_search("tt", "pretty Fast", False)

    def test_simple(self):
        self.compare_search("fast", "fast", False)
        self.compare_search("fast", "pretty fast", False)

    def test_case_sensitive(self):
        self.compare_search("Fast", "pretty Fast", True)
        self.compare_search("fast", "pretty Fast", False)

    def test_pattern_with_eol(self):
        self.compare_search("fast$", "fast fast", False)
        self.compare_search("fast$", "fast fast/", False)
        self.compare_search("fast$", "fast fa", False)
        self.compare_search("fast*fast$", "fast fast fast", False)

    def test_pattern_with_asterisks(self):
        self.compare_search("Fast*Fast", "Fast and furious. Fast and Fast", True)
        self.compare_search("Fast*Fast$", "Fast and furious. Fast and Fast", True)
        self.compare_search("Fast****ous*Fast$", "Fast and furious. Fast and Fast", True)

    def compare_fuzzy(self, pattern, string, cs, expected, start):
        fuzzy = FuzzySearchEngine(pattern, cs)
        match = fuzzy.search(string)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(), expected)
        self.assertEqual(match.start(), start)

    def test_simple_fuzzy(self):
        self.compare_fuzzy("afst", "pretty fast", cs=False, expected="fast", start=7)
        self.compare_fuzzy("dast", "pretty fast", cs=False, expected="fast", start=7)
        self.compare_fuzzy("Dast", "pretty fast", cs=False, expected="fast", start=7)
        self.compare_fuzzy("Dast", "pretty fast", cs=True, expected="fast", start=7)
        self.compare_fuzzy("aFst", "pretty Fast", cs=True, expected="Fast", start=7)
        self.compare_fuzzy("ast", "pretty fast", cs=False, expected="ast", start=8)

    def test_fuzzy_with_asterisks(self):
         self.compare_fuzzy("fat*us", "fast and furious", cs=False, expected="fast and furious", start=0)
         self.compare_fuzzy("das*us$", "fast and furious/", cs=False, expected="fast and furious/", start=0)
         self.compare_fuzzy("fast*fast", "fast fast fast", cs=False, expected="fast fast", start=0)
         self.compare_fuzzy("fast*fast$", "fast fast fast", cs=False, expected="fast fast fast", start=0)
         self.compare_fuzzy("fat*fast", "fast fat fast", cs=False, expected="fast fat fast", start=0)
         self.compare_fuzzy("das***nd***fun", "fast and furious/", cs=False, expected="fast and fur", start=0)


if __name__ == '__main__':
    unittest.main()
