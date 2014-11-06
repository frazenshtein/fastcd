fastcd
======

### Briefly

These scripts allow you to quickly navigate to the desired directory that has been recently visited.
The utility was written because of the great longing for FarManager and it's plug-in alternative history.

### Usage

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

### Tips

Missing or non-existent directories will be displayed dimmed and marked with '*'.
However, if you press Enter twice, you will cd to the nearest existing directory.

### Example

Type "j" and press Enter in the terminal to launch fastcd

    Fastcd to:

    ->  /home/frazenshtein/Soft
        /home/frazenshtein/Soft/fastcd/.git
        /usr/lib/pyhon2.7
        /home/frazenshtein/Soft/fastcd/
        /usr/lib

Type "fa" to filter list of directories

    Fastcd to: fa

    ->  /home/frazenshtein/Soft/fastcd/.git
        /home/frazenshtein/Soft/fastcd

Press Down and Enter to cd to /home/frazenshtein/Soft/fastcd

If you close and open terminal or open another one and launch fastcd ("j") you will get updated list of directories

    Fastcd to:

    ->  /home/frazenshtein/Soft/fastcd
        /home/frazenshtein/Soft
        /home/frazenshtein/Soft/fastcd/.git
        /usr/lib/pyhon2.7
        /usr/lib

Now you can just press Enter to cd to the last visited directory

### Installation

Requires bash + python 2.7 + extra modules
Just type the following to install required python modules:

    pip install --user urwid psutil

Get the utility:

    git clone https://github.com/frazenshtein/fastcd

Each user who wants to use fastcd should source the
set.sh file into their bashrc, i.e from within ~/.bashrc just add
a line:

    source PATH_TO_FASTCD/set.sh

And reload bashrc in your terminal:

    source ~/.bashrc