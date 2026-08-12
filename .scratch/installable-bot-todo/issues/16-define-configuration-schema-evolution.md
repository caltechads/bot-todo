# Define configuration schema evolution policy

Type: grilling
Status: resolved
Blocked by: 07, 11

## Question

How may configuration schema version 1 evolve, and when should bot-todo reject,
preserve, or migrate older and newer configuration files?

## Answer

Configuration Schema Version 1 is a closed compatibility contract. Its accepted
keys, required fields, value types, validation rules, and meanings remain stable.
Clarifications that do not alter that contract may remain Version 1; accepting
new keys, rejecting previously valid configuration, or changing existing meaning
requires a new Configuration Schema Version.

Each `bot-todo` release explicitly declares the configuration versions it
supports. Normal commands load a supported version without rewriting it and
reject any unsupported older or newer version before repository access or any
filesystem mutation. JSON mode reports `unsupported_config_version` with the
encountered version and the supported versions; malformed files using a
supported version remain `invalid_config`. Unsupported configurations are never
guessed at, partially parsed, preserved through a rewrite, or downgraded.

Adding support for a new configuration version is additive while existing
versions remain supported. Users need not migrate merely because a newer version
exists; they migrate when they need its features. After `bot-todo` 1.0, removing
a supported configuration version or changing its documented contract requires
a major package release.

Phase 1 provides no configuration migration machinery. A future schema-version
proposal must define its own smallest sufficient upgrade path; documented manual
editing is acceptable when that is simpler than a command. Any automated
migration must be explicit and opt-in, accept only a supported older source,
validate both source and result, replace atomically, retain a recoverable backup,
and never downgrade a newer configuration. Normal commands never migrate
implicitly.

Security or corruption defects may be corrected within a schema version only
when the documented accepted structure and meaning remain intact. A correction
that changes that contract still requires a new Configuration Schema Version.
