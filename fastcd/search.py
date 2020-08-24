# coding: utf-8

import re


class SearchEngine(object):
    '''
    Search engine must support '*' and '$' extra characters, where
     '*' means any number of any character
     '$' means end of the line
    '''

    def __init__(self, pattern, case_sensitive):
        pass

    def search(self, string, pos):
        raise NotImplementedError()

    def finditer(self, string):
        pos = 0
        while True:
            match = self.search(string, pos)
            if not match:
                return
            pos = match.end()
            yield match


class MatchObject(object):
    '''
    Partially repeats the interface of re.MatchObject
    '''

    __slots__ = ["string", "pattern", "match", "_start", "_end"]

    def __init__(self, string, pattern, match, start, end):
        self.string = string
        self.pattern = pattern
        self.match = match
        self._start = start
        self._end = end

    def __eq__(self, other):
        return (
            self.string == other.string and
            self.match == other.match and
            self._start == other._start and
            self._end == other._end)

    def __repr__(self):
        return '%s("%s", "%s", "%s", "%d", "%d")' % (
            self.__class__.__name__,
            self.string,
            self.pattern,
            self.match,
            self._start,
            self._end)

    def group(self, group=0):
        if group:
            raise RuntimeError("Not supported")
        return self.match

    def start(self, group=0):
        if group:
            raise RuntimeError("Not supported")
        return self._start

    def end(self, group=0):
        if group:
            raise RuntimeError("Not supported")
        return self._end


class RegexSearchEngine(SearchEngine):

    def __init__(self, pattern, case_sensitive=False):
        super(RegexSearchEngine, self).__init__(pattern, case_sensitive)
        special_symbols = {
            r"\*": ".*?",
            r"\$": r"$",
        }
        pattern = re.escape(pattern)
        for k, v in special_symbols.items():
            pattern = pattern.replace(k, v)
        self.pattern = pattern
        flags = 0 if case_sensitive else re.IGNORECASE
        self.regex = re.compile(self.pattern, flags=flags)

    def search(self, string, pos=0):
        match = self.regex.search(string, pos=pos)
        if match:
            return MatchObject(string, self.pattern, match.group(0), match.start(), match.end())
        return None


class FuzzySearchEngine(SearchEngine):
    r'''
    Fuzzy search for k=1 (Damerau–Levenshtein distance) (for each substring of pattern, separated by '*')
    with supported 2 operations: substitution and transposition of two adjacent characters.

    Finite deterministic automaton (fda) that is obtained by compiling the pattern "fast"
    where '?' is ANY_SYMBOL; core states are on the right
                                        |
                                      __v__
                                     |f|a|?|  - level 0 (initital state)
                                     |_|_|_|
                                    _/  |  \_
                              _____/    |    \____
                           __/__      __|__     __\__
                          |a|s|?|    |f| | |   |a| | |  - level 1
                          |_|_|_|    |_|_|_|   |_|_|_|
                         _/  | \___   \____     \
                   _____/    |     \_______\_____\
                __/__      __|__                __|__
               |s|t|?|    |a| | |              |s| | |  - level 2
               |_|_|_|    |_|_|_|              |_|_|_|
              _/  | \___   \________            \
        _____/    |     \___________\____________\
     __/__      __|__                           __|__
    | | |?|    |s| | |                         |t| | |  - level 3
    |_|_|_|    |_|_|_|                         |_|_|_|
         \___   \______                           |
             \_________\_________________________ |
                                                _\|__
                                               | | | |  - level 4 (finite state)
                                               |_|_|_|    (if the search has entered this state, we found a match)

    To visualize the generated automatons, you can call:
    >> import search, os
    >> search.FuzzySearchEngine("p*fast*and furious$", narrowing_parts=["furi"]).dump_dot("fda.dot")
    >> os.system("dot fda.dot -Tpng -o fda.png")
    '''

    ANY_SYMBOL = chr(1)

    def __init__(self, pattern, case_sensitive=False, minimal_fuzzy_pattern_len=3, narrowing_parts=None):
        super(FuzzySearchEngine, self).__init__(pattern, case_sensitive)
        self.original_pattern = pattern
        self.case_sensitive = case_sensitive
        self.narrowing_parts = narrowing_parts or []
        self.minimal_fuzzy_pattern_len = max(minimal_fuzzy_pattern_len, 2)
        if not case_sensitive:
            pattern = pattern.lower()
        self.pattern = pattern

        eol_pos = pattern.find("$")
        self.end_of_line = eol_pos != -1
        if self.end_of_line:
            pattern = pattern[:eol_pos]
        self.automatons = []
        for substr in pattern.split("*"):
            if substr:
                self.automatons.append(self.build_fda(substr))

    @staticmethod
    def get_subpatterns(narrowing_parts, pattern, len_threshold):
        # type (is direct), pattern
        subpatterns = [(None, pattern)]
        for narrow in narrowing_parts:
            newsub = []
            for _, subpattern in subpatterns:
                for line in subpattern.split(narrow):
                    if line:
                        newsub.append((None, line))
                    newsub.append((True, narrow))
                # remove last narrow
                newsub.pop()
            if newsub:
                subpatterns = newsub
        for index in range(len(subpatterns)):
            is_direct, pattern = subpatterns[index]
            if is_direct is None:
                subpatterns[index] = (len(pattern) < len_threshold, pattern)
        return subpatterns

    def build_fda(self, pattern):
        subpatterns = self.get_subpatterns(self.narrowing_parts, pattern, self.minimal_fuzzy_pattern_len)
        head = None
        tail = None
        shift = len(pattern)
        for direct, subpattern in reversed(subpatterns):
            shift -= len(subpattern)
            if direct:
                fda = self.build_direct_fda(subpattern, finite_state=head, level_shift=shift)
            else:
                fda = self.build_fuzzy_fda(subpattern, finite_state=head, level_shift=shift)
            head = fda.init_state
            if not tail:
                tail = fda.finite_state
        return Automaton(head, tail, pattern)

    def build_direct_fda(self, pattern, finite_state=None, level_shift=0):
        states = []
        for index, symbol in enumerate(pattern):
            state = State(symbol, level=index, level_shift=level_shift)
            states.append(state)
        # append finite state
        if finite_state:
            states.append(finite_state)
        else:
            states.append(State(level=len(pattern), level_shift=level_shift))
        # link states
        for index in range(len(states) - 1):
            states[index].left_state = states[index + 1]
        return Automaton(states[0], states[-1], pattern)

    def build_fuzzy_fda(self, pattern, finite_state=None, level_shift=0):
        # create core states
        init_state = State(pattern[0], pattern[1], self.ANY_SYMBOL, level=0, level_shift=level_shift)
        core_states = [init_state]
        for level, symbol in enumerate(pattern[1:], start=1):
            state = State(symbol, level=level, level_shift=level_shift)
            core_states.append(state)
        if not finite_state:
            finite_state = State(level=len(pattern), level_shift=level_shift)
        core_states.append(finite_state)

        # link core states
        init_state.right_state = core_states[0]
        for level, state in enumerate(core_states[1:-1], start=1):
            state.left_state = core_states[level + 1]

        state = init_state
        # last level is already created, penultimate will be created is a special way, that's why pattern[:-2]
        for level, symbol in enumerate(pattern[:-2], start=1):
            # create state for left edge
            left_state = State(pattern[level], pattern[level + 1], self.ANY_SYMBOL, level=level, level_shift=level_shift)

            # create state for middle edge and link it with core state
            middle_state = State(pattern[level - 1], level=level, level_shift=level_shift)
            middle_state.left_state = core_states[level + 1]

            state.left_state = left_state
            state.middle_state = middle_state
            state.right_state = core_states[level]
            # shift to a deeper level
            state = left_state

        # penultimate level is created in a special way
        level = len(pattern) - 1
        left_state = State(right=self.ANY_SYMBOL, level=level, level_shift=level_shift)
        left_state.right_state = finite_state

        middle_state = State(pattern[-2], level=level, level_shift=level_shift)
        middle_state.left_state = finite_state

        state.left_state = left_state
        state.middle_state = middle_state
        state.right_state = core_states[level]
        return Automaton(init_state, finite_state, pattern)

    def search_automaton(self, string, pos, automaton):
        strlen = len(string)
        # search string is less than the pattern - a definite mismatch
        if (strlen - pos) < automaton.depth:
            return None
        state = automaton.init_state
        index = pos
        while index < strlen:
            if state.left == string[index]:
                state = state.left_state
            elif state.middle == string[index]:
                state = state.middle_state
            elif state.right:
                state = state.right_state
            else:
                # there is no match - back on the number of done steps to start from the beginning
                index -= state.level
                state = automaton.init_state
            index += 1

            if state == automaton.finite_state:
                start = index - len(automaton.pattern)
                end = index
                return MatchObject(string, self.original_pattern, string[start:end], start, end)

    def search(self, string, pos=0):
        original_string = string
        if not self.case_sensitive:
            string = string.lower()
        matches = []
        for automaton in self.automatons:
            last_automaton = (automaton == self.automatons[-1])
            match = None
            # support '$' symbol
            if last_automaton and self.end_of_line:
                while pos < len(string):
                    match = self.search_automaton(string, pos, automaton)
                    if not match:
                        return None
                    if match.end() == len(string):
                        break
                    pos = match.end()
            else:
                match = self.search_automaton(string, pos, automaton)
            if not match:
                return None
            matches.append(match)
            pos = match.end()
        if not matches:
            return None
        start = matches[0].start()
        end = matches[-1].end()
        return MatchObject(original_string, self.pattern, original_string[start:end], start, end)

    def get_state_name(self, state):
        return "Node_{}_{}{}{}\n{}".format(
            state.level,
            state.left or "",
            state.middle or "",
            "?" if state.right else "",
            id(state))

    def dump_dot(self, filename):
        # to generate image:
        # dot FILENAME -Tpng -o automatons.png
        with open(filename, "w") as file:
            file.write("digraph G{\n")
            file.write('  graph [rankdir=LR label="pattern: {}"];\n'.format(self.pattern))
            for index in range(len(self.automatons)):
                queue = [self.automatons[index].init_state]
                # the graph is acyclic, recursion is not possible
                while queue:
                    newQueue = set()
                    for state in queue:
                        nodeName = self.get_state_name(state)
                        if state.left_state:
                            file.write('  "{}"->"{}" [label="{}"];\n'.format(nodeName, self.get_state_name(state.left_state), state.left))
                            newQueue.add(state.left_state)
                        if state.middle_state:
                            file.write('  "{}"->"{}" [label="{}"];\n'.format(nodeName, self.get_state_name(state.middle_state), state.middle))
                            newQueue.add(state.middle_state)
                        if state.right_state:
                            file.write('  "{}"->"{}" [label="?"];\n'.format(nodeName, self.get_state_name(state.right_state)))
                            newQueue.add(state.right_state)
                    queue = newQueue
                # draw a connection between several patterns
                if index < len(self.automatons) - 1:
                    init_state = self.get_state_name(self.automatons[index].finite_state)
                    finite_state = self.get_state_name(self.automatons[index + 1].init_state)
                    file.write('  "{}"->"{}" [label="*"];\n'.format(init_state, finite_state))
                else:
                    if self.end_of_line:
                        file.write('  "{}"->"EOL";\n'.format(self.get_state_name(self.automatons[-1].finite_state)))
            file.write("}\n")


class Automaton(object):

    __slots__ = ['init_state', 'finite_state', 'pattern', 'depth']

    def __init__(self, init_state, finite_state, pattern):
        self.init_state = init_state
        self.finite_state = finite_state
        self.pattern = pattern
        self.depth = len(pattern)


class State(object):

    '''
    Left edge is for direct match (most frequent case)
    Middle edge is for transposition of two adjacent characters
    Right edge is for substitution/misprint
    '''

    __slots__ = ['left', 'left_state', 'middle', 'middle_state', 'right', 'right_state', 'level']

    def __init__(self, left=None, middle=None, right=None, level=0, level_shift=0):
        self.level = level + level_shift
        self.left = left
        self.middle = middle
        self.right = right
        assert right is FuzzySearchEngine.ANY_SYMBOL or right is None, "Right edge is only for ANY_SYMBOL"
        self.left_state = None
        self.middle_state = None
        self.right_state = None

# -----------------------------------------------------------------------------

def compare():
    import time
    testdata = [
        (
            ["pretty fast and furious/"] * 1000,
            ["fast", "fats", "ast", "tsaf", "fas*us", "fat*us", "fat*us$"],
        ),
        (
            # no match at all
            ["Then they came for me - and there was no one left to speak for me"] * 1000,
            ["fast", "fast" * 30]
        ),
        (
            # long match
            ["pretty fast and fat and fat and fat and fat and fat and fat fast fat fast/"] * 1000,
            ["fast*fast", "fast*fast$", "fsat*fats$"],
        ),
        (
            # worst case - long string, long pattern, almost match
            ["a" * 80 + "bba"] * 1000,
            ["a" * 40 + "bba"]
        )
    ]

    for data, patterns in testdata:
        for pattern in patterns:
            print("\nPattern: " + pattern)
            for engine in (RegexSearchEngine, FuzzySearchEngine):
                start = time.time()
                se = engine(pattern)
                for line in data:
                    match = se.search(line)
                end = time.time()
                print("{:20} ({:4}:{:4}) {:0.6f}s {}".format(
                    engine.__name__,
                    match.start() if match else None,
                    match.end() if match else None,
                    end - start,
                    match.group() if match else None))

if __name__ == '__main__':
    compare()
