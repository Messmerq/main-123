.PHONY: run test check demo
PYTHON ?= python3

run:
	$(PYTHON) src/main.py

test:
	$(PYTHON) -m unittest discover -s tests -v

check:
	$(PYTHON) -m compileall -q src tests

demo:
	sh run.sh --script examples/stage5.txt --no-repl
