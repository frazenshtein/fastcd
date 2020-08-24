#!/usr/bin/env python3
try:
    from fastcd.jumper import main
except ImportError:
    from jumper import main

main()
