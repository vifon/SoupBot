.PHONY: all test pylint flake8 typing unittest

all: test

test: pylint flake8 typing unittest

# Yet to be enabled.
pylint:

flake8:
	flake8 bot.py irc

typing:
	mypy -m bot -m irc.client -m irc.plugin -m irc.message -m irc.user

unittest:
	./test.sh
