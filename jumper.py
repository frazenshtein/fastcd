#!/usr/bin/env python

import os
import re
from argparse import ArgumentParser, RawTextHelpFormatter

import urwid

DESC = '''
Jumper shows you the last visited directories, with the ability to quickly cd.
You can use arrows and Page Up/Down to navigate the list.
Press Esc to exit.
Press Enter to change directory.
Start typing to filter directories.
Press Tab to turn on/off case sensitive search.

Supported extra symbols:

    * - any number of any character
    ? - any character
    $ - end of path
'''

def parseCommandLine():
    parser = ArgumentParser(description=DESC, formatter_class=RawTextHelpFormatter)
    parser.add_argument("-i", "--input", dest="Input", metavar="FILE", default="~/.fastcd")
    parser.add_argument("-o", "--output", dest="Output", metavar="FILE", default=None)

    args = parser.parse_args()
    args.Input = os.path.expanduser(args.Input)
    return args


class PathWidget(urwid.WidgetWrap):

    def __init__(self, path, subline=None):
        self.Path = path
        self.Subline = subline

        if os.path.exists(self.Path):
            color = 'body'
            items = [
                ('fixed', 2, urwid.Text(""))
            ]
        else:
            color = 'missing'
            items = [
                ('fixed', 2, urwid.Text("*"))
            ]

        if self.Subline:
            before, match, after = self.Path.partition(self.Subline)
            text = urwid.AttrWrap(urwid.Text([before, ('match', match), after]), color, 'common')
            items.append(text)
        else:
            items.append(urwid.AttrWrap(urwid.Text(self.Path), color, 'common'))
        super(PathWidget, self).__init__(urwid.Columns(items, focus_column=1))

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

        with open(pathsFile) as file:
            for line in file.readlines():
                self.Paths.append(line.strip())

    def Run(self):
        listWalker = urwid.SimpleListWalker([PathWidget(p) for p in self.Paths])
        self.ListBox = urwid.ListBox(listWalker)
        if self.Paths:
            self.ListBox.set_focus(0)

        self.PathFilter = urwid.AttrWrap(urwid.Edit('Fastcd to: '), 'input')
        self.InfoText = urwid.Text("")
        self.Header = urwid.Pile([self.PathFilter, urwid.Padding(urwid.AttrWrap(self.InfoText, 'info'), left=2)])
        self.View = urwid.Frame(self.ListBox, header=self.Header)

        palette = [
            ('body',    'light gray',   'default',      'standout'),
            ('match',   'black',        'dark cyan',    'standout'),
            ('common',  'light blue',   'default',      'standout'),
            ('missing', 'dark gray',    'default',      'standout'),
            ('input',   'light gray',   'default',      'standout'),
            ('info',    'dark red',     'default',      'standout'),
        ]

        loop = urwid.MainLoop(self.View, palette, unhandled_input=self.InputHandler, handle_mouse=False)
        loop.run()

    def GetSelectedPath(self):
        return self.SelectedPath

    def InputHandler(self, input):
        if not isinstance(input, str):
            return input

        if input is 'esc':
            raise urwid.ExitMainLoop()

        if input is 'enter':
            selectedItem = self.ListBox.get_focus()[0]
            if selectedItem:
                path = selectedItem.Path
                if os.path.islink(path):
                    path = os.readlink(path)
                    if not os.path.exists(path):
                        self.InfoText.set_text("Link refers to the not existing directory: '%s'" % path)
                        return
                elif not os.path.exists(path):
                    self.InfoText.set_text("No such directory: '%s'" % path)
                    return
                self.SelectedPath = path
            raise urwid.ExitMainLoop()

        if input is 'tab':
            self.CaseSensitive = not self.CaseSensitive

        # Clean up header
        self.InfoText.set_text("")

        # Display input
        self.PathFilter.keypress((20,), input)

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
        for k ,v in validSpecialSymbols.items():
            inputText = inputText.replace(k, v)

        reFlags = 0 if self.CaseSensitive else re.IGNORECASE
        regex = re.compile(inputText, reFlags)
        for path in self.Paths:
            match = regex.search(path)
            if match:
                newItems.append(PathWidget(path, match.group(0)))

        listWalker = urwid.SimpleListWalker(newItems)

        self.ListBox.body[:] = listWalker
        if newItems:
            self.ListBox.set_focus(0)


def main(args):
    display = Display(args.Input)
    display.Run()

    selectedPath = display.GetSelectedPath()
    if args.Output:
        with open(args.Output, "w") as file:
            file.write(selectedPath)
    else:
        print(selectedPath)

if __name__ == '__main__':
    args = parseCommandLine()
    main(args)
