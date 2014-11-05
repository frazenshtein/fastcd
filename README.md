fastcd
======

## Briefly

These scripts allow you to quickly navigate to the desired directory
that have been recently visited.
The utility was written because of the great longing for FarManager and it's plug-in alternative history.

### USAGE

Just type "j" in the terminal, press Enter and start typing the name of the desired directory.
You can use arrows and Page Up/Down to navigate the list.
Press Esc to exit.
Press Enter to change directory.
Start typing to filter directories.
Press Tab to turn on/off case sensitive search.

Supported extra symbols:

    * - any number of any character
    ? - any character
    $ - end of path

For more info: "j --help"

### Example

Type "j" and press Enter in the terminal to launch fastcd

        /home/frazenshtein/Soft
        /home/frazenshtein/Soft/fastcd
        /usr/lib/pyhon2.7
        /usr/lib
    ->  /home/frazenshtein/Soft/fastcd/.git

    Fastcd to:

Type "fa" to filter list of directories

        /home/frazenshtein/Soft/fastcd
    ->  /home/frazenshtein/Soft/fastcd/.git

    Fastcd to: fa

Press Up and Enter to cd to /home/frazenshtein/Soft/fastcd

If you close terminal or open another one and launch fastcd ("j") you will get updated list of directories

        /home/frazenshtein/Soft
        /usr/lib/pyhon2.7
        /usr/lib
        /home/frazenshtein/Soft/fastcd/.git
    ->  /home/frazenshtein/Soft/fastcd

    Fastcd to:

Now you can just press Enter to cd to the last visited directory

### INSTALLATION

Requires bash + python 2.7 + extra modules
Just type the following to install required python modules.

    pip install --user urwid psutil

Get tool

    git clone https://github.com/frazenshtein/fastcd

Each user who wants to use fastcd should source the
set.sh file into their bashrc, i.e from within ~/.bashrc just add
a line:

    source PATH_TO_FASTCD/set.sh

And reload bashrc in your terminal:

    source ~/.bashrc