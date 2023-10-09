#!/usr/bin/env bash

FASTCDDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
JUMPERTOOL="$FASTCDDIR/jumper.py"
FASTCDCONFDIR="$HOME/.local/share/fastcd"

# Set hook to track visited dirs
function _fastcd_hook() {
    (python3 $JUMPERTOOL --add-path "$(pwd)" 2>>${FASTCDCONFDIR}/errors.log 1>&2 &) &>/dev/null
}

case $PROMPT_COMMAND in
    *_fastcd_hook*)
        ;;
    *)
        PROMPT_COMMAND="${PROMPT_COMMAND:+$(echo "${PROMPT_COMMAND}" | awk '{gsub(/; *$/,"")}1') ; }_fastcd_hook"
        ;;
esac

function fastcd {
    PATHFILE="/tmp/fastcd.$$.`date +%s`.path"
    python3 $JUMPERTOOL --escape-special-symbols -o $PATHFILE $@
    if [[ $? -eq 0 ]] && [[ $# -eq 0 ]]
    then
        OUTPUTPATH=`cat $PATHFILE`
        rm $PATHFILE
        if [[ ! -z "$OUTPUTPATH" ]]
        then
            # Eval is required to interpret ~
            eval cd $OUTPUTPATH
        fi
    fi
}
