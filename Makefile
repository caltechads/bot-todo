VERSION = 0.1.0

PACKAGE = bot-todo

version::
	@echo $(VERSION)

clean:
	rm -rf *.tar.gz dist build *.egg-info *.rpm
	find . -name "*.pyc" | xargs rm
	find . -name "__pycache__" | xargs rm -rf

dist: clean
	@python -m build

release: dist
	@bin/release.sh

MAIN_BRANCH = master

# --- Gate checks ---
check-branch:
	@branch="$$(git rev-parse --abbrev-ref HEAD)"; \
	[[ "$$branch" == "$(MAIN_BRANCH)" ]] || { echo "You're not on $(MAIN_BRANCH); aborting."; exit 1; }

check-clean:
	@[[ -z "$$(git status --untracked-files=no --porcelain)" ]] || { echo "You have uncommitted changes; aborting."; exit 1; }

# --- Shared release pipeline ---
# Expects BUMP=dev|patch|minor|major
_release: check-branch check-clean clean
	@echo "Releasing $(BUMP) version"
	@bump-my-version "$(BUMP)"
	@python -m build
	@bin/release.sh

# --- Explicit release targets (better tab-complete & discoverability) ---
release-dev:
	$(MAKE) _release BUMP=dev

release-patch:
	$(MAKE) _release BUMP=patch

release-minor:
	$(MAKE) _release BUMP=minor

release-major:
	$(MAKE) _release BUMP=major

pypi: dist
	@twine upload dist/*

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
