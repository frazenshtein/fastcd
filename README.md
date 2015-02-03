fastcd
======

### Briefly

These scripts allow you to quickly navigate to the desired directory that has been recently visited.
The utility was written because of the great longing for FarManager and it's plug-in alternative history.

### Usage

Just type "j" in the terminal, press Enter and start typing the name of the desired directory.
You can use arrows and Page Up/Down to navigate the list.
Start typing to filter directories.

    Press 'Esc', 'F10' or 'Meta'+'q' to exit.
    Press 'Enter' to change directory.
    Press 'Ctrl'+'w' to clean up input.
    Press 'Meta'+'Enter' to copy selected path to clipboard (pygtk support required).
    Press 'Meta'+'s' to turn on/off case sensitive search.
    Press 'Tab'/'Shift'+'Tab' to move search forward/backward.
    Press 'Shift'+'F2'-'F8' to set selected path as shortcut.
    Press 'F2'-'F8' to navigate to the directory where the shortcut points.

Supported extra symbols:

    * - any number of any character
    ? - any character
    $ - end of path

For more info: "j --help"

### Example

Type "j" and press Enter in the terminal to launch fastcd

    Fastcd to:

    ->  ~/Soft/FastCd/tests
        ~/Soft/FastCd/tests/temp
        ~/Soft/FastCd/fastcd/.git
        /usr/lib/pyhon2.7
        ~/Soft/FastCd/fastcd/
        /usr/lib

Type "fa" to filter list of directories

    Fastcd to: fa

    ->  ~/Soft/FastCd/tests
        ~/Soft/FastCd/tests/temp
        ~/Soft/FastCd/fastcd/.git
        ~/Soft/FastCd/fastcd

Press "Tab" to move search forward (to match second "fa" in path - it's equal to "fa*fa")

    Fastcd to: fa

    ->  ~/Soft/FastCd/fastcd/.git
        ~/Soft/FastCd/fastcd

Press Down and Enter to cd to ~/Soft/fastcd

If you close and open terminal or open another one and launch fastcd ("j") you will get updated list of directories

    Fastcd to:

    ->  ~/Soft/FastCd/fastcd
        ~/Soft/FastCd/tests
        ~/Soft/FastCd/tests/temp
        ~/Soft/FastCd/fastcd/.git
        /usr/lib/pyhon2.7
        /usr/lib

Now you can just press Enter to cd to the last visited directory

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

Requires python 2.7 + extra modules.
Just type the following to install required python modules:

    sudo apt-get install python-urwid

If you do not have privileges try:

    pip install --user urwid

Get the utility:

    git clone https://github.com/frazenshtein/fastcd

Each user who wants to use fastcd should source the
set.sh file into their bashrc, i.e from within ~/.bashrc just add
a line:

    source $HOME/fastcd/set.sh

And reload bashrc in your terminal:

    source ~/.bashrc
