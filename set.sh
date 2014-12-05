#!/usr/bin/env bash

# Add to ~/.bashrc:
#   source "/home/$USER/Soft/fastcd/set.sh"
# Do not forget to install extra modules: pip install --user urwid psutil

FASTCDTOOLS="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
JUMPERTOOL="$FASTCDTOOLS/jumper.py"
REFRESHERTOOL="$FASTCDTOOLS/refresher.py"
# Launch refresher to collect visited dirs
python $REFRESHERTOOL --daemon
# Set (J)umper
function j {
    PATHFILE="/tmp/`date +%s`.path"
    python $JUMPERTOOL --escape-special-symbols -o $PATHFILE $@
    if [[ ! $@ == "--help" ]] && [[ ! $@ == "-h" ]]
    then
        OUTPUTPATH=`cat $PATHFILE`
        rm $PATHFILE
        if [[ ! -z "$OUTPUTPATH" ]]
        then
            # Eval is required to interpolate ~
            eval cd $OUTPUTPATH
        fi
    fi
}
alias j='j'
