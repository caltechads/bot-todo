# Graph Report - .  (2026-08-12)

## Corpus Check
- Corpus is ~39,956 words - fits in a single context window. You may not need a graph.

## Summary
- 771 nodes · 1554 edges · 36 communities (28 shown, 8 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 151 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Skill Installation
- Domain and Agent Docs
- Configuration Tests
- Task Presentation
- Command Execution
- Architecture Research
- Skill Reconciliation
- Repository Selection
- Aggregate Query Tests
- Repository Parsing
- CLI Parsing
- Aggregate Runner
- Configuration Loading
- Repository Test Helpers
- Markdown Document Parsing
- Repository Store
- Task Field Utilities
- Configured CLI Tests
- Distribution Packaging
- Archive Persistence
- JSON Output Tests
- JSON Serialization
- Repository Transactions
- Core CLI Tests
- Aggregate Failure Tests
- CLI Grammar Tests
- Lifecycle Tests
- Skill Guidance Tests
- Initialization and Identity
- File Safety Tests
- Repository Locking
- Archive Behavior Tests
- Aggregate Selector Tests
- Task Claims
- Test Package
- bot-todo Entry Point

## God Nodes (most connected - your core abstractions)
1. `TodoError` - 77 edges
2. `Task` - 52 edges
3. `invoke()` - 45 edges
4. `TodoStore` - 42 edges
5. `CommandOutcome` - 31 edges
6. `SkillInstaller` - 28 edges
7. `RepositoryCollection` - 27 edges
8. `TodoCliTestCase` - 27 edges
9. `CommandRunner` - 26 edges
10. `RepositorySnapshot` - 20 edges

## Surprising Connections (you probably didn't know these)
- `CLI Commands` --semantically_similar_to--> `bot-todo`  [INFERRED] [semantically similar]
  README.md → CONTEXT.md
- `Todo Skill` --semantically_similar_to--> `todo skill`  [INFERRED] [semantically similar]
  src/bot_todo/skill_assets/todo/SKILL.md → CONTEXT.md
- `Repository Selection` --semantically_similar_to--> `Task Repository`  [INFERRED] [semantically similar]
  README.md → CONTEXT.md
- `T004 Aggregate Read Queries` --semantically_similar_to--> `Aggregate Query`  [INFERRED] [semantically similar]
  TODO.md → CONTEXT.md
- `Agent Skill Installation` --semantically_similar_to--> `Managed Skill Installation`  [INFERRED] [semantically similar]
  README.md → CONTEXT.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Four-Phase Cumulative Delivery** — _scratch_installable_bot_todo_phase_1_plan_phase_1_extract_the_single_repository_core, _scratch_installable_bot_todo_phase_2_plan_phase_2_complete_the_public_single_repository_cli, _scratch_installable_bot_todo_phase_3_plan_phase_3_add_aggregate_read_queries, _scratch_installable_bot_todo_phase_4_plan_phase_4_bundle_and_install_the_todo_skill [EXTRACTED 1.00]
- **Aggregate Query Contract** — _scratch_installable_bot_todo_issues_07_define_repository_configuration_repository_collection, _scratch_installable_bot_todo_issues_08_define_aggregate_query_semantics_deterministic_aggregate_ordering, _scratch_installable_bot_todo_issues_12_define_concurrency_and_failure_policy_aggregate_partial_failure, _scratch_installable_bot_todo_phase_3_plan_phase_3_add_aggregate_read_queries [INFERRED 0.95]
- **Bundled Skill Delivery Contract** — _scratch_installable_bot_todo_issues_02_verify_uv_packaging_contracts_verify_uv_tool_packaging_and_bundled_resource_contracts, _scratch_installable_bot_todo_issues_03_verify_agent_skill_installation_contracts_verify_agent_skill_installation_contracts, _scratch_installable_bot_todo_issues_09_define_skill_asset_model_canonical_packaged_skill_tree, _scratch_installable_bot_todo_issues_10_define_safe_skill_installation_managed_skill_installation, _scratch_installable_bot_todo_phase_4_plan_phase_4_bundle_and_install_the_todo_skill [INFERRED 0.95]
- **Canonical Task Management** — context_bot_todo, context_task_repository, readme_cli_commands, src_bot_todo_skill_assets_todo_skill_todo_skill, todo_bot_todo_backlog [INFERRED 0.95]
- **Aggregate Query Contract** — context_aggregate_query, readme_repository_selection, src_bot_todo_skill_assets_todo_skill_repository_scope_policy, todo_t004_aggregate_read_queries [INFERRED 0.95]
- **Archive Decoupling Model** — context_repository_transaction, docs_adr_0002_decouple_the_archive_from_the_transaction_archive_decoupling_decision, readme_task_file_lifecycle, src_bot_todo_skill_assets_todo_skill_archive_policy [INFERRED 0.95]

## Communities (36 total, 8 thin omitted)

### Community 0 - "Skill Installation"
Cohesion: 0.06
Nodes (32): Installable task-repository CLI for agent and human backlogs., Install the packaged todo skill into one Skill Target's Skill Root., Read the packaged todo skill as bytes for one Skill Target. Assets are located…, SkillAssets, ConflictTests, DryRunTests, ForcedReplacementTests, Any (+24 more)

### Community 1 - "Domain and Agent Docs"
Cohesion: 0.06
Nodes (58): Documentation Contract, Human-Comprehensible Architecture Preference, Post-Implementation Quality Gate, Repository Agent Instructions, Task Management Rules, Tooling Preflight, Actionable Task, Aggregate Query (+50 more)

### Community 2 - "Configuration Tests"
Cohesion: 0.07
Nodes (19): ConfigurationTestCase, EntryPathTests, PrecedenceTests, Path, Verify Configuration Schema Version 1 discovery, precedence, and validation., Cover the settled --config over BOT_TODO_CONFIG over default order., Write one configuration file per precedence level. Side Effects: Creates three…, Report which configuration a ``--repo`` lookup resolved against. The winning… (+11 more)

### Community 3 - "Task Presentation"
Cohesion: 0.05
Nodes (24): Render one repository's tasks in both output formats. Args: name: Configured…, Initialize a presenter bound to one repository's provenance. Args: name:…, Build one concise human task summary. Args: task: Task to summarize. Returns:…, Build one aggregate human summary carrying its provenance. Repository-local…, TaskPresenter, Represent one canonical Markdown task. Args: task_id: Stable repository task…, Report the task lifecycle state. Returns: One of ``open``, ``completed``, or…, Report the single classifying type tag. Returns: Type tag, or ``None`` when the… (+16 more)

### Community 4 - "Command Execution"
Cohesion: 0.10
Nodes (23): Namespace, CommandOutcome, CommandRunner, Carry one command result in both output formats. Args: data: Machine-readable…, Execute one parsed command against a selected Task Repository. Args: selected:…, Initialize a runner bound to one repository. Args: selected: Repository the…, Dispatch one command to its handler. Side Effects: Reads and may update the…, Create the canonical task file. Side Effects: Writes a new ``TODO.md``. Args:… (+15 more)

### Community 5 - "Architecture Research"
Cohesion: 0.13
Nodes (39): Inventory the existing CLI compatibility contract, Task Data Format 1, importlib.resources documentation, UV tools documentation, Verify UV tool packaging and bundled-resource contracts, Agent Skills specification, Verify agent skill installation contracts, Define the public bot-todo CLI contract (+31 more)

### Community 6 - "Skill Reconciliation"
Cohesion: 0.09
Nodes (20): _digest(), InstallationResult, Path, Initialize an installer over one requested installation. Args: target: Skill…, Classify and, unless this is a dry run, perform the installation. Side Effects:…, Resolve the Skill Root without creating it. Returns: Absolute Skill Root path,…, Decide the single Reconciliation Action this invocation performs. Side Effects:…, Digest every regular file in a tree without following links. Side Effects:… (+12 more)

### Community 7 - "Repository Selection"
Cohesion: 0.09
Nodes (18): Path, Name the single Task Repository one command operates on. Args: store: Store for…, Resolve the settled selector options into one Task Repository. Configuration is…, Initialize a selector over one command's selector options. Args: root: Exact…, Load the configured Repository Collection. Side Effects: Reads the…, Resolve the Task Repository for one command. Side Effects: Reads configuration…, Resolve one configured Repository Entry. A configured path may not exist yet,…, Resolve the explicitly requested configuration path. ``--config`` overrides… (+10 more)

### Community 8 - "Aggregate Query Tests"
Cohesion: 0.14
Nodes (11): AggregateQueryTests, AggregateTestCase, Any, Build an ordered two-repository collection for the --all selector., Remove both repositories and the configuration. Side Effects: Deletes the…, Run one command against a single repository by path. Side Effects: May update…, Add one simple chore to a repository and return its allocated ID. Side Effects:…, Run one aggregate query in human mode. Side Effects: Reads every configured… (+3 more)

### Community 9 - "Repository Parsing"
Cohesion: 0.11
Nodes (22): _archive_overflow(), _blockers(), _find_critical(), _find_next(), _is_actionable(), Read, validate, and safely update one Task Repository., Enforce task identity and lifecycle invariants. Args: document: Parsed document…, Return parsed blocker IDs for a task. Args: task: Task whose blockers should be… (+14 more)

### Community 10 - "CLI Parsing"
Cohesion: 0.12
Nodes (21): ArgumentParser, _build_parser(), _install_skill(), _json_requested(), main(), OutputWriter, _Parser, Manage canonical repository task files. (+13 more)

### Community 11 - "Aggregate Runner"
Cohesion: 0.12
Nodes (15): NoReturn, AggregateRow, AggregateRunner, Pair one task with the provenance and snapshot that resolve it. Aggregate…, Project the row into a JSON Schema 1 Task object. Returns: Task object carrying…, Build the row's human summary. Returns: Single-line summary naming its…, Run one read query across the whole configured Repository Collection. Every…, Dispatch one aggregate query to its handler. Side Effects: Reads every… (+7 more)

### Community 12 - "Configuration Loading"
Cohesion: 0.14
Nodes (20): _parse(), _parse_entries(), _parse_entry(), Path, Load and validate the Repository Collection configuration file., Read one configuration file into validated Repository Entries. Side Effects:…, Reject an unsupported schema version before any other validation. Args: path:…, Validate the repository table array into Repository Entries. Any invalid entry… (+12 more)

### Community 13 - "Repository Test Helpers"
Cohesion: 0.12
Nodes (12): Any, Run a failing command in JSON mode and parse its error document. Asserts that a…, Add a simple chore and return its allocated ID. Args: title: Task title.…, Exercise todo operations through their public command-line interface., Create an isolated repository root for each test. Side Effects: Creates a…, Remove the isolated repository root. Side Effects: Deletes the temporary…, Run the CLI against the isolated repository. Args: *arguments: Command and…, Run a successful command in JSON mode and parse its document. Args: *arguments:… (+4 more)

### Community 14 - "Markdown Document Parsing"
Cohesion: 0.14
Nodes (14): _parse_document(), _parse_task_lines(), Hold the exclusive lock across load, mutation, and commit. Side Effects:…, Parse and validate the active task file. Returns: Parsed, validated document.…, Render a collection with canonical blank-line separation. Args: tasks: Tasks to…, Parse active-file Markdown into one document. Args: todo_text: Active-file…, Parse task blocks from one section. Args: lines: Markdown lines within a task…, Require a path to be either absent or a regular file. Args: path: Path that… (+6 more)

### Community 15 - "Repository Store"
Cohesion: 0.15
Nodes (9): Require an existing repository directory before locking it. Raises: TodoError:…, Own the canonical files, coordination, and durability of one repository. Args:…, Find the nearest Task Repository at or above one directory. Args: start:…, Read one coherent view of the repository. Returns: Validated snapshot taken…, TodoStore, CompatibilityTests, LockingTests, Verify shared reads, exclusive mutations, and the conflict timeout. (+1 more)

### Community 16 - "Task Field Utilities"
Cohesion: 0.13
Nodes (16): _deduplicate(), _format_id(), _normalize_tags(), _optional_fields(), Separate a task title from its trailing tags. Args: value: Task-line content…, Format a numeric ID with a minimum width of three digits. Args: number:…, Validate and normalize tags without leading hashes. Args: tags: Raw tags.…, Return values once while retaining their first-seen order. Args: values: Values… (+8 more)

### Community 17 - "Configured CLI Tests"
Cohesion: 0.16
Nodes (6): invoke(), Run the CLI in this process and capture its streams. Args: *arguments:…, ConfiguredSelectionTests, Verify repository selection, discovery, and process contract., Cover the --repo selector against a temporary configuration., SelectionTests

### Community 18 - "Distribution Packaging"
Cohesion: 0.22
Nodes (10): Path, skipUnless, Verify that a built wheel installs and runs outside this checkout., Build a wheel and a source distribution from this checkout. Side Effects:…, List the packaged skill assets one distribution carries. Side Effects: Reads…, Build a wheel from this checkout. Side Effects: Writes distribution artifacts…, Install one wheel into a disposable virtual environment. Side Effects: Creates…, Run one command and return its standard output. Side Effects: Executes an… (+2 more)

### Community 19 - "Archive Persistence"
Cohesion: 0.13
Nodes (13): _current_branch(), _fsync_directory(), Path, Return the current Git branch or a portable fallback. Args: root: Repository…, Atomically replace one UTF-8 text file, preserving its permissions. Side…, Flush a directory entry so a rename survives a crash. Side Effects: Opens and…, Append-only history of tasks retired from the active task file. The archive is…, Initialize an archive at one path. Args: path: Path to the archive file. (+5 more)

### Community 21 - "JSON Serialization"
Cohesion: 0.16
Nodes (7): Any, Initialize a writer for one invocation's output format. Keyword Args:…, Build the repository provenance object. Returns: Nullable Repository Name and…, Project one task into a JSON Schema 1 Task object. Args: task: Task to project.…, Configure one parser with the settled argument-parsing policy. Args: *args:…, DurabilityTests, Verify that failed writes never publish a partial task file.

### Community 22 - "Repository Transactions"
Cohesion: 0.21
Nodes (9): Require an active task. Args: task: Task to inspect. Raises: TodoError: If the…, Apply one serialized mutation to a Task Repository. The caller obtains a…, Record an advisory claim on an active task. Args: task_id: Task to claim.…, Remove an advisory claim from an active task. Args: task_id: Task whose claim…, Complete or cancel an active task. Args: task_id: Task to close. outcome:…, Move Done entries beyond the retention limit toward the archive. Returns:…, Find a task held in the active file. Args: task_id: Task identifier to locate.…, RepositoryTransaction (+1 more)

### Community 23 - "Core CLI Tests"
Cohesion: 0.20
Nodes (6): CliResult, Shared harness for exercising bot-todo through its command-line interface., Captured outcome of one in-process CLI invocation., QueryTests, End-to-end tests for the bot-todo command-line interface., Cover the settled critical and actionable query semantics.

### Community 24 - "Aggregate Failure Tests"
Cohesion: 0.20
Nodes (5): AggregateFailureTests, Configure the isolated repository under a Repository Name. Side Effects: Writes…, Initialize the repositories alpha and beta and configure them in order. Side…, Rewrite the configuration over the named repositories, in order. Side Effects:…, Cover strict aggregate partial failure and its exit status.

### Community 27 - "Skill Guidance Tests"
Cohesion: 0.22
Nodes (5): Verify the packaged todo skill tells agents how to invoke the CLI., Cover agent invocation rules encoded in the packaged skill., Load the packaged skill text., Collect ``bot-todo`` example lines from fenced blocks. Returns: Stripped…, SkillGuidanceTests

### Community 29 - "File Safety Tests"
Cohesion: 0.29
Nodes (4): FileSafetyTests, skipUnless, Verify that unsafe canonical file types are rejected, never replaced., Assert that reading the repository reports an unsafe canonical file. Raises:…

### Community 30 - "Repository Locking"
Cohesion: 0.31
Nodes (6): AbstractContextManager, Serialize repository access with shared reads and exclusive mutations. Args:…, Hold a shared read lock for the duration of the context. Returns: Context…, Hold an exclusive mutation lock for the duration of the context. Returns:…, Acquire and release the lock file with the requested flags. Side Effects:…, RepositoryLock

### Community 33 - "Task Claims"
Cohesion: 0.50
Nodes (3): Claim, Hold the parsed ownership metadata of one claimed task. Args: actor: Agent or…, Report the parsed ownership claim. Returns: Parsed claim, or ``None`` when the…

## Knowledge Gaps
- **16 isolated node(s):** `bot-todo`, `UV tools documentation`, `importlib.resources documentation`, `Agent Skills specification`, `Four-Phase Delivery Plan` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TodoError` connect `Configuration Loading` to `Skill Installation`, `Configuration Tests`, `Task Presentation`, `Command Execution`, `Skill Reconciliation`, `Repository Selection`, `Repository Parsing`, `CLI Parsing`, `Aggregate Runner`, `Repository Test Helpers`, `Markdown Document Parsing`, `Repository Store`, `Task Field Utilities`, `Archive Persistence`, `JSON Serialization`, `Repository Transactions`, `File Safety Tests`, `Repository Locking`, `Archive Behavior Tests`?**
  _High betweenness centrality (0.269) - this node is a cross-community bridge._
- **Why does `invoke()` connect `Configured CLI Tests` to `Aggregate Selector Tests`, `Skill Installation`, `Configuration Tests`, `Aggregate Query Tests`, `CLI Parsing`, `Repository Test Helpers`, `JSON Output Tests`, `Core CLI Tests`, `Aggregate Failure Tests`, `CLI Grammar Tests`, `Initialization and Identity`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Why does `TodoCliTestCase` connect `Repository Test Helpers` to `Aggregate Selector Tests`, `Aggregate Query Tests`, `Repository Store`, `Configured CLI Tests`, `JSON Output Tests`, `JSON Serialization`, `Core CLI Tests`, `Aggregate Failure Tests`, `CLI Grammar Tests`, `Lifecycle Tests`, `Initialization and Identity`, `File Safety Tests`, `Archive Behavior Tests`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `TodoError` (e.g. with `AggregateRow` and `AggregateRunner`) actually correct?**
  _`TodoError` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `Task` (e.g. with `AggregateRow` and `AggregateRunner`) actually correct?**
  _`Task` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `TodoStore` (e.g. with `AggregateRow` and `AggregateRunner`) actually correct?**
  _`TodoStore` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `CommandOutcome` (e.g. with `RepositoryCollection` and `RepositorySnapshot`) actually correct?**
  _`CommandOutcome` has 6 INFERRED edges - model-reasoned connections that need verification._