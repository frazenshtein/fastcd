======
fastcd
======

Fastcd allows you to navigate quickly to the desired directory that has been visited recently.

Features
--------

* Autocomplete
* Fuzzy search
* Shortcuts for directories
* Flexible configuration

Usage
-----

Just enter ``j`` in the terminal to launch fastcd's jumper.

Fastcd's jumper shows last visited directories and allows you to change cwd quickly.
Start typing to filter directories.
You can use arrows and Page Up/Down to navigate the list.

Control::

    'Esc', 'F10' or 'Meta + q' to exit.
    'Enter' to change directory to the selected.
    'Meta + Enter' to change directory to the entered.
    'Tab' for auto completion. If entered path is not valid it will be extended.
    'Shift + Tab' to paste selected path.
    'Ctrl + w' or 'Ctrl + u' to clean up input.
    'Meta + Backspace' to remove word.
    'Ctrl + c' to copy selected path to clipboard (pygtk support required).


Search::

    'Meta + f' to turn on/off fuzzy search.
    'Meta + r' to change search position (any pos / from the beginning of the directory name).
    'Meta + s' to turn on/off case sensitive search.
    'Meta + l' to move search forward.
    'Meta + b' to move search backward.


Shortcuts::

    'Shift + F2', 'Shift + F3', 'Shift + F4' or 'Shift + F5' to set selected path as shortcut.
    'F2', 'F3', 'F4' or 'F5' to paste shortcut path.


Supported extra symbols::

    * - any number of any character
    $ - end of the line


Extra options and parameters can be found in ``fastcd/config.json``.
``Meta`` is usually stands for ``alt`` key.

Examples
--------

.. image:: https://raw.githubusercontent.com/frazenshtein/images/master/fastcd/example1.png

Tips
----

Missing or non-existent directories will be displayed dimmed and marked with ``*``.
However, if you press Enter twice, you will cd to the nearest existing directory.

If the entered path is not present in the database, but exists, you will still be able to go into it.

If you want to redefine shortcuts (``~/.local/share/fastcd/config.json``), but don't know their key codes - use ``key_picker.py``.

You can change palette in ``~/.local/share/fastcd/config.json``.

Your current path in shell will be first in list,
while the previous path (``OLDPWD``) will be the second.
Previous path is selected by default.
Thus fastcd (j) + enter is equivalent to ``cd -``.

Type ``j -l`` to list shortcuts and directories to which they point.

If you want to change directory immediately when pressing path shortcut (``F2-F8``) - change ``exit_after_path_shortcut_pressed`` to 1 in ``config.json``

Supported platforms
-------------------
* Linux
* MacOs

Installation
------------

1. Get the utility: ``sudo python3 -m pip install fastcd`` or ``python3 -m pip install fastcd --user``
2. Install shell hook to make fastcd able to track visited directories: ``python3 -m fastcd install``.
3. Restart console session or run ``source ~/.bashrc`` to apply changes.
4. Type ``j`` and press enter to run fastcd.

If you would like to install another alias name for fastcd use:
``python3 -m fastcd install --alias=fcd``

Installation from source code
-----------------------------
Get source code::

    cd $HOME
    git clone https://github.com/frazenshtein/fastcd


Each user who wants to use fastcd should install shell hook first::

    python3 fastcd/fastcd/__main__.py install
    source ~/.bashrc


Utility requires python 3 + extra module::

    sudo python3 -m pip install urwid



If you do not have pip try first::

    sudo apt-get install python3-pip
