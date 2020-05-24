#!/usr/bin/env python3

from setuptools import setup, find_packages

if __name__ == "__main__":
    setup(
        name="SoupBot",
        description="A pluggable IRC bot",
        packages=find_packages(),
        entry_points={
            'console_scripts': [
                'soupbot = irc.__main__:start_event_loop',
            ],
        },
    )
