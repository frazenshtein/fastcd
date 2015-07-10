fastcd
======

### Briefly

Fastcd allows you to navigate quickly to the desired directory that has been visited recently.

### Features

* Extremely quick directory navigation
* Fuzzy search
* Autocomplete
* Shortcuts for directories
* Flexible configuration

### Usage

Just enter 'j' in the terminal to launch jumper that shows
last visited directories and allows you change cwd quickly.
You can use arrows and Page Up/Down to navigate the list.
Start typing to filter directories.

    'Esc', 'F10' or 'Meta + q' to exit.
    'Enter' to change directory to the selected.
    'Meta + Enter' to change directory to the entered.
    'Tab' for auto completion. If entered path is not valid it will be extended.
    'Shift + Tab' to paste selected path.
    'Ctrl + w' or 'Ctrl + u' to clean up input.
    'Meta + Backspace' to remove word.
    'Ctrl + c' to copy selected path to clipboard (pygtk support required).
    'Meta + f' to turn on/off fuzzy search.
    'Meta + r' to change search position (any pos / from the beginning of the directory name).
    'Meta + s' to turn on/off case sensitive search.
    'Meta + l' to move search forward.
    'Meta + b' to move search backward.
    'Shift F2-F8' to set selected path as shortcut.
    'F2-F8' to paste shortcut path.

Supported extra symbols:

    * - any number of any character
    $ - end of the line

Extra options and parameters can be found in config.json.

### Examples

![Example](https://github.com/frazenshtein/images/blob/master/fastcd/example1.png)
![Example](https://github.com/frazenshtein/images/blob/master/fastcd/example2.png)

### Tips

Missing or non-existent directories will be displayed dimmed and marked with '*'.
However, if you press Enter twice, you will cd to the nearest existing directory.

If the entered path is not present in the database, but is exists, you will still be able to go into it.
If if doesn't exist, you will stay in your current directory.

If you want to redefine shortcuts (config.json), but don't know their key codes - use key_picker.py.

You can change palette in config.json.

Your current path in shell will be first in list,
while the previous path (OLDPWD) will be the second.
Previous path is selected by default.
Thus fastcd (j) + enter is equivalent to "cd -".

Type 'j -l' to list shortcuts and directories to which they point.

If you want to change directory immediately when pressing path shortcut ('F2'-'F8') - change "exit_after_path_shortcut_pressed" to 1 in config.json

### Installation

Get the utility:

    git clone https://github.com/frazenshtein/fastcd

Each user who wants to use fastcd should source the
set.sh file into their bashrc, i.e from within ~/.bashrc just add
a line:

    source $HOME/fastcd/set.sh

And reload bashrc in your terminal:

    source ~/.bashrc

Utility requires python 2.7 + extra module.
Just type the following to install required python modules:

    sudo pip install urwid

If you do not have privileges try:

    pip install --user urwid

If you do not have pip try first:

    sudo apt-get install python-pip

