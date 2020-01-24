.PHONY: all test pylint typing

all: test

test: pylint flake8 typing

# Yet to be enabled.
pylint:

flake8:
	flake8 bot.py irc

typing:
	mypy -m bot -m irc.client -m irc.plugin -m irc.message -m irc.user
