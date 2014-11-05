#!/usr/bin/env python

import os
import re
from argparse import ArgumentParser

import urwid

def parseCommandLine():
    parser = ArgumentParser()
    parser.add_argument("-i", "--input", dest="Input", metavar="FILE", default="~/.fastcd")
    parser.add_argument("-o", "--output", dest="Output", metavar="FILE", default=None)

    args = parser.parse_args()
    args.Input = os.path.expanduser(args.Input)
    return args


class ItemWidget(urwid.WidgetWrap):

    def __init__(self, label, subline=None):
        self.Label = label
        self.Subline = subline
        items = [
            ('fixed', 5, urwid.AttrWrap(urwid.Text("  ->"), 'selected', 'focus')),
        ]
        if self.Subline:
            before, match, after = self.Label.partition(self.Subline)
            items.append(urwid.Text(('body', [before, ('match', match), after])))
        else:
            items.append(urwid.AttrWrap(urwid.Text(self.Label), 'body'))

        super(ItemWidget, self).__init__(urwid.Columns(items))

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
        self.HeaderText = None
        self.ListBox = None
        self.FooterEdit = None
        self.View = None

        with open(pathsFile) as file:
            for line in file.readlines():
                self.Paths.append(line.strip())

    def Run(self):
        listWalker = urwid.SimpleListWalker([ItemWidget(p) for p in self.Paths])
        self.ListBox = urwid.ListBox(listWalker)
        if self.Paths:
            self.ListBox.set_focus(len(self.Paths) - 1)

        self.FooterEdit = urwid.Edit('Fastcd to: ')
        self.HeaderText = urwid.Text("")
        self.Header = urwid.Pile([urwid.Padding(urwid.AttrWrap(self.HeaderText, 'info'), left=2)])
        self.View = urwid.Frame(urwid.AttrWrap(self.ListBox, 'body'), footer=self.FooterEdit, header=self.Header)

        palette = [
            ('selected', 'black,underline', '',      'standout'),
            ('body',     'light gray',      '',      'standout'),
            ('match',    'light cyan',      '',      'standout'),
            ('focus',    'brown',           '',      'standout'),
            ('footer',   'light gray',      '',      'standout'),
            ('info',     'dark red',        '',      'standout'),
        ]

        loop = urwid.MainLoop(self.View, palette, unhandled_input=self.InputHandler)
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
                path = selectedItem.Label
                if os.path.islink(path):
                    path = os.readlink(path)
                    if not os.path.exists(path):
                        self.HeaderText.set_text("Link refers to the not existing directory: '%s'" % path)
                        return
                elif not os.path.exists(path):
                    self.HeaderText.set_text("No such directory: '%s'" % path)
                    return
                self.SelectedPath = path
            raise urwid.ExitMainLoop()

        # Clean up header
        self.HeaderText.set_text("")

        # Display input
        self.FooterEdit.keypress((20,), input)

        # Filter list
        newItems = []
        inputText = self.FooterEdit.get_edit_text()
        # Support unix filename pattern matching
        inputText = re.escape(inputText).replace(r"\?", ".").replace(r"\*", ".*?")
        regex = re.compile(inputText, re.IGNORECASE)
        for path in self.Paths:
            match = regex.search(path)
            if match:
                newItems.append(ItemWidget(path, match.group(0)))

        listWalker = urwid.SimpleListWalker(newItems)

        self.ListBox.body[:] = listWalker
        if newItems:
            self.ListBox.set_focus(len(newItems) - 1)


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
