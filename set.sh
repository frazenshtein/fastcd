#!/usr/bin/env bash

# Add to ~/.bashrc:
#   source "$HOME/Soft/fastcd/set.sh"
# Do not forget to install extra modules: pip install --user urwid

FASTCDTOOLS="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
JUMPERTOOL="$FASTCDTOOLS/jumper.py"

# Set hook to collect visited dirs
fastcd_hook() {
    (python3 $JUMPERTOOL --add-path "$(pwd)" 2>>${FASTCDTOOLS}/errors.log 1>&2 &) &>/dev/null
}

case $PROMPT_COMMAND in
    *fastcd_hook*)
        ;;
    *)
        PROMPT_COMMAND="${PROMPT_COMMAND:+$(echo "${PROMPT_COMMAND}" | awk '{gsub(/; *$/,"")}1') ; }fastcd_hook"
        ;;
esac

# Set (J)umper
function j {
    PATHFILE="/tmp/`date +%s`.path"
    python3 $JUMPERTOOL --escape-special-symbols -o $PATHFILE $@
    if [[ $? -eq 0 ]] && [[ ! $@ == "--help" ]] && [[ ! $@ == "-h" ]] && [[ ! $@ == "--list-shortcut-paths" ]] && [[ ! $@ == "-l" ]]
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
alias j='j'
