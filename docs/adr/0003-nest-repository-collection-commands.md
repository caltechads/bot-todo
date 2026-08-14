# 3. Nest Repository Collection commands

Status: accepted (2026-08-14)

Issue 04 kept the public command list flat. Collection management cannot: `add`
already creates a task, so `bot-todo add .` cannot mean “append a Repository
Entry.” A nested `repos` group (`path`, `list`, `add`, `remove`) names the
entries without colliding with task commands. JSON keeps `command` as the
single token `repos` and discriminates with `data.operation`.
