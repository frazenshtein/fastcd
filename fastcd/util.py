# coding: utf-8

import os
import re
import sys
import copy
import json
import time
import fcntl
import struct
import termios
import contextlib


HOMEDIR = os.environ["HOME"]
REALHOMEDIR = os.path.realpath(os.environ["HOME"])


def copy_to_clipboard(path):
    try:
        import gtk
        import pygtk
        clipboard = gtk.clipboard_get()
        clipboard.set_text(path)
        clipboard.store()
    except Exception:
        pass


def obtain_lockfile(fd):
    while True:
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except IOError:
            time.sleep(0.1)
            continue


def replace_home_with_tilde(path):
    for candidate in [HOMEDIR, REALHOMEDIR]:
        if path.startswith(candidate):
            path = path.replace(candidate, "~")
    return path


def get_nearest_existing_dir(dir):
    if os.path.exists(dir):
        return dir
    while dir:
        dir, _ = os.path.split(dir)
        if os.path.exists(dir):
            return dir


def get_reference_config_path():
    return os.path.join(get_module_path(), "config.json")


def get_module_path():
    return os.path.dirname(os.path.realpath(__file__))


def load_json(filename):
    with open(filename) as file:
        data = file.read()
    # remove comments
    data = re.sub(r"\/\*.*?\*\/", "", data, flags=re.MULTILINE|re.DOTALL)
    return json.loads(data)


def get_stdin_buffer(one_line=False):
    # https://stackoverflow.com/questions/4327942/non-buffering-stdin-reading
    try:
        stdin = sys.stdin.fileno()
        original_tty_attrs = termios.tcgetattr(stdin)
        tty_attrs = copy.deepcopy(original_tty_attrs)
        # set noncanonical  mode
        tty_attrs[3] &= ~termios.ICANON
        tty_attrs[3] |= termios.ECHO
        tty_attrs[6][termios.VMIN] = 0
        tty_attrs[6][termios.VTIME] = 0
        try:
            termios.tcsetattr(stdin, termios.TCSANOW, tty_attrs)
            if one_line:
                symbols = []
                while True:
                    char = sys.stdin.read(1)
                    if char in ['', '\n']:
                        break
                    symbols.append(char)
                return ''.join(symbols)
            return sys.stdin.read()
        finally:
            termios.tcsetattr(stdin, termios.TCSANOW, original_tty_attrs)
    except Exception:
        pass
    return ""


def get_dirs(path):
    return [dir for dir in os.listdir(path) if os.path.isdir(os.path.join(path, dir))]


def get_cwd():
    try:
        return os.getcwd()
    except OSError:
        # current directory removed
        return os.path.expanduser("~")


def patch_dict(src, patch, key_path=""):
    assert isinstance(src, dict)
    assert isinstance(patch, dict)

    for key, value in src.items():
        if key not in patch:
            continue
        key_path = key_path + "/" + key
        if type(value) != type(patch[key]):
            msg = "Type missmatch. Src:'{0}'|{1} Patch:{0}|{2}".format(key_path, type(value), type(patch[key]))
            raise TypeError(msg)

        if isinstance(src[key], dict):
            patch_dict(src[key], patch[key], key_path)
        elif src[key] != patch[key]:
            src[key] = patch[key]
    return src


def get_term_width(stream=sys.stdout):
    if not hasattr(stream, 'fileno') or not os.isatty(stream.fileno()):
        return None
    res = fcntl.ioctl(stream.fileno(), termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0))
    return struct.unpack('HHHH', res)[1]


def print_status(msg, stream=sys.stdout, truncate=False):
    msg = str(msg)
    term_width = get_term_width(stream)
    if not term_width:
        return

    if truncate:
        msg = msg[:term_width]

    if len(msg) > term_width:
        stream.write("\r" + msg)
        stream.flush()
    else:
        stream.write("\r" + msg)
        stream.write(" " * (term_width - len(msg)))
        stream.flush()


def remove_status(stream=sys.stdout):
    term_width = get_term_width(stream)
    if not term_width:
        return

    stream.write("\r" + " " * term_width)
    stream.flush()


@contextlib.contextmanager
def with_status(msg, stream=sys.stdout, truncate=False):
    print_status(msg, stream, truncate)
    yield
    remove_status()


def get_bashrc():
    filename = os.path.expanduser('~/.bashrc')
    if not os.path.exists(filename):
        return ''

    with open(filename) as afile:
        return afile.read()


def dump_bashrc(data):
    with open(os.path.expanduser('~/.bashrc'), 'w') as afile:
        return afile.write(data)


def install_shell_hook(alias_name):
    module_path = get_module_path()
    filename = os.path.join(module_path, 'fastcd_hook.sh')

    bashrc_data = get_bashrc()
    pattern = r'source "(.*/fastcd_hook.sh)"; alias (\S+)=fastcd'
    install_line = 'source "{}"; alias {}=fastcd'.format(filename, alias_name)

    match = re.search(pattern, bashrc_data)
    if not match :
        bashrc_data += '\n{}\n'.format(install_line)
        dump_bashrc(bashrc_data)
    elif match.group(1) != filename or match.group(2) != alias_name:
        bashrc_data = re.sub(pattern, install_line, bashrc_data)
        dump_bashrc(bashrc_data)
