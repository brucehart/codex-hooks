.PHONY: test check install

test:
	python3 -m unittest discover -s tests -v

check: test
	python3 -m py_compile src/codex_api_cost.py scripts/install.py
	bash -n scripts/install.sh

install:
	./scripts/install.sh
