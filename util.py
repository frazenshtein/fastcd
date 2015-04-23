# coding: utf-8

import os
import re
import sys
import copy
import json
import time
import fcntl
import termios


HOMEDIR = os.environ["HOME"]
REALHOMEDIR = os.path.realpath(os.environ["HOME"])


def copy_to_clipboard(path):
    try:
        import gtk
        import pygtk
        clipboard = gtk.clipboard_get()
        clipboard.set_text(path)
        clipboard.store()
    except BaseException:
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

def convert_json(data):
    if isinstance(data, dict):
        return {convert_json(key): convert_json(value) for key, value in data.iteritems()}
    elif isinstance(data, list):
        return [convert_json(element) for element in data]
    elif isinstance(data, unicode):
        string = data.encode("utf-8")
        # if string.isdigit():
        #     return int(string)
        return string
    else:
        return data

def load_json(filename):
    with open(filename) as file:
        data = file.read()
    # remove comments
    data = re.sub(r"\/\*.*?\*\/", "", data, flags=re.MULTILINE|re.DOTALL)
    jsonData = json.loads(data)
    return convert_json(jsonData)

def get_stdin_buffer():
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
            return sys.stdin.read()
        finally:
            termios.tcsetattr(stdin, termios.TCSANOW, original_tty_attrs)
    except Exception:
        pass
    return ""

def get_dirs(path):
    return [dir for dir in os.listdir(path) if os.path.isdir(os.path.join(path, dir))]

