PY_SOURCES = bot.py $(wildcard irc/*.py irc/plugins/*.py)
PY_TEST_SOURCES = test_server.py $(wildcard lib/*.py lib/test/*.py)

.PHONY: all
all: test

.PHONY: help
help:
	@ echo "  Available targets:"
	@ echo "    make test"
	@ echo "    make coverage"
	@ echo "    make coverage-html"

.PHONY: test
test: pylint flake8 typing unittest

.PHONY: clean
clean:
	rm -f .coverage
	rm -rf htmlcov .mypy_cache
	find */ -name __pycache__ -exec rm -rf '{}' +


# Yet to be enabled.
.PHONY: pylint
pylint:

.PHONY: flake8
flake8:
	flake8 bot.py irc

.PHONY: typing
typing:
	mypy --namespace-packages -m bot -m irc.client -m irc.plugin -m irc.message -m irc.user

.PHONY: unittest
unittest:
	./test.sh


.PHONY: coverage
coverage: .coverage
	coverage report

.coverage: $(PY_SOURCES) $(PY_TEST_SOURCES)
	./test.sh -c

.PHONY: coverage-html
coverage-html: htmlcov/index.html
	xdg-open file://$(PWD)/htmlcov/index.html

htmlcov/index.html: .coverage
	coverage html
