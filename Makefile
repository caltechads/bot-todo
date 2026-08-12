VERSION = 0.1.0

PACKAGE = bot_todo

version::
	@echo $(VERSION)

pytest::
	@if [ -z "$(ARGS)" ]; then \
		uv run pytest -c pyproject.toml; \
	else \
		uv run pytest -c pyproject.toml $(ARGS); \
	fi;

napoleon-gate:
	@python ~/bin/check_napoleon_gate.py --target src

napoleon-gate-strict:
	@python ~/bin/check_napoleon_gate.py --target src --strict

napoleon-gate-baseline:
	@python ~/bin/check_napoleon_gate.py --target src --write-baseline
