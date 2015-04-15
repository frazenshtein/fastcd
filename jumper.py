#!/usr/bin/env python
# TODO unify style

import os
import re
import signal
from os.path import expanduser
from argparse import ArgumentParser, RawTextHelpFormatter

try:
    import urwid
except ImportError:
    print("Cannot import urwid module. Install it first 'sudo apt-get install python-urwid' or 'pip install --user urwid'")
    exit(1)

import util


DESC = '''
# TODO UPDATE
Jumper shows you the last visited directories, with the ability to quickly cd.
You can use arrows and Page Up/Down to navigate the list.
Start typing to filter directories.

Press 'Esc', 'F10' or 'Meta'+'q' to exit.
Press 'Enter' to change directory.
Press 'Ctrl'+'w' to clean up input.
Press 'Meta'+'Enter' to copy selected path to clipboard (pygtk support required)
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
    parser.add_argument("-a", "--add-path", dest="AddPath", default=None, help="Add path to base")
    parser.add_argument("-o", "--output", dest="Output", metavar="FILE", default=None)
    parser.add_argument("--escape-special-symbols", dest="EscapeSpecialSymbols", action='store_true')

    args = parser.parse_args()
    return args

def add_sep(path):
    return path.rstrip("/") + "/"

def load_config():
    modulePath = os.path.dirname(os.path.realpath(__file__))
    configPath = os.path.join(modulePath, "config.json")
    return util.load_json(configPath)

def prepare_environment(config):
    # Create directories
    for param in ["paths_history", "stored_paths"]:
        path = os.path.expanduser(config[param])
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        # Create file
        with open(path, "a"):
            pass

def update_path_list(path, filename, limit):
    if os.path.exists(filename):
        with open(filename) as file:
            paths = [l.strip() for l in file.readlines()]
    else:
        paths = []
    # Path already in data
    if path in paths:
        # Raise path
        paths.remove(path)
    paths = [path] + paths[:limit]
    with open(filename + ".tmp", "w") as file:
        for path in paths:
            file.write("%s\n" % path)
    # Change file atomically
    os.rename(filename + ".tmp", filename)


class PathWidget(urwid.WidgetWrap):

    def __init__(self, path="", exists=True, shift=2):
        self.Path = path

        if not isinstance(path, (str, tuple)):
            raise TypeError("Path must be str or three-element tuple")

        if exists:
            color = 'text'
            items = [
                ('fixed', shift, urwid.Text(""))
            ]
        else:
            color = 'missing'
            items = [
                ('fixed', shift, urwid.Text("*"))
            ]

        if isinstance(self.Path, tuple):
            before, match, after = self.Path
            text = urwid.AttrWrap(urwid.Text([before, ('match', match), after]), color, 'selected')
            items.append(text)
        else:
            items.append(urwid.AttrWrap(urwid.Text(self.Path), color, 'selected'))
        super(PathWidget, self).__init__(urwid.Columns(items, focus_column=1))

    def GetPath(self):
        if isinstance(self.Path, str):
            return self.Path
        return "".join(self.Path)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

class AutoCompletionPopup(urwid.WidgetWrap):

    def __init__(self, maxHeight, minWidth):
        self.MaxHeight = maxHeight
        self.MinWidth = minWidth
        self.IsShown = False
        self.Height = 1
        self.Width = 1
        self.Prefix = ""
        self.ListBox = urwid.ListBox(urwid.SimpleListWalker([]))
        self.Pile = urwid.Pile([urwid.LineBox(urwid.BoxAdapter(self.ListBox, self.Height))])

        fill = urwid.Filler(self.Pile)
        self.__super.__init__(urwid.AttrWrap(fill, 'match'))

    def Update(self, paths, prefix):
        self.Prefix = prefix
        self.Width = self.MinWidth
        items = []
        for path in paths:
            self.Width = max(self.Width, len(path))
            prevLen = len(prefix)
            pathTuple = ("", path[:prevLen], path[prevLen:])
            widget = PathWidget(pathTuple, shift=0)
            items.append(widget)

        listWalker = urwid.SimpleListWalker(items)
        self.ListBox.body[:] = listWalker
        if items:
            self.ListBox.set_focus(0)

        self.Height = min(len(items), self.MaxHeight)
        lineBox = urwid.LineBox(urwid.BoxAdapter(self.ListBox, self.Height))
        self.Pile.contents[0] = (lineBox, ('weight', 1))

    def GetHeight(self):
        return self.Height

    def GetWidth(self):
        return self.Width


class PathFilterWidget(urwid.PopUpLauncher):

    def __init__(self, caption):
        self.Caption = caption
        self.PathCache = {}
        self.PathEdit = urwid.AttrWrap(urwid.Edit(caption), 'input')
        # TODO calc in %
        self.Popup = AutoCompletionPopup(20, 20)

        super(PathFilterWidget, self).__init__(self.PathEdit)

    def ParsePath(self, path):
        if "/" in path:
            path, prefix = path.rsplit("/", 1)
            # In this case / is not separator, it path to the root (/)
            if not path:
                path = "/"
            absPath = expanduser(path)
            if os.path.exists(absPath) and os.path.isdir(absPath):
                if absPath not in self.PathCache:
                    self.PathCache[absPath] = util.get_dirs(absPath)
                dirs = self.PathCache[absPath]
                if prefix:
                    dirs = filter(lambda x: x.lower().startswith(prefix.lower()), dirs)
                dirs = sorted(dirs, key=str.lower)
                return path, dirs, prefix
        return path, [], ""

    def AutoComplete(self):
        path = self.GetText()
        path, dirs, prefix = self.ParsePath(path)
        # There is only one directory
        if len(dirs) == 1:
            self.SetText(os.path.join(path, dirs[0]) + "/")
            self.ClosePopup()
        # Show candidates
        elif dirs:
            self.Popup.Update(dirs, prefix)
            self.ShowPopup()

    def IsPopupShown(self):
        return self.Popup.IsShown

    def ClosePopup(self):
        self.close_pop_up()
        self.Popup.IsShown = False

    def ShowPopup(self):
        self.open_pop_up()
        self.Popup.IsShown = True

    def SetText(self, text):
        self.PathEdit.set_edit_text(text)
        self.PathEdit.set_edit_pos(len(text))

    def GetText(self):
        return self.PathEdit.get_edit_text()

    def create_pop_up(self):
        return self.Popup

    def keypress(self, size, key):
        self.PathEdit.keypress(size, key)
        # Update popup's content
        if self.IsPopupShown():
            path = self.GetText()
            path, dirs, prefix = self.ParsePath(path)
            if dirs:
                self.Popup.Update(dirs, prefix)
            else:
                self.ClosePopup()
        return key

    def GetPopupLeftPos(self):
        return len(self.GetText()) + len(self.Caption) - len(self.Popup.Prefix) - 1

    def get_pop_up_parameters(self):
        return {
            'left': self.GetPopupLeftPos(),
            'top': 1,
            'overlay_width': self.Popup.GetWidth() + 2,  # 2 is linebox's border
            'overlay_height': self.Popup.GetHeight() + 2,
        }

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
        self.CaseSensitive = bool(self.Config["case_sensitive_search"])
        self.SearchOffset = 0
        self.PrevSelectedMissingPath = ""
        self.DefaultSelectedItemIndex = 0
        self.PathsFilename = expanduser(self.Config["stored_paths"])

        cwd = util.replace_home_with_tilde(self.GetCwd())
        cwd = add_sep(cwd)
        oldpwd = util.replace_home_with_tilde(os.environ.get("OLDPWD", cwd))
        oldpwd = add_sep(oldpwd)

        with open(expanduser(self.Config["paths_history"])) as file:
            for line in file.readlines():
                path = line.strip()
                if path in [cwd, oldpwd]:
                    continue
                exists = os.path.exists(expanduser(path))
                self.Paths.append((path, exists))
        # Cwd always first, prev path in the current shell is always second if available
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

        self.PathFilter = PathFilterWidget(caption=self.Config["greeting_line"])
        self.InfoText = urwid.Text("")
        self.Header = urwid.Pile([self.PathFilter, urwid.Padding(urwid.AttrWrap(self.InfoText, 'info'), left=2)])
        self.View = urwid.AttrWrap(urwid.Frame(self.ListBox, header=self.Header), 'bg')

        palette = []
        for name, values in self.Config["palette"].items():
            text, bg = values.split("/")
            entry = (name, text, bg, 'standout')
            palette.append(entry)

        # There may be data that user already entered before MainLoop was launched
        bufferData = util.get_stdin_buffer()
        if bufferData:
            self.PathFilter.SetText(bufferData)
            self.UpdateLixtBox()

        loop = urwid.MainLoop(self.View, palette, unhandled_input=self.InputHandler, handle_mouse=False, pop_ups=True)
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
        return util.replace_home_with_tilde(self.SelectedPath)

    def IsShortcut(self, input):
        return filter(lambda x: input in x, self.Shortcuts.values()) != []

    def InputHandler(self, input):
        if not isinstance(input, str):
            return input

        if input in self.Shortcuts["exit"]:
            if self.PathFilter.IsPopupShown():
                self.PathFilter.ClosePopup()
            else:
                raise urwid.ExitMainLoop()

        if input in self.Shortcuts["cd_selected_path"]:
            if self.PathFilter.IsPopupShown():
                selectedItem = self.PathFilter.Popup.ListBox.get_focus()[0]
                dirname = os.path.dirname(self.PathFilter.GetText())
                path = os.path.join(dirname, selectedItem.GetPath()) + "/"

                self.PathFilter.SetText(path)
                self.PathFilter.ClosePopup()
            else:
                selectedItem = self.ListBox.get_focus()[0]
                if selectedItem:
                    path = selectedItem.GetPath()
                else:
                    path = self.PathFilter.GetText()
                self.ChangeDirectory(path)
                return

        if input in self.Shortcuts["cd_entered_path"]:
            self.ChangeDirectory(self.PathFilter.GetText())
            return

        if input in self.Shortcuts["copy_selected_path_to_clipboard"]:
            selectedItem = self.ListBox.get_focus()[0]
            if selectedItem:
                util.copy_to_clipboard(selectedItem.GetPath())
                if self.Config["exit_after_coping_path"]:
                    raise urwid.ExitMainLoop()
                return

        if input in self.Shortcuts["autocomplete"]:
            path = self.PathFilter.GetText()
            if not path.startswith("~") and not path.startswith("/"):
                path = self.ExtendPathFilterInput() or path
            # TODO ??? hack
            if path == "~":
                path = add_sep(path)
                self.PathFilter.SetText(path)
            self.PathFilter.AutoComplete()

        # rename shortcut name
        if input in self.Shortcuts["paste_selected_path"]:
            self.ExtendPathFilterInput()

        if input in self.Shortcuts["remove_word"]:
            path = self.PathFilter.GetText()
            path = path.rstrip("/")
            if "/" in path:
                path, _ = path.rsplit("/", 1)
                if path:
                    path += "/"
                self.PathFilter.SetText(path)
            else:
                self.PathFilter.SetText("")

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
                if self.Config["exit_after_pressing_path_shortcut"]:
                    self.SelectedPath = path
                    raise urwid.ExitMainLoop()
                else:
                    path = util.replace_home_with_tilde(path)
                    if self.Config["append_asterisk_after_pressing_path_shortcut"]:
                        path += "*"
                    self.PathFilter.SetText(path)
            else:
                # Do nothing
                return

        if input in self.Shortcuts["store_path"]:
            self.StoreSelectedPath(self.Shortcuts["store_path"].index(input))
            return

        # Clean up header
        self.InfoText.set_text("")

        if input in self.Shortcuts["clean_input"]:
            self.PathFilter.SetText("")

        # Display input if it is not a shortcut
        if not self.IsShortcut(input):
            self.PathFilter.keypress((20,), input)
            # Remove offset if there is no output
            if not self.PathFilter.GetText():
                self.SearchOffset = 0

        # Update popup content
        if self.PathFilter.IsPopupShown():
            path = self.PathFilter.GetText()
            path, dirs, prefix = self.PathFilter.ParsePath(path)
            if dirs:
                self.PathFilter.Popup.Update(dirs, prefix)
            else:
                self.PathFilter.ClosePopup()

        # Don't re-render listbox extra time
        if input not in ["up", "down", "left", "right"]:
            self.UpdateLixtBox()

    def ChangeDirectory(self, path):
        path = expanduser(path)
        # Double Enter should return nearest path
        if path == self.PrevSelectedMissingPath:
            path = util.get_nearest_existing_dir(path)
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

    def ExtendPathFilterInput(self):
        selectedItem = self.ListBox.get_focus()[0]
        if selectedItem:
            if isinstance(selectedItem.Path, tuple):
                path = selectedItem.Path[0] + selectedItem.Path[1]
            else:
                path = selectedItem.Path
            # Remove / to prevent popup appearance
            # when autocompletion called for first time
            if path.rstrip("/") == self.PathFilter.GetText().rstrip("/"):
                path = selectedItem.GetPath()
            else:
                path = path.rstrip("/")
            self.PathFilter.SetText(path)
            return path

    def UpdateLixtBox(self):
        inputText = self.PathFilter.GetText()
        if inputText:
            # Filter list
            widgets = []
            # Support unix filename pattern matching
            validSpecialSymbols = {
                r"\?": ".",
                r"\*": ".*?",
                r"\$": r"\/?$",
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
                        widgets.append(PathWidget(path, exists=exists))
                        break

            if self.SearchOffset and len(widgets) == 0:
                self.SearchOffset -= 1
                return self.UpdateLixtBox()
        else:
            widgets = [PathWidget(path, exists=exists) for path, exists in self.Paths]

        self.ListBox.body[:] = urwid.SimpleListWalker(widgets)
        if widgets:
            self.ListBox.set_focus(0)

    def GetStoredPath(self, pathIndex):
        if not os.path.exists(self.PathsFilename):
            return ""
        with open(self.PathsFilename) as file:
            data = file.read()
        for num, line in enumerate(data.split("\n")):
            if num == pathIndex:
                return util.get_nearest_existing_dir(expanduser(line)) or ""
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
    config = load_config()
    prepare_environment(config)

    if args.ListShortcutPaths:
        storeFilename = expanduser(config["stored_paths"])
        if os.path.exists(storeFilename):
            with open(storeFilename) as file:
                paths = [line.strip() for line in file.readlines()]
            while len(paths) < len(config["shortcuts"]["cd_to_path"]):
                paths.append("")
            print("Shortcuts:")
            for shortcut, path in zip(config["shortcuts"]["cd_to_path"], paths):
                print("{:>3} - {}".format(shortcut, util.replace_home_with_tilde(path)))
    elif args.AddPath:
        historyFile = expanduser(config["paths_history"])
        lockFile = os.path.dirname(historyFile) + ".lock"
        with open(lockFile, "w+") as lock:
            util.obtain_lockfile(lock)
            path = args.AddPath
            path = util.replace_home_with_tilde(path)
            path = re.sub(r"/{2,}", r"/", path)
            path = add_sep(path)
            update_path_list(path, historyFile, config["paths_history_limit"])
    else:
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
