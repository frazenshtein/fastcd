#!/usr/bin/env python

from __future__ import with_statement

import os.path

import setuptools


def get_version(fname=os.path.join('fastcd', '__init__.py')):
    with open(fname) as f:
        for line in f:
            if line.startswith('__version__'):
                return eval(line.split('=')[-1])


def get_long_description():
    with open('README.rst') as f:
        return f.read()


setuptools.setup(
    name="fastcd",
    license="GPLv2",
    version=get_version(),
    description="Navigation tool for Linux/MacOs",
    long_description=get_long_description(),
    author="frazenshtein",
    author_email="ivansduck@gmail.com",
    url="https://github.com/frazenshtein/fastcd",
    packages=["fastcd"],
    package_data={"fastcd": ["config.json", "fastcd_hook.sh"]},
    python_requires='>=3.4',
    install_requires=["urwid>=1.2"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development",
        "Topic :: Utilities",
    ],
    scripts=["bin/fastcd"],
)
