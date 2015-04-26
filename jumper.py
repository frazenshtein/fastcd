#!/usr/bin/env python
# coding: utf-8

import os
import re
import signal
import argparse
from os.path import expanduser

try:
    import urwid
except ImportError:
    print("Cannot import urwid module. Install it first 'sudo pip install urwid' or 'pip install --user urwid'")
    exit(1)

version = urwid.__version__.split(".")
if version[0] < 1 or version[1] < 2:
    print("Old urwid version detected. Please, upgrade it first 'sudo pip install --upgrade urwid'")
    exit(1)


import util
import search


DESC = '''
Jumper shows last visited directories and allows you change cwd quickly.
You can use arrows and Page Up/Down to navigate the list.
Start typing to filter directories.

'Esc', 'F10' or 'Meta'+'q' to exit.
'Enter' to change directory to the selected.
'Meta + Enter' to change directory to the entered.
'Tab' for auto completion. If entered path is not valid it will be extended.
'Shift + Tab' to paste selected path.
'Ctrl + w' or 'Ctrl + u' to clean up input.
'Meta + Backspace' to remove word.
'Ctrl + c' to copy selected path to clipboard (pygtk support required).
'Meta + f' to turn on/off fuzzy search.
'Meta + s' to turn on/off case sensitive search.
'Meta + l' to move search forward.
'Meta + b' to move search backward.
'Shift'+'F2'-'F8' to set selected path as shortcut.
'F2'-'F8' to paste shortcut path.

Supported extra symbols:

    * - any number of any character
    $ - end of the line

Extra options and parameters can be found in config.json.
'''

def parse_command_line():
    parser = argparse.ArgumentParser(description=DESC, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-l", "--list-shortcut-paths", action='store_true', help="Displays list of stored shortcut paths")
    parser.add_argument("-a", "--add-path", default=None, help=argparse.SUPPRESS) # add path to base
    parser.add_argument("-o", "--output", metavar="FILE", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--escape-special-symbols", action='store_true', help=argparse.SUPPRESS)

    args = parser.parse_args()
    return args


def add_sep(path):
    return path.rstrip("/") + "/"


def load_config():
    module_path = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(module_path, "config.json")
    return util.load_json(config_path)


def prepare_environment(config):
    # create directories
    for param in ["paths_history", "stored_paths"]:
        path = os.path.expanduser(config[param])
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            try:
                os.makedirs(dirname)
            except OSError:
                pass
        # create file
        with open(path, "a"):
            pass


def update_path_list(filename, path, limit):
    if os.path.exists(filename):
        with open(filename) as file:
            paths = [l.strip() for l in file.readlines()]
    else:
        paths = []
    # path already in data
    if path in paths:
        # rise path upward
        paths.remove(path)
    paths = [path] + paths[:limit]
    with open(filename + ".tmp", "w") as file:
        for path in paths:
            file.write("%s\n" % path)
    # change file atomically
    os.rename(filename + ".tmp", filename)


def get_stored_path(filename, path_index):
    if not os.path.exists(filename):
        return ""
    with open(filename) as file:
        data = file.read()
    for num, line in enumerate(data.split("\n")):
        if num == path_index:
            return util.get_nearest_existing_dir(expanduser(line)) or ""
    return ""


def store_path(filename, path, path_index):
    with open(filename) as file:
        stored_paths = [line.strip() for line in file.readlines()]
    # extend list
    for _ in range(path_index + 1 - len(stored_paths)):
        stored_paths.append("")
    stored_paths[path_index] = path

    with open(filename, "w") as file:
        for path in stored_paths:
            file.write(path + "\n")


class PathWidget(urwid.WidgetWrap):

    def __init__(self, path="", exists=True, shift=2):
        self.path = path

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

        if isinstance(self.path, tuple):
            before, match, after = self.path
            text = urwid.AttrWrap(urwid.Text([before, ('match', match), after]), color, 'selected')
            items.append(text)
        else:
            items.append(urwid.AttrWrap(urwid.Text(self.path), color, 'selected'))
        super(PathWidget, self).__init__(urwid.Columns(items, focus_column=1))

    def get_path(self):
        if isinstance(self.path, str):
            return self.path
        return "".join(self.path)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

class AutoCompletionPopup(urwid.WidgetWrap):

    def __init__(self, max_height, min_width):
        self.max_height = max_height
        self.min_width = min_width
        self.is_opened = False
        self.height = 1
        self.width = 1
        self.prefix = ""
        self.listbox = urwid.ListBox(urwid.SimpleListWalker([]))
        self.pile = urwid.Pile([urwid.LineBox(urwid.BoxAdapter(self.listbox, self.height))])

        fill = urwid.Filler(self.pile)
        self.__super.__init__(urwid.AttrWrap(fill, 'match'))

    def update(self, paths, prefix):
        self.prefix = prefix
        self.width = self.min_width
        items = []
        for path in paths:
            self.width = max(self.width, len(path))
            prev_len = len(prefix)
            path_tuple = ("", path[:prev_len], path[prev_len:])
            items.append(PathWidget(path_tuple, shift=0))

        self.listbox.body[:] = urwid.SimpleListWalker(items)
        if items:
            self.listbox.set_focus(0)

        self.height = min(len(items), self.max_height)
        linebox = urwid.LineBox(urwid.BoxAdapter(self.listbox, self.height))
        self.pile.contents[0] = (linebox, ('weight', 1))

    def get_selected(self):
        if self.listbox.body:
            return self.listbox.get_focus()[0]

    def get_height(self):
        return self.height

    def get_width(self):
        return self.width


class PathFilterWidget(urwid.PopUpLauncher):

    def __init__(self, caption):
        self.caption = caption
        self.path_cache = {}
        self.path_edit = urwid.AttrWrap(urwid.Edit(caption), 'input')
        # TODO calc in %
        self.popup = AutoCompletionPopup(20, 20)

        super(PathFilterWidget, self).__init__(self.path_edit)

    def parse_path(self, path):
        if "/" in path:
            path, prefix = path.rsplit("/", 1)
            # in this case '/' is not separator, it's path to the root (/)
            if not path:
                path = "/"
            abspath = expanduser(path)
            if os.path.exists(abspath) and os.path.isdir(abspath):
                if abspath not in self.path_cache:
                    self.path_cache[abspath] = util.get_dirs(abspath)
                dirs = self.path_cache[abspath]
                if prefix:
                    dirs = filter(lambda x: x.lower().startswith(prefix.lower()), dirs)
                dirs = sorted(dirs, key=str.lower)
                return path, dirs, prefix
        return path, [], ""

    def autocomplete(self):
        path = self.get_text()
        path, dirs, prefix = self.parse_path(path)
        # there is only one directory
        if len(dirs) == 1:
            self.set_text(os.path.join(path, dirs[0]) + "/")
            self.close_popup()
        # show candidates
        elif dirs:
            self.popup.update(dirs, prefix)
            self.open_popup()

    def is_popup_opened(self):
        return self.popup.is_opened

    def close_popup(self):
        self.close_pop_up()
        self.popup.is_opened = False

    def open_popup(self):
        self.open_pop_up()
        self.popup.is_opened = True

    def set_text(self, text):
        self.path_edit.set_edit_text(text)
        self.path_edit.set_edit_pos(len(text))

    def get_text(self):
        text = self.path_edit.get_edit_text()
        if isinstance(text, unicode):
            return text.encode("utf-8")
        return text

    def create_pop_up(self):
        return self.popup

    def keypress(self, size, key):
        self.path_edit.keypress(size, key)
        # update popup's content
        if self.is_popup_opened():
            path = self.get_text()
            path, dirs, prefix = self.parse_path(path)
            if dirs:
                self.popup.update(dirs, prefix)
            else:
                self.close_popup()
        return key

    def get_popup_left_pos(self):
        return len(self.get_text()) + len(self.caption) - len(self.popup.prefix) - 1

    def get_pop_up_parameters(self):
        return {
            'left': self.get_popup_left_pos(),
            'top': 1,
            'overlay_width': self.popup.get_width() + 2,  # 2 is border of linebox
            'overlay_height': self.popup.get_height() + 2,
        }


class Display(object):

    def __init__(self, config):
        self.config = config
        self.shortcuts = self.config["shortcuts"]
        self.selected_path = ""
        self.stored_paths = []
        self.header_pile = None
        self.info_text_header = None
        self.listbox = None
        self.path_filter = None
        self.view = None
        self.case_sensitive = bool(self.config["enable_case_sensitive_search"])
        self.fuzzy_search = bool(self.config["enable_fuzzy_search"])
        self.search_offset = 0
        self.previously_selected_nonexistent_path = ""
        self.default_selected_item_index = 0
        self.stored_paths_filename = expanduser(self.config["stored_paths"])

        cwd = util.replace_home_with_tilde(util.get_cwd())
        cwd = add_sep(cwd)
        oldpwd = util.replace_home_with_tilde(os.environ.get("OLDPWD", cwd))
        oldpwd = add_sep(oldpwd)

        with open(expanduser(self.config["paths_history"])) as file:
            for line in file.readlines():
                path = line.strip()
                if path in [cwd, oldpwd]:
                    continue
                exists = os.path.exists(expanduser(path))
                self.stored_paths.append((path, exists))
        # cwd always first, prev path in the current shell is always second if available
        self.stored_paths.insert(0, (cwd, os.path.exists(expanduser(cwd))))
        if cwd != oldpwd:
            self.stored_paths.insert(1, (oldpwd, os.path.exists(expanduser(oldpwd))))
            # previous directory should be selected by default
            self.default_selected_item_index = 1

        signal.signal(signal.SIGINT, Display.hanlder_SIGINT)

    @staticmethod
    def hanlder_SIGINT(signum, frame):
        raise urwid.ExitMainLoop()

    def run(self):
        widgets = [PathWidget(path, exists=exists) for path, exists in self.stored_paths]
        list_walker = urwid.SimpleListWalker(widgets)
        self.listbox = urwid.ListBox(list_walker)
        if self.stored_paths:
            self.listbox.set_focus(self.default_selected_item_index)

        self.path_filter = PathFilterWidget(caption=self.config["greeting_line"])
        self.info_text_header = urwid.Text("")
        self.header_pile = urwid.Pile([self.path_filter, urwid.Padding(urwid.AttrWrap(self.info_text_header, 'info'), left=2)])
        self.view = urwid.AttrWrap(urwid.Frame(self.listbox, header=self.header_pile), 'bg')

        palette = []
        for name, values in self.config["palette"].items():
            text, bg = values.split("/")
            entry = (name, text, bg, 'standout')
            palette.append(entry)

        # there may be data that user already entered before MainLoop was launched
        buffer = util.get_stdin_buffer()
        if buffer:
            self.path_filter.set_text(buffer)
            self.update_listbox()
            # TODO This is temporary fix, it seems to me that cleaning of the list is not really correct
            # steps to reproduce problem:
            # - add time.sleep(3) just before get_stdin_buffer()
            # - launch j
            # - input nonexistent path
            # IndexError: No widget at position 0
            # this is due to cleaning of the ListBox (self.listbox.body[:] = urwid.SimpleListWalker([])) in update_listbox()
            # however, such cleaning method of the Listbox works correctly if you enter a nonexistent path during normal run of the program
            if not self.listbox.body:
                # replace self.listbox with a new one with empty listwalker
                self.listbox = urwid.ListBox(urwid.SimpleListWalker([]))
                self.view = urwid.AttrWrap(urwid.Frame(self.listbox, header=self.header_pile), 'bg')

        loop = urwid.MainLoop(self.view, palette, unhandled_input=self.input_handler, handle_mouse=False, pop_ups=True)
        loop.run()

    def get_selected_path(self):
        if not self.selected_path:
            return ""
        return util.replace_home_with_tilde(self.selected_path)

    def is_shortcut(self, input):
        return filter(lambda x: input in x, self.shortcuts.values()) != []

    def input_handler(self, input):
        if not isinstance(input, (str, unicode)):
            return input

        if input in self.shortcuts["exit"]:
            if self.path_filter.is_popup_opened():
                self.path_filter.close_popup()
            else:
                raise urwid.ExitMainLoop()

        if input in self.shortcuts["cd_selected_path"]:
            if self.path_filter.is_popup_opened():
                selected = self.path_filter.popup.get_selected()
                dirname = os.path.dirname(self.path_filter.get_text())
                path = os.path.join(dirname, selected.get_path()) + "/"

                self.path_filter.set_text(path)
                self.path_filter.close_popup()
            else:
                selected = self.listbox.get_focus()[0]
                if selected:
                    path = selected.get_path()
                else:
                    path = self.path_filter.get_text()
                self.change_directory(path)
                return

        if input in self.shortcuts["cd_entered_path"]:
            self.change_directory(self.path_filter.get_text())
            return

        if input in self.shortcuts["copy_selected_path_to_clipboard"]:
            selected = self.listbox.get_focus()[0]
            if selected:
                util.copy_to_clipboard(selected.get_path())
                if self.config["exit_after_coping_path"]:
                    raise urwid.ExitMainLoop()
                return

        if input in self.shortcuts["autocomplete"]:
            path = self.path_filter.get_text()
            if not path.startswith("~") and not path.startswith("/"):
                path = self.extend_path_filter_text() or path
            # TODO ??? hack
            if path == "~":
                path = add_sep(path)
                self.path_filter.set_text(path)
            self.path_filter.autocomplete()

        # rename shortcut name
        if input in self.shortcuts["paste_selected_path"]:
            self.extend_path_filter_text()

        if input in self.shortcuts["remove_word"]:
            path = self.path_filter.get_text()
            path = path.rstrip("/")
            if "/" in path:
                path, _ = path.rsplit("/", 1)
                if path:
                    path += "/"
                self.path_filter.set_text(path)
            else:
                self.path_filter.set_text("")

        if input in self.shortcuts["case_sensitive"]:
            self.case_sensitive = not self.case_sensitive

        if input in self.shortcuts["fuzzy_search"]:
            self.fuzzy_search = not self.fuzzy_search

        if input in self.shortcuts["inc_search_offset"]:
            self.search_offset += 1

        if input in self.shortcuts["dec_search_offset"]:
            self.search_offset -= 1
            if self.search_offset < 0:
                self.search_offset = 0

        if input in self.shortcuts["cd_to_path"]:
            path = get_stored_path(self.stored_paths_filename, self.shortcuts["cd_to_path"].index(input))
            if path:
                if self.config["exit_after_pressing_path_shortcut"]:
                    self.selected_path = path
                    raise urwid.ExitMainLoop()
                else:
                    path = util.replace_home_with_tilde(path)
                    if self.config["append_asterisk_after_pressing_path_shortcut"]:
                        path += "*"
                    self.path_filter.set_text(path)
            else:
                # do nothing
                return

        if input in self.shortcuts["store_path"]:
            selected = self.listbox.get_focus()[0]
            if selected:
                selected_path = expanduser(selected.get_path())
                store_path(self.stored_paths_filename, selected_path, self.shortcuts["store_path"].index(input))
            return

        # clean up header
        self.info_text_header.set_text("")

        if input in self.shortcuts["clean_input"]:
            self.path_filter.set_text("")

        # display input if it is not a shortcut
        if not self.is_shortcut(input):
            self.path_filter.keypress((20,), input)
            # Remove offset if there is no output
            if not self.path_filter.get_text():
                self.search_offset = 0

        # update popup content
        if self.path_filter.is_popup_opened():
            path = self.path_filter.get_text()
            path, dirs, prefix = self.path_filter.parse_path(path)
            if dirs:
                self.path_filter.popup.update(dirs, prefix)
            else:
                self.path_filter.close_popup()

        # don't re-render listbox extra time
        if input not in ["up", "down", "left", "right"]:
            self.update_listbox()

    def change_directory(self, path):
        path = expanduser(path)
        # double Enter should return nearest path
        if path == self.previously_selected_nonexistent_path:
            path = util.get_nearest_existing_dir(path)
        elif os.path.islink(path):
            path = os.readlink(path)
            if not os.path.exists(path):
                self.previously_selected_nonexistent_path = path
                self.info_text_header.set_text("Link refers to the not existing directory: '%s'" % path)
                return
        elif not os.path.exists(path):
            self.previously_selected_nonexistent_path = path
            self.info_text_header.set_text("No such directory: '%s'" % path)
            return
        self.selected_path = path
        raise urwid.ExitMainLoop()

    def extend_path_filter_text(self):
        selected = self.listbox.get_focus()[0]
        if selected:
            if isinstance(selected.path, tuple):
                path = selected.path[0] + selected.path[1]
            else:
                path = selected.path
            # remove / to prevent popup appearance
            # when autocompletion called for first time
            if path.rstrip("/") == self.path_filter.get_text().rstrip("/"):
                path = selected.get_path()
            else:
                path = path.rstrip("/")
            self.path_filter.set_text(path)
            return path

    def update_listbox(self):
        input_path = self.path_filter.get_text()
        # filter list
        if input_path:
            widgets = []
            if self.fuzzy_search:
                engine = search.FuzzySearchEngine(input_path, self.case_sensitive, self.config["min_fuzzy_search_len"])
            else:
                engine = search.RegexSearchEngine(input_path, self.case_sensitive)
            for path, exists in self.stored_paths:
                for counter, match in enumerate(engine.finditer(path)):
                    if counter >= self.search_offset:
                        # before, match, after
                        path = (path[:match.start()], match.group(), path[match.end():])
                        widgets.append(PathWidget(path, exists=exists))
                        break

            if self.search_offset and len(widgets) == 0:
                self.search_offset -= 1
                return self.update_listbox()
        else:
            widgets = [PathWidget(path, exists=exists) for path, exists in self.stored_paths]

        self.listbox.body[:] = urwid.SimpleListWalker(widgets)
        if widgets:
            self.listbox.set_focus(0)


def main(args):
    config = load_config()
    prepare_environment(config)

    if args.list_shortcut_paths:
        store_filename = expanduser(config["stored_paths"])
        if os.path.exists(store_filename):
            with open(store_filename) as file:
                paths = [line.strip() for line in file.readlines()]
            while len(paths) < len(config["shortcuts"]["cd_to_path"]):
                paths.append("")
            print("Shortcuts:")
            smax_len = len(max(config["shortcuts"]["cd_to_path"], key=lambda x: len(x))) + 1
            for shortcut, path in zip(config["shortcuts"]["cd_to_path"], paths):
                print("{:>{}} - {}".format(shortcut, smax_len, util.replace_home_with_tilde(path)))
    elif args.add_path:
        for pattern in config["skip_list"]:
            if re.search(pattern, args.add_path):
                return

        history_filename = expanduser(config["paths_history"])
        lockfile = os.path.dirname(history_filename) + ".lock"
        with open(lockfile, "w+") as lock:
            util.obtain_lockfile(lock)
            path = args.add_path
            path = util.replace_home_with_tilde(path)
            path = re.sub(r"/{2,}", r"/", path)
            path = add_sep(path)
            update_path_list(history_filename, path, config["paths_history_limit"])
    else:
        urwid.set_encoding("UTF-8")
        # interactive menu
        display = Display(config)
        display.run()

        selected_path = display.get_selected_path()
        if args.escape_special_symbols:
            symbols = [" ", "(", ")"]
            for symbol in symbols:
                selected_path = selected_path.replace(symbol, "\\" + symbol)
        if args.output:
            with open(args.output, "w") as file:
                file.write(selected_path)
        else:
            print(selected_path)


if __name__ == '__main__':
    args = parse_command_line()
    main(args)
