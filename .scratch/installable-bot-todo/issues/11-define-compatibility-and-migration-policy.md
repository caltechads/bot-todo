# Define compatibility and migration policy

Type: grilling
Status: resolved
Blocked by: 01, 04, 05

## Question

Which current behaviors are immutable compatibility requirements, how should format and JSON schema versions evolve, and what explicit policy should govern unsupported or future task-data versions without requiring a Phase 1 migration?

## Answer

### Compatibility boundary

Task Data Format 1 preserves the semantics of every document valid under the
current contract: task fields, P0/P1/P2 ordering, lifecycle transitions,
blocker completion rules, monotonic identifiers and their high-water mark,
claims, cancellation reasons, and the recent-Done/archive split. It also keeps
accepting the currently tolerated blank lines and noncanonical field order.

Mutations may continue rewriting documents into canonical Markdown. Exact
whitespace, byte layout, unreleased script paths, legacy human output, and
other implementation quirks are not compatibility promises. The first public
CLI and JSON contracts begin with the previously resolved public interface.

### Task Data Format evolution

Task Data Format versions describe the Markdown structure and lifecycle
semantics independently of the `bot-todo` release and JSON Schema Version.
Format 1 remains format 1 only while existing readers cannot misread the data
and every document valid under its written contract remains valid.

An implementation may accept additional noncanonical input within format 1
only when it still emits valid format-1 documents. Reinterpreting existing
data, adding required fields or lifecycle states, or rejecting a document that
the written format-1 contract accepts requires a new Task Data Format version.

### Unsupported versions and migration

Normal task commands, including `validate`, reject any declared Task Data
Format version they do not support without writing either task file. JSON mode
uses the additive `unsupported_format_version` error code and reports the
encountered and supported versions. A newer version is never guessed at,
partially parsed, downgraded, or automatically rewritten.

Phase 1 reads and writes format 1 and provides no migration command. Before a
future release makes format 2 the normal write format, it must provide an
explicit, opt-in, validated, and recoverable migration from format 1. Normal
commands may then require that migration rather than carrying multiple write
formats indefinitely. Automatic migration and speculative migration machinery
remain out of scope.

### JSON Schema Version evolution

JSON Schema Version 1 permits additive object keys, commands with their own
result shapes, and values explicitly documented as extensible, including error
codes. Existing keys retain their presence, meaning, type, and nullability.
Removing or reinterpreting a key, changing its type or nullability, or extending
a closed enumeration requires a new JSON Schema Version.

`bot-todo` emits one JSON schema and provides no schema-negotiation option.
After `bot-todo` 1.0, a breaking JSON schema change requires both a schema
version increment and a major package release. Concurrent schema support or a
`--schema-version` option should be added only when real consumers require it.

### Contract defects

The written contracts, not accidental implementation behavior, define
compatibility. Data-loss, corruption, and security defects may be corrected
within the same version. A correction that rejects data valid under the written
Task Data Format or breaks the documented JSON contract still requires the
corresponding version change.
