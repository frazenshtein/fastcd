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
    parser.add_argument("--path-timeout", dest="PathTimeout", metavar="FLOAT", default=0.2)
    parser.add_argument("--process-timeout", dest="ProcessTimeout", metavar="FLOAT", default=5.0)
    parser.add_argument("--daemon", dest="Daemon", action="store_true")
    parser.add_argument("--restart", dest="Restart", action="store_true")

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

def updatePathList(path, filename, limit=3000):
    if os.path.exists(filename):
        with open(filename) as file:
            paths = [l.strip() for l in file.readlines()]
    else:
        paths = []
    # Path already in data
    if path in paths:
        # Raise path
        paths.remove(path)
    paths = [path] + paths[:limit]
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
            if proc.name in shellDaemons:
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

def getUserHomeDir():
    return os.path.realpath(os.environ["HOME"])

def replaceHomeWithTilde(path, home):
    if path.startswith(home):
        path = path.replace(home, "~")
    return path

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
    userHome = getUserHomeDir()

    if not os.path.exists(args.Output):
        for path in lastCwds.values():
            path = replaceHomeWithTilde(path, userHome)
            updatePathList(path, args.Output)

    while True:
        for proc in shells:
            try:
                procCwd = getCleanPath(proc.getcwd())
                if procCwd != lastCwds[proc.pid]:
                    lastCwds[proc.pid] = procCwd
                    path = replaceHomeWithTilde(procCwd, userHome)
                    updatePathList(path, args.Output)
            except psutil.NoSuchProcess: pass

        time.sleep(timeout)
        shellTimeout += timeout
        if shellTimeout >= args.ProcessTimeout:
            shellTimeout = 0.0
            shells = getShells(daemons)
            lastCwds = getCwds(shells)

def perror(line):
    print(line)
    exit(1)

def restart(args):
    if os.path.exists(args.Lock):
        with open(args.Lock) as file:
            pid = file.read()
        if pid:
            try:
                proc = psutil.Process(int(pid))
                if proc.name == "python" and os.path.basename(sys.argv[0]) in proc.cmdline:
                    proc.terminate()
                    proc.wait()
            except psutil.NoSuchProcess: pass

if __name__ == '__main__':
    args = parseCommandLine()

    if args.Daemon:
        daemonize("/tmp/%s_stderr.log" % os.path.basename(sys.argv[0]))

    if args.Restart:
        restart(args)

    with open(args.Lock, "r+") as lock:
        try:
            fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            perror("Another instance of %s is launched" % sys.argv[0])
        lock.truncate()
        lock.write(str(os.getpid()))
        lock.flush()

        main(args)
