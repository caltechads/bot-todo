# Verify UV tool packaging and bundled-resource contracts

Type: research
Status: resolved

## Question

What current UV and Python packaging contracts govern tool entry points, source layouts, build backends, package data, and runtime access to bundled skill assets when installing from a local checkout, Git URL, or built distribution?

## Answer

### Authoritative facts

- `uv tool install <PACKAGE>` creates a persistent isolated environment and exposes the package's declared executables in UV's tool bin directory. It accepts registry packages and direct sources including local directories, Git URLs/refs, and built wheel paths. Normal directory installs are copied; `--editable` deliberately retains a checkout dependency. See [UV tools](https://docs.astral.sh/uv/concepts/tools/) and [`uv tool install`](https://docs.astral.sh/uv/reference/cli/#uv-tool-install).
- `[project.scripts]` is the standard console-entry-point declaration, and an explicit `[build-system]` is required for reliable project packaging. See the [PyPA entry-point specification](https://packaging.python.org/en/latest/specifications/entry-points/#use-for-scripts) and [UV build-system guidance](https://docs.astral.sh/uv/concepts/projects/config/#build-systems).
- `uv_build` is UV's pure-Python backend. Its default normalized layout maps `bot-todo` to `src/bot_todo/`; the module directory is included in wheels and source distributions, so small runtime assets should live below that import package. See [UV's build backend](https://docs.astral.sh/uv/concepts/build-backend/) and [file-inclusion rules](https://docs.astral.sh/uv/concepts/build-backend/#file-inclusion-and-exclusion).
- `importlib.resources.files()` exposes packaged resources as `Traversable` objects without assuming they are physical checkout paths. `as_file()` temporarily materializes a real path when required; whole-directory support is available on Python 3.12 and newer. See [`importlib.resources`](https://docs.python.org/3/library/importlib.resources.html).
- `uv build --no-sources` verifies that a distribution builds without UV-only local source mappings. See [UV's build and publish guide](https://docs.astral.sh/uv/guides/package/).

### Architecture implications

The native minimal shape is `src/bot_todo/` with the canonical skill below `src/bot_todo/skill_assets/todo/`, a `bot-todo = "bot_todo.cli:main"` script, and an explicit build backend. Runtime code should locate assets with `importlib.resources`, never `Path(__file__)`, the current directory, or checkout-relative traversal.

Keep one canonical packaged skill tree rather than a root copy plus build hook. Use ordinary `uv tool install .` for local installation, editable mode only during development, commit-pinned Git URLs for reproducible source installs, and built wheels for release verification.

Packaging acceptance should build with `uv build --no-sources`, inspect both wheel and source distribution for skill assets, install the wheel as an isolated tool, run outside or after removal of the checkout, and exercise skill installation. The current `requires-python = ">=3.14"` is not justified by existing code and should be decided explicitly in the runtime-support ticket.
