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

import helper

DESC = '''
Jumper shows you the last visited directories, with the ability to quickly cd.
You can use arrows and Page Up/Down to navigate the list.
Start typing to filter directories.

Press 'Esc', 'F10' or 'Meta'+'q' to exit.
Press 'Enter' to change directory.
Press 'Meta'+'s' to turn on/off case sensitive search.
Press 'Tab'/'Shift'+'Tab' to move search forward/backward.
Press 'Shift'+'F2'-'F8' to set selected path as shortcut.
Press 'F2'-'F8' to navigate to the directory where the shortcut points.

Supported extra symbols:

    * - any number of any character
    ? - any character
    $ - end of path

'''

def parseCommandLine():
    parser = ArgumentParser(description=DESC, formatter_class=RawTextHelpFormatter)
    parser.add_argument("-l", "--list-shortcut-paths", dest="ListShortcutPaths", action='store_true', help="Displays list of stored shortcut paths")
    parser.add_argument("-o", "--output", dest="Output", metavar="FILE", default=None)
    parser.add_argument("--escape-special-symbols", dest="EscapeSpecialSymbols", action='store_true')

    args = parser.parse_args()
    return args

def setPathToClipboard(path):
    try:
        import pygtk
        import gtk
        clipboard = gtk.clipboard_get()
        clipboard.set_text(path)
        clipboard.store()
    except BaseException: pass

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
            color = 'text'
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
            text = urwid.AttrWrap(urwid.Text([before, ('match', match), after]), color, 'selected')
            items.append(text)
        else:
            items.append(urwid.AttrWrap(urwid.Text(path), color, 'selected'))
        super(PathWidget, self).__init__(urwid.Columns(items, focus_column=1))

    def GetPath(self):
        return self.Path

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class Display(object):

    def __init__(self, config):
        self.Config = config
        self.Shortcuts = self.Config["shortcuts"]
        self.SelectedPath = ""
        self.Paths = []
        self.Header = None
        self.InfoText = None
        self.ListBox = None
        self.PathFilter = None
        self.View = None
        self.CaseSensitive = False
        self.SearchOffset = 0
        self.PrevSelectedMissingPath = ""
        self.DefaultSelectedItemIndex = 0
        self.PathsFilename = expanduser(self.Config["stored_paths"])

        cwd = helper.replaceHomeWithTilde(self.GetCwd())
        oldpwd = helper.replaceHomeWithTilde(os.environ.get("OLDPWD", cwd))

        with open(expanduser(self.Config["paths_history"])) as file:
            for line in file.readlines():
                path = line.strip()
                if path in [cwd, oldpwd]:
                    continue
                exists = os.path.exists(expanduser(path))
                self.Paths.append((path, exists))
        # Cwd always first, prev path in the current shell always second
        self.Paths.insert(0, (cwd, os.path.exists(expanduser(cwd))))
        if cwd != oldpwd:
            self.Paths.insert(1, (oldpwd, os.path.exists(expanduser(oldpwd))))
            # Previous directory should be selected by default
            self.DefaultSelectedItemIndex = 1

        signal.signal(signal.SIGINT, Display.hanlderSIGINT)

    @staticmethod
    def hanlderSIGINT(signum, frame):
        raise urwid.ExitMainLoop()

    def Run(self):
        widgets = [PathWidget(path, exists=exists) for path, exists in self.Paths]
        listWalker = urwid.SimpleListWalker(widgets)
        self.ListBox = urwid.ListBox(listWalker)
        if self.Paths:
            self.ListBox.set_focus(self.DefaultSelectedItemIndex)

        self.PathFilter = urwid.AttrWrap(urwid.Edit(self.Config["greeting_line"]), 'input')
        self.InfoText = urwid.Text("")
        self.Header = urwid.Pile([self.PathFilter, urwid.Padding(urwid.AttrWrap(self.InfoText, 'info'), left=2)])
        self.View = urwid.AttrWrap(urwid.Frame(self.ListBox, header=self.Header), 'bg')

        palette = []
        for name, values in self.Config["palette"].items():
            text, bg = values.split("/")
            entry = (name, text, bg, 'standout')
            palette.append(entry)

        loop = urwid.MainLoop(self.View, palette, unhandled_input=self.InputHandler, handle_mouse=False)
        loop.run()

    def GetCwd(self):
        try:
            return os.getcwd()
        except OSError:
            # Current directory removed
            return expanduser("~")

    def GetSelectedPath(self):
        if not self.SelectedPath:
            return ""
        return helper.replaceHomeWithTilde(self.SelectedPath)

    def IsShortcut(self, input):
        return filter(lambda x: input in x, self.Shortcuts.values()) != []

    def InputHandler(self, input):
        if not isinstance(input, str):
            return input

        if input in self.Shortcuts["exit"]:
            raise urwid.ExitMainLoop()

        if input in self.Shortcuts["change_dir"]:
            selectedItem = self.ListBox.get_focus()[0]
            if selectedItem:
                path = expanduser(selectedItem.GetPath())
                # Double Enter should return nearest path
                if path == self.PrevSelectedMissingPath:
                    path = helper.getNearestExistingDir(path)
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

        if input in self.Shortcuts["copy_to_clipboard"]:
            selectedItem = self.ListBox.get_focus()[0]
            if selectedItem:
                setPathToClipboard(selectedItem.GetPath())
                if self.Config["exit_after_coping_path"]:
                    raise urwid.ExitMainLoop()
                return

        if input in self.Shortcuts["case_sensitive"]:
            self.CaseSensitive = not self.CaseSensitive

        if input in self.Shortcuts["inc_search_offset"]:
            self.SearchOffset += 1

        if input in self.Shortcuts["dec_search_offset"]:
            self.SearchOffset -= 1
            if self.SearchOffset < 0:
                self.SearchOffset = 0

        if input in self.Shortcuts["cd_to_path"]:
            path = self.GetStoredPath(self.Shortcuts["cd_to_path"].index(input))
            if path:
                self.SelectedPath = path
                raise urwid.ExitMainLoop()
            return

        if input in self.Shortcuts["store_path"]:
            self.StoreSelectedPath(self.Shortcuts["store_path"].index(input))
            return

        # Clean up header
        self.InfoText.set_text("")

        # Display input if it is not a shortcut
        if not self.IsShortcut(input):
            self.PathFilter.keypress((20,), input)
            # Remove offset if there is no output
            if not self.PathFilter.get_edit_text():
                self.SearchOffset = 0

        # Don't re-render listbox extra time
        if input not in ["up", "down", "left", "right"]:
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

    def GetStoredPath(self, pathIndex):
        if not os.path.exists(self.PathsFilename):
            return ""
        with open(self.PathsFilename) as file:
            data = file.read()
        for num, line in enumerate(data.split("\n")):
            if num == pathIndex:
                return helper.getNearestExistingDir(expanduser(line))
        return ""

    def StoreSelectedPath(self, pathIndex):
        selectedItem = self.ListBox.get_focus()[0]
        if selectedItem:
            selectedPath = expanduser(selectedItem.GetPath())
            storedPaths = []
            # Load stored paths
            if os.path.exists(self.PathsFilename):
                with open(self.PathsFilename) as file:
                    storedPaths = [line.strip() for line in file.readlines()]
            # Extend list
            for _ in range(pathIndex + 1 - len(storedPaths)):
                storedPaths.append("")
            storedPaths[pathIndex] = selectedPath
            # Save
            with open(self.PathsFilename, "w") as file:
                for path in storedPaths:
                    file.write(path + "\n")


def main(args):
    config = helper.loadConfig("jumper")

    if args.ListShortcutPaths:
        storeFilename = expanduser(config["stored_paths"])
        if os.path.exists(storeFilename):
            with open(storeFilename) as file:
                paths = [line.strip() for line in file.readlines()]
            while len(paths) < len(config["shortcuts"]["cd_to_path"]):
                paths.append("")
            print("Shortcuts:")
            for shortcut, path in zip(config["shortcuts"]["cd_to_path"], paths):
                print("{:>3} - {}".format(shortcut, helper.replaceHomeWithTilde(path)))
        return

    # Interactive menu
    display = Display(config)
    display.Run()

    selectedPath = display.GetSelectedPath()
    if args.EscapeSpecialSymbols:
        symbols = [" ", "(", ")"]
        for symbol in symbols:
            selectedPath = selectedPath.replace(symbol, "\\" + symbol)
    if args.Output:
        with open(args.Output, "w") as file:
            file.write(selectedPath)
    else:
        print(selectedPath)

if __name__ == '__main__':
    args = parseCommandLine()
    main(args)
