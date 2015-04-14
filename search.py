import re
# TODO unify style
# TODO profile search()

class SearchEngine(object):
    '''
    Search engines must support '*' and '$' extra characters
    '''

    def __init__(self, pattern, caseSensitive):
        raise NotImplementedError()

    def search(self, string, pos):
        raise NotImplementedError()

    # TODO finditer()
    # yield


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
            self.pattern == other.pattern and
            self.match == other.match and
            self.start == other.start and
            self.end == other.end)

    def group(self, group=0):
        if group:
            raise Exception("Not supported")
        return self.match

    def start(self, group=0):
        if group:
            raise Exception("Not supported")
        return self._start

    def end(self, group=0):
        if group:
            raise Exception("Not supported")
        return self._end


class RegexSearchEngine(SearchEngine):

    def __init__(self, pattern, caseSensitive=False):
        specialSymbols = {
            r"\*": ".*?",
            r"\$": "\/?$",
        }
        pattern = re.escape(pattern)
        for k, v in specialSymbols.items():
            pattern = pattern.replace(k, v)
        self.pattern = pattern
        reFlags = 0 if caseSensitive else re.IGNORECASE
        self.regex = re.compile(self.pattern, flags=reFlags)

    def search(self, string, pos=0):
        match = self.regex.search(string, pos=pos)
        if match:
            return MatchObject(string, self.pattern, match.group(0), match.start(), match.end())
        return None


class FuzzySearchEngine(SearchEngine):
    '''
    Fuzzy search for k=1 (for each substr of pattern) with supported 2 operations:
    substitution and transposition of two adjacent characters
    '''

    AnySymbol = chr(1)

    def __init__(self, pattern, caseSensitive=False):
        self.OriginalPattern = pattern
        if not caseSensitive:
            pattern = pattern.lower()
        self.Pattern = pattern
        self.CaseSensitive = caseSensitive

        eolPos = pattern.find("$")
        self.EndOfLine = eolPos != -1
        if self.EndOfLine:
            pattern = pattern[:eolPos].rstrip("/")
        self.Automatons = []
        # TODO test 'fast***fast'
        for substr in pattern.split("*"):
            if substr:
                # TODO rewrite
                self.Automatons.append(self.BuildFda(substr))

    def BuildFda(self, pattern):
        if len(pattern) < 3:
            return self.BuildDirectFda(pattern)
        return self.BuildFuzzyFda(pattern)

    def BuildFuzzyFda(self, pattern):
        # TODO write moreinfo
        # create initial and core states
        initState = State(pattern[0], pattern[1], self.AnySymbol, level=0)
        coreStates = [initState]
        for level, symbol in enumerate(pattern[1:], start=1):
            state = State(symbol, level=level)
            coreStates.append(state)
        finiteState = State(level=len(pattern))
        coreStates.append(finiteState)

        # link initial states
        initState.rightRef = coreStates[0]
        for level, state in enumerate(coreStates[1:-1], start=1):
            state.leftRef = coreStates[level + 1]

        currState = initState
        for level, symbol in enumerate(pattern[:-2], start=1):
            # create state for left edge
            leftState = State(pattern[level], pattern[level + 1], self.AnySymbol, level=level)

            # create state for middle edge and link it with core state
            midState = State(pattern[level - 1], level=level)
            midState.leftRef = coreStates[level + 1]

            currState.leftRef = leftState
            currState.midRef = midState
            currState.rightRef = coreStates[level]
            # shift to a deeper level
            currState = leftState

        # create last level and link it
        level = len(pattern) - 1
        midState = State(pattern[-2], level=level)
        midState.leftRef = coreStates[level + 1]

        leftState = State(right=self.AnySymbol, level=level)
        leftState.rightRef = coreStates[level + 1]

        currState.leftRef = leftState
        currState.midRef = midState
        return Automaton(initState, finiteState, pattern)

    def BuildDirectFda(self, pattern):
        states = []
        for index, symbol in enumerate(pattern):
            state = State(symbol, level=index)
            states.append(state)
        # append finite state
        states.append(State(level=len(pattern)))
        # link states
        for index in range(len(states) - 1):
            states[index].leftRef = states[index + 1]
        return Automaton(states[0], states[-1], pattern)

    def search_automaton(self, string, pos, automaton):
        # TODO rewrite this shame
        state = automaton.initState
        index = pos
        while True:
            if state.left == string[index]:
                state = state.leftRef
            elif state.mid == string[index]:
                state = state.midRef
            elif state.right:
                state = state.rightRef
            else:
                # TODO check
                index -= state.level
                state = automaton.initState

            if state == automaton.finiteState:
                start = index - state.level + 1
                end = index - state.level + 1 + len(automaton.pattern)
                return MatchObject(string, self.Pattern, string[start:end], start, end)
            index += 1
            if index >= len(string):
                return None

    def search(self, string, pos=0):
        matches = []
        for automaton in self.Automatons:
            lastAutomaton = (automaton == self.Automatons[-1])
            # support $
            # TODO rewrite
            if lastAutomaton and self.EndOfLine:
                while pos < len(string):
                    match = self.search_automaton(string, pos, automaton)
                    if not match:
                        return None
                    if match.end() == len(string):
                        break
                    elif match.end() == len(string) - 1 and string[-1] == "/":
                        match._end += 1
                        break
                    pos = match.end()
            else:
                match = self.search_automaton(string, pos, automaton)
            if not match:
                return None
            matches.append(match)
            pos = match.end()
        start = matches[0].start()
        end = matches[-1].end()
        return MatchObject(string, self.Pattern, string[start:end], start, end)

    def GetStateName(self, state):
        return "Node_{}_{}{}{}\n{}".format(
            state.level,
            state.left or "",
            state.mid or "",
            "?" if state.right else "",
            id(state))

    def DumpDot(self, filename):
        # to get image:
        # dot FILENAME -Tpng -o automatons.png
        with open(filename, "w") as file:
            file.write("digraph G{\n")
            file.write('  graph [rankdir=LR label="pattern: {}"];\n'.format(self.Pattern))
            for index in range(len(self.Automatons)):
                queue = [self.Automatons[index].initState]
                # The graph is acyclic, recursion is not possible
                while queue:
                    newQueue = set()
                    for state in queue:
                        nodeName = self.GetStateName(state)
                        if state.leftRef:
                            file.write('  "{}"->"{}" [label="{}"];\n'.format(nodeName, self.GetStateName(state.leftRef), state.left))
                            newQueue.add(state.leftRef)
                        if state.midRef:
                            file.write('  "{}"->"{}" [label="{}"];\n'.format(nodeName, self.GetStateName(state.midRef), state.mid))
                            newQueue.add(state.midRef)
                        if state.rightRef:
                            file.write('  "{}"->"{}" [label="?"];\n'.format(nodeName, self.GetStateName(state.rightRef)))
                            newQueue.add(state.rightRef)
                    queue = newQueue
                # Draw a connection between several subpatterns
                if index < len(self.Automatons) - 1:
                    initState = self.GetStateName(self.Automatons[index].finiteState)
                    finiteState = self.GetStateName(self.Automatons[index + 1].initState)
                    file.write('  "{}"->"{}" [label="*"];\n'.format(initState, finiteState))
                else:
                    if self.EndOfLine:
                        file.write('  "{}"->"EOL";\n'.format(self.GetStateName(self.Automatons[-1].finiteState)))
            file.write("}\n")

class Automaton(object):

    __slots__ = ['initState', 'finiteState', 'pattern', 'depth']

    def __init__(self, initState, finiteState, pattern):
        self.initState = initState
        self.finiteState = finiteState
        self.pattern = pattern
        self.depth = len(pattern)


class State(object):

    __slots__ = ['left', 'leftRef', 'mid', 'midRef', 'right', 'rightRef', 'level']

    def __init__(self, left=None, mid=None, right=None, level=0):
        self.level = level
        self.left = left
        self.mid = mid
        self.right = right
        assert right is FuzzySearchEngine.AnySymbol or right is None, "Right edge is only for AnySymbol"
        self.leftRef = None
        self.midRef = None
        self.rightRef = None


def compare():
    import time
    # fuzzy = FuzzySearchEngine("fast")
    # fuzzy.DumpDot("fuzzy.dot")

    testData = [
        (
            # match in every line
            ["pretty fast and furious/"] * 1000,
            ["fast", "fats", "dast", "ast", "tsaf", "fas*us", "fat*us", "fat*us$"],
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
            # $ with /
            ["pretty fast, fast and fast"] * 1000,
            ["fast*fast$"],
        ),
        (
            # long match with long pattern
            ["fast" * 30 + "!"] * 1000,
            ["fast" * 30 + "!"]
        )
    ]

    for data, patterns in testData:
        for pattern in patterns:
            print("\nPattern: " + pattern)
            for engine in (RegexSearchEngine, FuzzySearchEngine):
                start = time.time()
                se = engine(pattern)
                for line in data:
                    match = se.search(line)
                end = time.time()
                print("{:20} ({:4}:{:4}) {:0.6f}s  {}".format(engine.__name__, match.start() if match else None, match.end() if match else None, end - start, match.group() if match else None))

# f = FuzzySearchEngine("fat*fu*fast$")
# f.DumpDot("1.dot")
# import os
# os.system("dot 1.dot -Tpng -o 1.png")

if __name__ == '__main__':
    compare()
