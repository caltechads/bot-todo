# Choose the package and repository layout

Type: grilling
Status: resolved
Blocked by: 01, 02

## Question

What minimal source, test, and packaged-asset layout makes this repository primarily the installable `bot-todo` package while keeping the `todo` skill co-located, distributable, and discoverable through supported runtime resource APIs?

## Answer

Use one standard source package, one canonical packaged skill tree, and root-level tests:

```text
pyproject.toml
src/
└── bot_todo/
    ├── __init__.py
    ├── cli.py
    └── skill_assets/
        └── todo/
            ├── SKILL.md
            └── agents/
                └── openai.yaml
tests/
├── test_cli.py
└── test_distribution.py
```

`pyproject.toml` declares the build backend and the `bot-todo = "bot_todo.cli:main"` console entry point. `bot_todo.cli` initially retains the existing compatibility-sensitive behavior together; later decisions may add modules only when their responsibilities are known.

The `todo` skill under `skill_assets` is the sole canonical copy. Runtime code and tests access it through `importlib.resources`; packaging must not rely on checkout-relative paths, asset-copy hooks, or duplicate source trees. The exact asset contents remain owned by [Define the bundled skill asset model](09-define-skill-asset-model.md).

`test_cli.py` owns CLI and task-data behavior. `test_distribution.py` verifies built artifacts, packaged-resource access, and isolated installed-tool behavior. Tests are not included in the installed package.

Implementation makes one atomic migration: move the CLI, tests, and skill assets; update repository instructions; and remove `main.py` plus the root `skills/todo/` tree. Do not add a compatibility wrapper, `bot_todo.__main__`, empty future modules, or placeholder package directories.
