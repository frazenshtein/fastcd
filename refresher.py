#!/usr/bin/env python

import os
import sys
import time
import fcntl
import logging
from os.path import expanduser
from argparse import ArgumentParser

try:
    import psutil
except ImportError:
    print("Cannot import psutil module. Install it first 'pip install --user psutil' and reload bashrc 'source ~/.bashrc'")
    exit(1)

import helper

log = None

def parseCommandLine():
    parser = ArgumentParser()
    parser.add_argument("--daemon", dest="Daemon", action="store_true")
    parser.add_argument("--restart", dest="Restart", action="store_true")
    parser.add_argument("--log", dest="LogPath", default="/dev/null")
    parser.add_argument("--verbose", dest="Verbose", action="store_true")
    parser.add_argument("--timestamps", dest="TimeStamps", action="store_true")

    args = parser.parse_args()
    args.LogPath = os.path.abspath(os.path.expanduser(args.LogPath))
    return args

def setupLogger(verbose, timeStamps=False):
    global log

    log = logging.getLogger()
    log.setLevel(logging.DEBUG if verbose else logging.ERROR)
    if timeStamps:
        format = "[%(asctime)s] %(message)s"
    else:
        format = "%(message)s"

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch_format = logging.Formatter(format)
    ch.setFormatter(ch_format)
    log.addHandler(ch)

def daemonize(filename):
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    se = file(filename, "w", 0)
    os.dup2(se.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

def updatePathList(path, filename, limit):
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
    with open(filename + ".tmp", "w") as file:
        for path in paths:
            file.write("%s\n" % path)
    # Change file atomically
    os.rename(filename + ".tmp", filename)

def pstuilProcMethod(proc, method):
    val = getattr(proc, method)
    if psutil.__version__.startswith("1"):
        return val
    return val()

def getProcessExe(proc):
    return pstuilProcMethod(proc, "exe")

def getProcessName(proc):
    return pstuilProcMethod(proc, "name")

def getProcessCmdline(proc, join=False):
    cmdline = pstuilProcMethod(proc, "cmdline")
    if join:
        return " ".join(cmdline)
    return cmdline

def getShells(terminalEmulators, shell):
    shells = []
    log.debug("Obtaining list of shells")
    for proc in psutil.process_iter():
        try:
            if getProcessName(proc) in terminalEmulators:
                log.debug("Terminal emulator: {}".format(proc))
                for candidate in proc.get_children():
                    try:
                        log.debug("Possible shell: {}".format(proc))
                        if getProcessExe(candidate).endswith(shell):
                            log.debug("Shell: {}".format(proc))
                            shells.append(candidate)
                    except (psutil.NoSuchProcess, psutil.AccessDenied): pass
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

def prepareEnvironment(config):
    # Create directories
    for param in ["paths_history", "stored_paths"]:
        path = expanduser(config[param])
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        # Create file
        with open(path, "a"):
            pass

def main(config):
    def _updatePathList(path):
        path = helper.replaceHomeWithTilde(path)
        updatePathList(path, config["paths_history"], config["paths_history_limit"])

    shellTimeout = 0.0
    timeout = config["path_updater_delay"]
    shells = getShells(config["terminal_emulators"], config["shell"])
    lastCwds = getCwds(shells)

    log.debug("Updating paths of currently launched shells")
    for path in lastCwds.values():
        log.debug("Shell's current path: %s" % path)
        _updatePathList(path)

    while True:
        log.debug("Obtaining shell's paths")
        for proc in shells:
            try:
                procCwd = getCleanPath(proc.getcwd())
                log.debug("Shell {} current path: {}".format(proc.pid, procCwd))
                if procCwd != lastCwds[proc.pid]:
                    log.debug("Shell {} changed path. Was: {}".format(proc.pid, lastCwds[proc.pid]))
                    lastCwds[proc.pid] = procCwd
                    _updatePathList(procCwd)
            except psutil.NoSuchProcess: pass

        time.sleep(timeout)
        shellTimeout += timeout
        if shellTimeout >= config["search_for_new_shells_delay"]:
            log.debug("Searing for new shells")
            shellTimeout = 0.0
            shells = getShells(config["terminal_emulators"], config["shell"])
            newCwds = getCwds(shells)
            # Get paths of new shells
            paths = set(newCwds.values()).difference(lastCwds.values())
            for path in paths:
                log.debug("Found new shell with cwd: %s" % path)
                _updatePathList(path)
            lastCwds = newCwds

def restart(lockfile):
    if os.path.exists(lockfile):
        with open(lockfile) as file:
            pid = file.read()
        if pid:
            try:
                proc = psutil.Process(int(pid))
                if getProcessName(proc) == "python" and os.path.basename(sys.argv[0]) in getProcessCmdline(proc, join=True):
                    proc.terminate()
                    proc.wait()
            except psutil.NoSuchProcess: pass

if __name__ == '__main__':
    args = parseCommandLine()
    setupLogger(args.Verbose, args.TimeStamps)

    config = helper.loadConfig("refresher")
    config["paths_history"] = expanduser(config["paths_history"])
    lockfile = os.path.join(os.path.dirname(expanduser(config["paths_history"])), "lock")

    prepareEnvironment(config)

    if args.Daemon:
        daemonize(args.LogPath)
    if args.Restart:
        restart(lockfile)

    mode = "r+" if os.path.exists(lockfile) else "w+"
    with open(lockfile, mode) as lock:
        try:
            fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            log.error("Another instance of %s is launched" % sys.argv[0])
            exit(1)
        lock.truncate()
        lock.write(str(os.getpid()))
        lock.flush()

        main(config)
