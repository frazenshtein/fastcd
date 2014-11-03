fastcd
======

## Fastcd


## Far-like directory alternative history for linux

These scripts allow you to quickly navigate to the desired directory
that have been recently visited.

### USAGE

Just enter "j" in the terminal and start typing the name of the desired directory.
You can use arrows and Page Up/Down to navigate the list.
Press Esc to exit.
Press Enter to change directory.

### INSTALLATION

Requires bash + python 2.7 + extra modules
Just type the following to install required python modules.

    pip install --user urwid psutil

Each user who wants to use fastcd should source the
set.sh file into their bashrc, i.e from within ~/.bashrc just add
a line:

    source PATH_TO_FASTCD/set.sh

And update ~/.bashrc:

    source ~/.bashrc