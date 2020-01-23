.PHONY: all test pylint typing

all: test

test: pylint typing

pylint:

typing:
	mypy -m bot -m irc.client -m irc.plugin -m irc.message -m irc.user
