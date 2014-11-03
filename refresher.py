#!/usr/bin/env python

import os
import sys
import time
import fcntl
from argparse import ArgumentParser

import psutil

def parseCommandLine():
    parser = ArgumentParser()
    parser.add_argument("-o", "--output", dest="Output", metavar="FILE", default="~/.fastcd")
    parser.add_argument("--path-timeout", dest="PathTimeout", metavar="FLOAT", default=0.5)
    parser.add_argument("--process-timeout", dest="ProcessTimeout", metavar="FLOAT", default=5.0)
    parser.add_argument("--daemon", dest="Daemon", action="store_true")

    args = parser.parse_args()
    args.Output = os.path.expanduser(args.Output)
    args.Lock = args.Output + ".lock"
    return args

def daemonize(stderr):
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    se = file(stderr, "w", 0)
    os.dup2(se.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

def updatePathList(path, filename, limit=5000):
    if os.path.exists(filename):
        with open(filename) as file:
            paths = [l.strip() for l in file.readlines()]
    else:
        paths = []
    # Path already in data
    if path in paths:
        # Put path down
        paths.remove(path)
    paths.append(path)

    paths = paths[:limit]
    with open(filename, "w") as file:
        for path in paths:
            file.write("%s\n" % path)

def getProcessExe(proc):
    if psutil.__version__.startswith("1"):
        return proc.exe
    return proc.exe()

def getShells(shellDaemons, shell="bash"):
    shells = []
    for proc in psutil.process_iter():
        try:
            name = getProcessExe(proc).rsplit(os.sep, 1)[1]
            if name in shellDaemons:
                for candidate in proc.get_children():
                    if getProcessExe(candidate).endswith(shell):
                        shells.append(candidate)
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    return shells

def getCwds(shells):
    d = {}
    for proc in shells:
        try:
            d[proc.pid] = getCleanPath(proc.getcwd())
        except psutil.NoSuchProcess: pass
    return d

def getCleanPath(path):
    return path.replace(" (deleted)", "")

def main(args):
    daemons = [
        "konsole",
        "sshd",
        "tmux",
        "terminator",
        "gnome-terminal",
        "xfce4-terminal",
    ]

    shellTimeout = 0.0
    timeout = args.PathTimeout
    shells = getShells(daemons)
    lastCwds = getCwds(shells)

    if not os.path.exists(args.Output):
        for path in lastCwds.values():
            updatePathList(path, args.Output)


    while True:
        for proc in shells:
            try:
                procCwd = getCleanPath(proc.getcwd())
                if procCwd != lastCwds[proc.pid]:
                    lastCwds[proc.pid] = procCwd
                    updatePathList(procCwd, args.Output)
            except psutil.NoSuchProcess: pass

        time.sleep(timeout)
        shellTimeout += timeout
        if shellTimeout >= args.ProcessTimeout:
            shellTimeout = 0.0
            shells = getShells(daemons)
            lastCwds = getCwds(shells)

if __name__ == '__main__':
    args = parseCommandLine()

    if args.Daemon:
        daemonize("/tmp/%s_stderr.log" % os.path.basename(sys.argv[0]))

    with open(args.Lock, "w") as lock:
        try:
            fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print("Another instance of %s is launched" % sys.argv[0])
            exit(1)

        main(args)
