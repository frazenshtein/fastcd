#!/usr/bin/env python
# coding: utf-8

import os
import re
import signal
import argparse
from os.path import expanduser

# # XXX
# def step(msg):
#     import sys
#     import time
#     if "--stages" in sys.argv:
#         current = time.time()
#         passed = getattr(step, 'last', current)
#         with open(os.path.join(os.path.dirname(__file__), "stages.log"), "a") as afile:
#             afile.write("[{:.5f} | {:.2f}] {}\n".format(current - passed, current, msg))
#         setattr(step, 'last', current)

try:
    import urwid
except ImportError:
    print("Cannot import urwid module. Install it first 'sudo pip3 install urwid' or 'python3 -mpip install --user urwid'")
    exit(1)

URWID_VERSION = urwid.__version__.split(".")
if float(URWID_VERSION[0] + "." + URWID_VERSION[1]) < 1.1:
    print("Old urwid version detected (%s). Please, upgrade it first 'sudo pip3 install --upgrade urwid'" % urwid.__version__)
    exit(1)

try:
    from fastcd import util, search
except ImportError:
    from . import util, search


DESC = '''
Fastcd's jumper shows last visited directories and allows you change cwd quickly.
You can use arrows and Page Up/Down to navigate the list.
Start typing to filter directories.

Control:
{exit} to exit.
{cd_selected_path} to change directory to the selected.
{cd_entered_path} to change directory to the entered.
{autocomplete} for auto completion. If entered path is not valid it will be extended.
{paste_selected_path} to paste selected path.
{clean_input} to clean up input.
{remove_word} to remove word.
{copy_selected_path_to_clipboard} to copy selected path to clipboard (pygtk support required).

Search:
{fuzzy_search} to turn on/off fuzzy search.
{search_pos} to change search position (any pos / from the beginning of the directory name).
{case_sensitive} to turn on/off case sensitive search.
{inc_search_offset} to move search forward.
{dec_search_offset} to move search backward.

Shortcuts:
{store_shortcut_path} to set selected path as shortcut.
{cd_to_shortcut_path} to paste shortcut path.

Supported extra symbols:
    * - any number of any character
    $ - end of the line

Extra options and parameters can be found in config.json.
'''

def parse_command_line(config):
    parser = argparse.ArgumentParser(description=get_description(config["shortcuts"]), formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("install", nargs='?', help="Setup shell hook make fastcd able to track visited directories")
    parser.add_argument("--alias", default='j', help="Specifies installation alias for fastcd (default: 'j')")
    parser.add_argument("-l", "--list-shortcut-paths", action='store_true', help="Displays list of stored shortcut paths")
    parser.add_argument("-a", "--add-path", default=None, help=argparse.SUPPRESS) # add path to base
    parser.add_argument("-o", "--output", metavar="FILE", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--escape-special-symbols", action='store_true', help=argparse.SUPPRESS)
    parser.add_argument("--stages", action='store_true', help=argparse.SUPPRESS)  # XXX

    args = parser.parse_args()
    return args


def get_description(shortcuts):
    def representative(shortcut):
        return " + ".join([p.capitalize() if len(p) > 1 else p for p in shortcut.split(" ")])

    shortcuts_data = {}
    for name, keys in shortcuts.items():
        shortcut_enum = []
        for shortcut in keys:
            shortcut_enum.append("'%s'" % representative(shortcut))
        if len(shortcut_enum) > 1:
            shortcut_enum_text = ", ".join(shortcut_enum[:-1]) + " or " + shortcut_enum[-1]
        else:
            shortcut_enum_text = shortcut_enum[0]
        shortcuts_data[name] = shortcut_enum_text
    return DESC.format(**shortcuts_data)


def load_config():
    def expand_paths(config):
        paths = ["history_file", "shortcuts_paths_file", "user_config_file"]
        for param in paths:
            config[param] = expanduser(config[param])
        return config

    ref_config = expand_paths(util.load_json(util.get_reference_config_path()))
    if os.path.exists(ref_config["user_config_file"]):
        usr_config = expand_paths(util.load_json(ref_config["user_config_file"]))
        config = util.patch_dict(ref_config, usr_config)
        config["user_config_file"] = ref_config["user_config_file"]
        return config
    return ref_config


def prepare_environment(config):
    # create directories
    for param in ["history_file", "shortcuts_paths_file", "user_config_file"]:
        dirname = os.path.dirname(config[param])
        if not os.path.exists(dirname):
            try:
                os.makedirs(dirname)
            except OSError:
                pass

    # generate user config
    user_config_file = config["user_config_file"]
    if not os.path.exists(user_config_file):
        with open(util.get_reference_config_path()) as afile:
            data = afile.read()
        # remove description warning
        data = data[data.find("{"):]
        with open(user_config_file, "w") as afile:
            afile.write(data)

    # create rest files
    for param in ["history_file", "shortcuts_paths_file"]:
        open(config[param], "a").close()


def path_strip(path):
    # root path
    if path and path == "/":
        return path
    return path.rstrip("/")


def update_path_list(filename, path, limit, skip_list):
    if os.path.exists(filename):
        with open(filename) as afile:
            paths = [l.strip() for l in afile.readlines()]
    else:
        paths = []

    def in_skip_list(path):
        for pattern in skip_list:
            if re.search(pattern, path):
                return True
    # remove unwanted paths - keep history clean
    paths = [p for p in paths if not in_skip_list(p)]
    # path already in data
    if path in paths:
        # rise path upward
        paths.remove(path)
    paths = [path] + paths[:limit]
    with open(filename + ".tmp", "w") as afile:
        for path in paths:
            afile.write("%s\n" % path)
    # change file atomically
    os.rename(filename + ".tmp", filename)


def get_shortcut_path(filename, path_index):
    if not os.path.exists(filename):
        return ""
    with open(filename) as afile:
        data = afile.read()
    for num, line in enumerate(data.split("\n")):
        if num == path_index:
            return util.get_nearest_existing_dir(expanduser(line)) or ""
    return ""


def store_shortcut_path(filename, path, path_index):
    with open(filename) as afile:
        stored_paths = [line.strip() for line in afile.readlines()]
    # extend list
    for _ in range(path_index + 1 - len(stored_paths)):
        stored_paths.append("")
    stored_paths[path_index] = path

    with open(filename, "w") as afile:
        for path in stored_paths:
            afile.write(path + "\n")


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
            color = 'minor'
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
        super().__init__(urwid.AttrWrap(fill, 'match'))

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

    def __init__(self):
        self.path_cache = {}
        self.path_edit = urwid.AttrWrap(urwid.Edit(), 'input')
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
                    dirs = [d for d in dirs if d.lower().startswith(prefix.lower())]
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
        return self.path_edit.get_edit_text()

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
        return len(self.get_text()) - len(self.popup.prefix) - 1

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
        self.search_engine_label = None
        self.path_filter = None
        self.view = None
        self.case_sensitive = bool(self.config["enable_case_sensitive_search"])
        self.fuzzy_search = bool(self.config["enable_fuzzy_search"])
        # search will look for matches from the beginning of the directory name if false
        self.search_from_any_pos = bool(self.config["search_from_any_pos"])
        self.search_engine_label_limit = 20
        self.search_offset = 0
        self.previously_selected_nonexistent_path = ""
        # select by default oldpwd or last visited if there is no oldpwd
        self.default_selected_item_index = 1
        self.shortcuts_paths_filename = self.config["shortcuts_paths_file"]
        self.shortcuts_cache = set()
        self.stored_paths = self.get_stored_paths()

        if len(self.stored_paths) < 2:
            self.default_selected_item_index = 0

        signal.signal(signal.SIGINT, Display.handler_sigint)

    @staticmethod
    def handler_sigint(signum, frame):
        raise urwid.ExitMainLoop()

    def run(self):
        widgets = [PathWidget(path, exists=exists) for path, exists in self.stored_paths]
        list_walker = urwid.SimpleListWalker(widgets)
        self.listbox = urwid.ListBox(list_walker)
        if self.stored_paths:
            self.listbox.set_focus(self.default_selected_item_index)

        self.path_filter = PathFilterWidget()
        self.search_engine_label = urwid.AttrWrap(urwid.Text(self.get_search_engine_label_text(), align='right'), 'minor')
        filter_column = urwid.Columns(
            [
                ('pack', urwid.Text(self.config["greeting_line"])),
                self.path_filter,
                (self.search_engine_label_limit, self.search_engine_label)
            ])
        self.info_text_header = urwid.Text("")
        self.header_pile = urwid.Pile([filter_column, urwid.Padding(urwid.AttrWrap(self.info_text_header, 'info'), left=2)])
        self.view = urwid.AttrWrap(urwid.Frame(self.listbox, header=self.header_pile), 'bg')

        palette = []
        for name, values in self.config["palette"].items():
            text, bg = values.split("/")
            entry = (name, text, bg, 'standout')
            palette.append(entry)

        # there may be data that user already entered before MainLoop was launched
        buff = util.get_stdin_buffer(one_line=True)
        if buff:
            self.path_filter.set_text(buff)
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

    def get_stored_paths(self):
        cwd = util.replace_home_with_tilde(util.get_cwd())
        cwd = path_strip(cwd)
        oldpwd = util.replace_home_with_tilde(os.environ.get("OLDPWD", cwd))
        oldpwd = path_strip(oldpwd)
        paths = []

        with open(self.config["history_file"]) as afile:
            entries = afile.read().split("\n")

        check_existence = self.config["check_directory_existence"]
        # this may take a while - print something
        # there may be network paths or meta info might be not in the system cache
        if check_existence:
            util.print_status("Checking the existence of directories...", truncate=True)

        skip_set = ('', cwd, oldpwd)
        for line in entries:
            path = line.strip()
            if path in skip_set:
                continue
            if check_existence:
                exists = os.path.exists(expanduser(path))
            else:
                exists = True
            paths.append((path_strip(path), exists))

        if check_existence:
            util.remove_status()

        # cwd always first, prev path in the current shell is always second if available
        paths.insert(0, (cwd, os.path.exists(expanduser(cwd))))
        if cwd != oldpwd:
            paths.insert(1, (oldpwd, os.path.exists(expanduser(oldpwd))))
        return paths

    def is_shortcut(self, input):
        if not self.shortcuts_cache:
            for x in self.shortcuts.values():
                self.shortcuts_cache.update(x)
        return input in self.shortcuts_cache

    def input_handler(self, input):
        if not isinstance(input, str):
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
                path = path_strip(path)
                self.path_filter.set_text(path)
            self.path_filter.autocomplete()

        # rename shortcut name
        if input in self.shortcuts["paste_selected_path"]:
            self.extend_path_filter_text()

        if input in self.shortcuts["remove_word"]:
            path = self.path_filter.get_text()
            path = path_strip(path)
            if "/" in path:
                path, _ = path.rsplit("/", 1)
                if path:
                    path += "/"
                self.path_filter.set_text(path)
            else:
                self.path_filter.set_text("")

        if input in self.shortcuts["case_sensitive"]:
            self.case_sensitive = not self.case_sensitive
            self.update_search_engine_label()

        if input in self.shortcuts["fuzzy_search"]:
            self.fuzzy_search = not self.fuzzy_search
            self.update_search_engine_label()

        if input in self.shortcuts["search_pos"]:
            self.search_from_any_pos = not self.search_from_any_pos
            self.update_search_engine_label()

        if input in self.shortcuts["inc_search_offset"]:
            self.search_offset += 1

        if input in self.shortcuts["dec_search_offset"]:
            self.search_offset -= 1
            if self.search_offset < 0:
                self.search_offset = 0

        if input in self.shortcuts["cd_to_shortcut_path"]:
            path = get_shortcut_path(self.shortcuts_paths_filename, self.shortcuts["cd_to_shortcut_path"].index(input))
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

        if input in self.shortcuts["store_shortcut_path"]:
            selected = self.listbox.get_focus()[0]
            if selected:
                selected_path = expanduser(selected.get_path())
                store_shortcut_path(self.shortcuts_paths_filename, selected_path, self.shortcuts["store_shortcut_path"].index(input))
            return

        # clean up header
        self.info_text_header.set_text("")

        if input in self.shortcuts["clean_input"]:
            self.path_filter.set_text("")
            return

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
        path = expanduser(path).rstrip(" ")
        # double Enter should return nearest path
        if path == self.previously_selected_nonexistent_path:
            path = util.get_nearest_existing_dir(path)
        elif os.path.islink(path):
            path = os.readlink(path)
            if not os.path.exists(path):
                self.previously_selected_nonexistent_path = path
                self.info_text_header.set_text("Link refers to the not existing directory: '%s'" % path)
                return
        elif os.path.isfile(path):
            path = os.path.dirname(path)
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
            if path_strip(path) == path_strip(self.path_filter.get_text()):
                path = selected.get_path()
            else:
                path = path_strip(path)
            self.path_filter.set_text(path)
            return path

    def update_search_engine_label(self):
        self.search_engine_label.set_text(self.get_search_engine_label_text())

    def get_search_engine_label_text(self):
        parts = []
        if self.fuzzy_search:
            parts.append("fuzzy")
        else:
            parts.append("direct")

        if self.search_from_any_pos:
            parts.append("any pos")
        else:
            parts.append("/headed")

        if self.case_sensitive:
            parts.append("CS")
        else:
            parts.append("CIS")

        return "[%s]" % " ".join(parts)[:self.search_engine_label_limit - 2]

    def update_listbox(self):
        input_path = self.path_filter.get_text()
        # filter list
        if input_path:
            if not self.search_from_any_pos and not input_path.startswith("/") and not input_path.startswith("~"):
                input_path = "/" + input_path

            if self.fuzzy_search:
                engine = search.FuzzySearchEngine(input_path, self.case_sensitive, self.config["min_fuzzy_search_len"], narrowing_parts=["/"])
            else:
                engine = search.RegexSearchEngine(input_path, self.case_sensitive)
            widgets = []
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


def main():
    config = load_config()
    args = parse_command_line(config)

    if args.install:
        util.install_shell_hook(args.alias)
        print("Restart console session or run 'source ~/.bashrc' to finish fastcd's installation.")
        print("Then use '{}' command to run fastcd.".format(args.alias))
        prepare_environment(config)
        return

    prepare_environment(config)

    if args.list_shortcut_paths:
        store_filename = config["shortcuts_paths_file"]
        if os.path.exists(store_filename):
            with open(store_filename) as afile:
                paths = [line.strip() for line in afile.readlines()]
            while len(paths) < len(config["shortcuts"]["cd_to_shortcut_path"]):
                paths.append("")
            print("Shortcuts:")
            smax_len = len(max(config["shortcuts"]["cd_to_shortcut_path"], key=len)) + 1
            for shortcut, path in zip(config["shortcuts"]["cd_to_shortcut_path"], paths):
                print("{:>{}} - {}".format(shortcut, smax_len, util.replace_home_with_tilde(path)))
    elif args.add_path:
        for pattern in config["skip_list"]:
            if re.search(pattern, args.add_path):
                return

        history_filename = config["history_file"]
        lockfile = os.path.dirname(history_filename) + ".lock"
        with open(lockfile, "w+") as lock:
            util.obtain_lockfile(lock)
            path = args.add_path
            path = util.replace_home_with_tilde(path)
            path = re.sub(r"/{2,}", r"/", path)
            path = path_strip(path)
            update_path_list(history_filename, path, config["history_limit"], config["skip_list"])
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
            with open(args.output, "w") as afile:
                afile.write(selected_path)
        else:
            print(selected_path)


if __name__ == '__main__':
    main()