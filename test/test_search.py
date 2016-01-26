import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from search import FuzzySearchEngine, RegexSearchEngine


class FuzzyEngineTests(unittest.TestCase):

    def get_engines(self, pattern, case_sensitive):
        fuzzy = FuzzySearchEngine(pattern, case_sensitive)
        reference = RegexSearchEngine(pattern, case_sensitive)
        return fuzzy, reference

    def compare_search(self, pattern, string, case_sensisitive=False):
        fuzzy, reference = self.get_engines(pattern, case_sensisitive)
        self.assertEqual(fuzzy.search(string), reference.search(string))

    def test_small_pattern(self):
        self.compare_search("a", "")
        self.compare_search("a", "fast")
        self.compare_search("tt", "pretty Fast")

    def test_simple(self):
        self.compare_search("fast", "")
        self.compare_search("fast", "fast")
        self.compare_search("fast", "pretty fast")
        self.compare_search("aaaabba", "aaaaaabba")

    def test_case_sensitive(self):
        self.compare_search("Fast", "pretty Fast", True)
        self.compare_search("fast", "pretty Fast")

    def test_pattern_with_eol(self):
        self.compare_search("fast$", "fast fast")
        self.compare_search("fast$", "fast fast/")
        self.compare_search("fast$", "fast fa")
        # TOFIX self.compare_search("fast*$", "fast fast fast")
        self.compare_search("fast*fast*$", "fast fast fast")

    def test_pattern_with_asterisks(self):
        self.compare_search("Fast*Fast", "Fast and furious. Fast and Fast", True)
        self.compare_search("Fast*Fast$", "Fast and furious. Fast and Fast", True)
        self.compare_search("Fast***ous*Fast$", "Fast and furious. Fast and Fast", True)
        self.compare_search("*Fast*furious*", "Fast and furious. Fast and Fast", True)

    def compare_fuzzy(self, pattern, string, expected=None, start=0, cs=False):
        fuzzy = FuzzySearchEngine(pattern, case_sensitive=cs)
        match = fuzzy.search(string)
        if expected is None:
            self.assertIsNone(match)
        else:
            self.assertIsNotNone(match)
            self.assertEqual(match.group(), expected)
            self.assertEqual(match.start(), start)

    def test_simple_fuzzy(self):
        self.compare_fuzzy("fas", "f s", expected="f s", start=0)
        self.compare_fuzzy("afst", "pretty fast", expected="fast", start=7)
        self.compare_fuzzy("dast", "pretty fast", expected="fast", start=7)
        self.compare_fuzzy("Dast", "pretty fast", expected="fast", start=7)
        self.compare_fuzzy("Dast", "pretty fast", cs=True, expected="fast", start=7)
        self.compare_fuzzy("aFst", "pretty Fast", cs=True, expected="Fast", start=7)
        self.compare_fuzzy("ast", "pretty fast", expected="ast", start=8)

    def test_fuzzy_with_asterisks(self):
        self.compare_fuzzy("fat*us", "fast and furious", expected="fast and furious", start=0)
        self.compare_fuzzy("das*us$", "fast and furious/", expected=None)
        self.compare_fuzzy("fast*fast", "fast fast fast", expected="fast fast", start=0)
        self.compare_fuzzy("fast*fast$", "fast fast fast", expected="fast fast fast", start=0)
        self.compare_fuzzy("fat*fast", "fast fat fast", expected="fast fat fast", start=0)
        self.compare_fuzzy("das***nd***fun", "fast and furious/", expected="fast and fur", start=0)

    def compare_finditer(self, pattern, string, expected):
        fuzzy = FuzzySearchEngine(pattern)
        matched = []
        for match in fuzzy.finditer(string):
            matched.append(match)
        matched = [m.group() for m in matched]
        self.assertEqual(matched, expected)

    def test_finditer(self):
        self.compare_finditer("fast", "fast faster fastest", ["fast", "fast", "fast"])
        self.compare_finditer("fsat", "fast faster fastest", ["fast", "fast", "fast"])
        self.compare_finditer("fsta", "fast faster fastest", [])


if __name__ == '__main__':
    unittest.main()
