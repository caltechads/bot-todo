# Choose the CLI framework

Type: grilling
Status: resolved
Blocked by: 04

## Question

Does the settled public CLI contract justify replacing `argparse` with Click, or is retaining the standard-library parser the smaller sufficient design?

## Answer

Retain the standard-library `argparse` parser. The settled interface is a flat, deterministic, non-interactive command tree; Click provides no required capability that offsets a new runtime dependency, a parser rewrite, and additional exception adaptation. Do not add Click or a CLI-framework abstraction.

Use one small `ArgumentParser` subclass for the root parser and every subparser. It must:

- disable long-option abbreviation everywhere, because the root `allow_abbrev=False` setting does not propagate to child parsers;
- disable ANSI-colored help where the selected Python runtime supports argparse color;
- raise an internal usage exception from `error()` rather than printing and exiting.

The top-level `main()` boundary owns rendering and status mapping. It returns `0` for success, `1` for operational/domain/filesystem failures, `2` for command-line usage failures, and `3` for aggregate partial failures. For parse failures before a namespace exists, detect an exact `--json` token in raw arguments before the `--` terminator; do not accept prefixes such as `--js`. That choice determines whether the stable JSON or human error renderer handles the failure.

Keep `argparse.Namespace` inside parsing and command dispatch. Task Repository operations receive explicit values rather than parser objects; replacing the current `TodoStore.add` and `TodoStore.edit` namespace parameters is an internal cleanup, not a framework migration.

Use native human-readable argparse help and version output with successful exit status, even when `--json` is present. Exact help layout remains noncontractual. Tests must cover rejected option abbreviations at root and subcommand levels, JSON usage errors raised before parsing completes, native help/version success, and the four settled exit-code classes.
