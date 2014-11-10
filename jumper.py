#!/usr/bin/env python

import os
import re
import signal
from os.path import expanduser
from argparse import ArgumentParser, RawTextHelpFormatter

try:
    import urwid
except ImportError:
    print("Cannot import urwid module. Install it first 'pip install --user urwid'")
    exit(1)

try:
    import psutil
except ImportError:
    print("Cannot import psutil module for refresher.py. Install it first 'pip install --user psutil' and reload bashrc 'source ~/.bashrc'")
    exit(1)

DESC = '''
Jumper shows you the last visited directories, with the ability to quickly cd.
You can use arrows and Page Up/Down to navigate the list.
Start typing to filter directories.

Press 'Esc', 'F10' or 'Meta'+'q' to exit.
Press 'Enter' to change directory.
Press 'Meta'+'s' to turn on/off case sensitive search.
Press 'Tab'/'Shift'+'Tab' to move search forward/backward.

Supported extra symbols:

    * - any number of any character
    ? - any character
    $ - end of path

'''

def parseCommandLine():
    parser = ArgumentParser(description=DESC, formatter_class=RawTextHelpFormatter)
    parser.add_argument("-i", "--input", dest="Input", metavar="FILE", default="~/.fastcd")
    parser.add_argument("-o", "--output", dest="Output", metavar="FILE", default=None)
    parser.add_argument("--escape-spaces", dest="EscapeSpaces", action='store_true')

    args = parser.parse_args()
    args.Input = expanduser(args.Input)
    return args


class PathWidget(urwid.WidgetWrap):

    def __init__(self, path="", exists=True):
        self.Path = None

        if isinstance(path, str):
            self.Path = path
        elif isinstance(path, tuple):
            self.Path = "".join(path)
        else:
            raise TypeError("Path must be str or three-element tuple")

        if exists:
            color = 'body'
            items = [
                ('fixed', 2, urwid.Text(""))
            ]
        else:
            color = 'missing'
            items = [
                ('fixed', 2, urwid.Text("*"))
            ]

        if isinstance(path, tuple):
            before, match, after = path
            text = urwid.AttrWrap(urwid.Text([before, ('match', match), after]), color, 'common')
            items.append(text)
        else:
            items.append(urwid.AttrWrap(urwid.Text(path), color, 'common'))
        super(PathWidget, self).__init__(urwid.Columns(items, focus_column=1))

    def GetPath(self):
        return self.Path

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class Display(object):

    def __init__(self, pathsFile):
        self.PathsFile = pathsFile
        self.SelectedPath = os.getcwd()
        self.Paths = []
        self.Header = None
        self.InfoText = None
        self.ListBox = None
        self.PathFilter = None
        self.View = None
        self.CaseSensitive = False
        self.SearchOffset = 0
        self.PrevSelectedMissingPath = ""

        with open(pathsFile) as file:
            for line in file.readlines():
                path = line.strip()
                exists = os.path.exists(expanduser(path))
                self.Paths.append((path, exists))

        signal.signal(signal.SIGINT, Display.hanlderSIGINT)

    @staticmethod
    def hanlderSIGINT(signum, frame):
        raise urwid.ExitMainLoop()

    def Run(self):
        widgets = [PathWidget(path, exists=exists) for path, exists in self.Paths]
        listWalker = urwid.SimpleListWalker(widgets)
        self.ListBox = urwid.ListBox(listWalker)
        if self.Paths:
            self.ListBox.set_focus(0)

        self.PathFilter = urwid.AttrWrap(urwid.Edit('Fastcd to: '), 'input')
        self.InfoText = urwid.Text("")
        self.Header = urwid.Pile([self.PathFilter, urwid.Padding(urwid.AttrWrap(self.InfoText, 'info'), left=2)])
        self.View = urwid.AttrWrap(urwid.Frame(self.ListBox, header=self.Header), 'bg')

        bgColor = 'default'
        palette = [
            ('bg',      bgColor,        bgColor,      'standout'),
            ('body',    'light gray',   bgColor,      'standout'),
            ('match',   'dark cyan',    bgColor,      'standout'),
            ('common',  'black',        'dark cyan',  'standout'),
            ('missing', 'dark gray',    bgColor,      'standout'),
            ('input',   'light gray',   bgColor,      'standout'),
            ('info',    'dark red',     bgColor,      'standout'),
        ]
        loop = urwid.MainLoop(self.View, palette, unhandled_input=self.InputHandler, handle_mouse=False)
        loop.run()

    def GetUserHomeDir(self):
        return os.path.realpath(os.environ["HOME"])

    def ReplaceHomeWithTilde(self, path):
        home = self.GetUserHomeDir()
        if path.startswith(home):
            path = path.replace(home, "~")
        return path

    def GetSelectedPath(self):
        return self.ReplaceHomeWithTilde(self.SelectedPath)

    def InputHandler(self, input):
        if not isinstance(input, str):
            return input

        if input in ['esc', 'f10', 'meta q']:
            raise urwid.ExitMainLoop()

        if input == 'enter':
            selectedItem = self.ListBox.get_focus()[0]
            if selectedItem:
                path = expanduser(selectedItem.GetPath())
                # Double Enter should return nearest path
                if path == self.PrevSelectedMissingPath:
                    while path:
                        path, tail = os.path.split(path)
                        if os.path.exists(path):
                            break
                elif os.path.islink(path):
                    path = os.readlink(path)
                    if not os.path.exists(path):
                        self.PrevSelectedMissingPath = path
                        self.InfoText.set_text("Link refers to the not existing directory: '%s'" % path)
                        return
                elif not os.path.exists(path):
                    self.PrevSelectedMissingPath = path
                    self.InfoText.set_text("No such directory: '%s'" % path)
                    return
                self.SelectedPath = path
            raise urwid.ExitMainLoop()

        if input == 'meta s':
            self.CaseSensitive = not self.CaseSensitive

        if input == 'tab':
            self.SearchOffset += 1

        if input == 'shift tab':
            self.SearchOffset -= 1
            if self.SearchOffset < 0:
                self.SearchOffset = 0

        # Clean up header
        self.InfoText.set_text("")

        # Display input
        self.PathFilter.keypress((20,), input)
        # Remove offset if there is no output
        if not self.PathFilter.get_edit_text():
            self.SearchOffset = 0

        self.UpdateLixtBox()

    def UpdateLixtBox(self):
        # Filter list
        newItems = []
        inputText = self.PathFilter.get_edit_text()
        # Support unix filename pattern matching
        validSpecialSymbols = {
            r"\?": ".",
            r"\*": ".*?",
            r"\$": "$",
        }
        inputText = re.escape(inputText)
        for k, v in validSpecialSymbols.items():
            inputText = inputText.replace(k, v)
        reFlags = 0 if self.CaseSensitive else re.IGNORECASE
        regex = re.compile(inputText, reFlags)

        for path, exists in self.Paths:
            for counter, match in enumerate(regex.finditer(path)):
                if counter >= self.SearchOffset:
                    # before, match, after
                    path = (path[:match.start(0)], match.group(0), path[match.end(0):])
                    newItems.append(PathWidget(path, exists=exists))
                    break

        if self.SearchOffset and len(newItems) == 0:
            self.SearchOffset -= 1
            return self.UpdateLixtBox()

        listWalker = urwid.SimpleListWalker(newItems)

        self.ListBox.body[:] = listWalker
        if newItems:
            self.ListBox.set_focus(0)


def main(args):
    display = Display(args.Input)
    display.Run()

    selectedPath = display.GetSelectedPath()
    if args.EscapeSpaces:
        selectedPath = selectedPath.replace(" ", r"\ ")
    if args.Output:
        with open(args.Output, "w") as file:
            file.write(selectedPath)
    else:
        print(selectedPath)

if __name__ == '__main__':
    args = parseCommandLine()
    main(args)
