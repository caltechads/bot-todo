# Graph Report - bot_todo  (2026-08-27)

## Corpus Check
- 80 files · ~197,714 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1434 nodes · 2761 edges · 83 communities (69 shown, 14 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 250 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `60143bde`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- .install
- Bot Todo Domain Language
- .load_failure
- Task
- CommandOutcome
- Wayfinder Map: Make bot-todo an installable multi-repository tool
- Path
- .load
- AggregateQueryTests
- repository.py
- SkillInstaller
- AggregateRunner
- TodoError
- TodoCliTestCase
- .discover
- TodoStore
- RepositoryTransaction
- invoke
- WheelSmokeTests
- ReposCliTestCase
- JsonDocumentTests
- DurabilityTests
- AGENTS.md
- test_cli.py
- AggregateFailureTests
- .get
- LifecycleTests
- SkillGuidanceTests
- InitializationAndIdentityTests
- FileSafetyTests
- .snapshot
- ArchiveTests
- AggregateSelectorTests
- Claim
- tests/__init__.py
- bot-todo
- .post
- .request
- WebCommandTests
- BoardTask
- Repository Collection CLI
- KanbanRequestHandler
- CollectionKanbanWebTests
- Implementation order
- Implementation order
- KanbanWebApp
- .store
- KanbanWebTests
- CollectionStoreTestCase
- SkillAssets
- .collection
- ReviewStateTests
- ConfiguredSelectionTests
- ReconciliationActionTests
- Implementation order
- File Map
- BoardSelection
- ._render_add_form
- RemoveTests
- test_skill_installation.py
- ConflictTests
- .resolve_path
- .view
- Global Constraints
- Kanban Task Detail Modal
- Local Kanban Board Design
- Files
- T010 Tabler redesign QA
- 9. Kanban task detail lives in a board modal
- 10. Edit open and review tasks in the Kanban detail modal
- 11. Keep collection Kanban selection request-scoped and read-only
- Files
- SkillInstallationTestCase
- _build_parser
- 7. Serve the local Kanban Board with the Python standard library
- 8. Use pinned Tabler assets for the Kanban presentation
- .__init__
- test_task_management_snippet.py
- .create_server
- FormatVersionTests
- .setUp
- release.sh
- .__init__

## God Nodes (most connected - your core abstractions)
1. `TodoError` - 108 edges
2. `Task` - 69 edges
3. `TodoStore` - 65 edges
4. `invoke()` - 63 edges
5. `KanbanWebTests` - 61 edges
6. `RepositoryCollection` - 56 edges
7. `KanbanWebApp` - 48 edges
8. `CommandOutcome` - 44 edges
9. `RepositoryEntry` - 36 edges
10. `TodoCliTestCase` - 35 edges

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

## Communities (83 total, 14 thin omitted)

### Community 0 - ".install"
Cohesion: 0.22
Nodes (6): ForcedReplacementTests, Path, Replace conflicts only when explicitly authorized., Resolve Skill Roots per target and per override., Install one target successfully and return its ``data`` object. Args:…, SkillRootTests

### Community 1 - "Bot Todo Domain Language"
Cohesion: 0.06
Nodes (58): Documentation Contract, Human-Comprehensible Architecture Preference, Post-Implementation Quality Gate, Repository Agent Instructions, Task Management Rules, Tooling Preflight, Actionable Task, Aggregate Query (+50 more)

### Community 2 - ".load_failure"
Cohesion: 0.07
Nodes (19): ConfigurationTestCase, EntryPathTests, PrecedenceTests, Path, Verify Configuration Schema Version 1 discovery, precedence, and validation., Cover the settled --config over BOT_TODO_CONFIG over default order., Write one configuration file per precedence level. Side Effects: Creates three…, Report which configuration a ``--repo`` lookup resolved against. The winning… (+11 more)

### Community 3 - "Task"
Cohesion: 0.05
Nodes (23): Represent one canonical Markdown task. Args: task_id: Stable repository task…, Require a task that is not completed or cancelled. Args: task: Task to inspect.…, Report the task lifecycle state. Returns: One of ``open``, ``review``,…, Report the single classifying type tag. Returns: Type tag, or ``None`` when the…, Report ordinary tags without the type or ``simple`` markers. Returns: Ordered…, Report whether the task deliberately omits acceptance criteria. Returns:…, Report the acceptance criteria. Returns: Acceptance text, or ``None`` for a…, Report the supporting context reference. Returns: Context text, or ``None``… (+15 more)

### Community 4 - "CommandOutcome"
Cohesion: 0.06
Nodes (36): Namespace, CollectionRunner, CommandOutcome, CommandRunner, Build a repos result that always names the configuration path. Args: operation:…, Project one Repository Entry into JSON. Args: entry: Repository Entry to…, Report the active configuration path. Args: _arguments: Parsed CLI arguments,…, List configured Repository Entries. Side Effects: Reads the configuration file.… (+28 more)

### Community 5 - "Wayfinder Map: Make bot-todo an installable multi-repository tool"
Cohesion: 0.13
Nodes (39): Inventory the existing CLI compatibility contract, Task Data Format 1, importlib.resources documentation, UV tools documentation, Verify UV tool packaging and bundled-resource contracts, Agent Skills specification, Verify agent skill installation contracts, Define the public bot-todo CLI contract (+31 more)

### Community 6 - "Path"
Cohesion: 0.13
Nodes (14): _digest(), Path, Initialize an installer over one requested installation. Args: target: Skill…, Decide the single Reconciliation Action this invocation performs. Side Effects:…, Digest every regular file in a tree without following links. Side Effects:…, Compare a scanned tree against its manifest and the packaged view. Side…, Read the managed asset digests one manifest records. Side Effects: Reads the…, Render the ownership manifest for one asset view. Args: view: Packaged asset… (+6 more)

### Community 7 - ".load"
Cohesion: 0.24
Nodes (3): Load and fully validate a Repository Collection. An explicit path must exist,…, DiscoveryTests, Cover configuration location, precedence, and absence.

### Community 8 - "AggregateQueryTests"
Cohesion: 0.15
Nodes (10): AggregateQueryTests, AggregateTestCase, Any, Build an ordered two-repository collection for the --all selector., Run one command against a single repository by path. Side Effects: May update…, Add one simple chore to a repository and return its allocated ID. Side Effects:…, Run one aggregate query in human mode. Side Effects: Reads every configured…, Run one successful aggregate query and parse its data object. Side Effects:… (+2 more)

### Community 9 - "repository.py"
Cohesion: 0.05
Nodes (52): _archive_overflow(), _blockers(), _current_branch(), _find_critical(), _find_next(), _fsync_directory(), _is_actionable(), _normalize_tags() (+44 more)

### Community 10 - "SkillInstaller"
Cohesion: 0.08
Nodes (22): _install_skill(), _json_requested(), main(), OutputWriter, Dispatch one aggregate query to its handler. Side Effects: Reads every…, Render results and failures in the selected output format. Args: json_mode:…, Write one successful result to stdout. Side Effects: Writes to stdout. Args:…, Write one expected failure to stderr, leaving stdout empty. Side Effects:… (+14 more)

### Community 11 - "AggregateRunner"
Cohesion: 0.07
Nodes (25): AggregateRow, AggregateRunner, Any, Run one read query across the whole configured Repository Collection. Every…, Initialize a runner bound to one Repository Collection. Args: collection:…, List every open task across the collection. Args: rows: Every open task in…, Group open tasks under Repository Name headers. Args: rows: Every open task in…, Select the highest-priority open task in the collection. Blocked and claimed… (+17 more)

### Community 12 - "TodoError"
Cohesion: 0.06
Nodes (65): _Parser, Manage canonical repository task files., Name the single Task Repository one command operates on. Args: store: Store for…, Resolve the settled selector options into one Task Repository. ``web`` loads…, Reject long-option abbreviation and ANSI styling on every parser. Args: *args:…, RepositorySelector, SelectedRepository, _allowed_add_path() (+57 more)

### Community 13 - "TodoCliTestCase"
Cohesion: 0.11
Nodes (15): Any, Shared harness for exercising bot-todo through its command-line interface., Run a failing command in JSON mode and parse its error document. Asserts that a…, Add a task through the CLI and return its allocated ID. Args: *arguments:…, Add a simple chore and return its allocated ID. Args: title: Task title.…, Read the Task ID from a human mutation confirmation. Args: stdout: Human…, Exercise todo operations through their public command-line interface., Create an isolated repository root for each test. Side Effects: Creates a… (+7 more)

### Community 15 - "TodoStore"
Cohesion: 0.24
Nodes (6): Own the canonical files, coordination, and durability of one repository. Args:…, TodoStore, CompatibilityTests, LockingTests, Verify shared reads, exclusive mutations, and the conflict timeout., Verify that task data written before this release still loads.

### Community 16 - "RepositoryTransaction"
Cohesion: 0.09
Nodes (26): _deduplicate(), _format_id(), _optional_fields(), Format a numeric ID with a minimum width of three digits. Args: number:…, Return values once while retaining their first-seen order. Args: values: Values…, Return stripped non-empty single-line text. Args: value: Candidate text. name:…, Return an unambiguous title without hashtag-like tokens. Args: value: Candidate…, Collect populated values as canonical fields. Args: candidates: Canonical field… (+18 more)

### Community 17 - "invoke"
Cohesion: 0.09
Nodes (8): invoke(), Run the CLI in this process and capture its streams. Args: *arguments:…, GrammarTests, Cover the settled option grammar and usage failures., Verify repository selection, discovery, and process contract., SelectionTests, Emit the snippet without a Task Repository., SnippetCommandTests

### Community 18 - "WheelSmokeTests"
Cohesion: 0.22
Nodes (10): Path, skipUnless, Verify that a built wheel installs and runs outside this checkout., List the packaged skill assets one distribution carries. Side Effects: Reads…, Build a wheel from this checkout. Side Effects: Writes distribution artifacts…, Install one wheel into a disposable virtual environment. Side Effects: Creates…, Run one command and return its standard output. Side Effects: Executes an…, Build, install, and exercise the distribution in a disposable venv. (+2 more)

### Community 19 - "ReposCliTestCase"
Cohesion: 0.09
Nodes (18): Verify the nested repos command group through the public CLI., Cover repos path against missing and present configuration files., Cover repos list for empty and populated collections., Cover repos add JSON, human output, and default path., Exercise repos commands against an isolated default configuration., Create an isolated XDG configuration root. Side Effects: Creates a temporary…, Cover repos remove by name and by path., Cover selector combinations the repos group accepts and rejects. (+10 more)

### Community 22 - "AGENTS.md"
Cohesion: 0.06
Nodes (28): Agent skills, AGENTS.md, Documentation Contract (Required), Domain docs, Human-Comprehensible Architecture Preference (Required), Issue tracker, Local Overrides, Post-Implementation Quality Gate (Required) (+20 more)

### Community 23 - "test_cli.py"
Cohesion: 0.12
Nodes (9): CliResult, Captured outcome of one in-process CLI invocation., HumanMutationConfirmationTests, MigrationTests, QueryTests, End-to-end tests for the bot-todo command-line interface., Cover the settled critical and actionable query semantics., Verify human mutation stdout names the operation, ID, and title. (+1 more)

### Community 24 - "AggregateFailureTests"
Cohesion: 0.32
Nodes (3): AggregateFailureTests, Rewrite the configuration over the named repositories, in order. Side Effects:…, Cover strict aggregate partial failure and its exit status.

### Community 25 - ".get"
Cohesion: 0.07
Nodes (15): Catch an edit form appearing on a completed or cancelled task., Catch Review tasks left on the read-only definition list., Catch a standalone GET edit page., Request one board page. Args: path: Absolute request path. Returns: Status,…, Catch malformed repo queries becoming 500s or leaking selector details., Catch missing columns, wrong state grouping, and unescaped titles., Catch a board that omits persisted task fields or restores a detail page., Catch a leftover GET /tasks/<id> page for a task that is on the board. (+7 more)

### Community 27 - "SkillGuidanceTests"
Cohesion: 0.16
Nodes (5): Verify the packaged todo skill tells agents how to invoke the CLI., Cover agent invocation rules encoded in the packaged skill., Load the packaged skill text., Collect ``bot-todo`` example lines from fenced blocks. Returns: Stripped…, SkillGuidanceTests

### Community 29 - "FileSafetyTests"
Cohesion: 0.29
Nodes (4): FileSafetyTests, skipUnless, Verify that unsafe canonical file types are rejected, never replaced., Assert that reading the repository reports an unsafe canonical file. Raises:…

### Community 30 - ".snapshot"
Cohesion: 0.29
Nodes (4): AbstractContextManager, Read one coherent view of the repository. Returns: Validated snapshot taken…, Require an existing repository directory before locking it. Raises: TodoError:…, Hold a shared read lock for the duration of the context. Returns: Context…

### Community 33 - "Claim"
Cohesion: 0.50
Nodes (3): Claim, Hold the parsed ownership metadata of one claimed task. Args: actor: Agent or…, Report the parsed ownership claim. Returns: Parsed claim, or ``None`` when the…

### Community 36 - ".post"
Cohesion: 0.07
Nodes (15): Catch an edit POST that drops fields or skips RepositoryTransaction.edit., Catch a no-change Save treated as a CLI-style usage error., Catch an edit POST that mutates a completed or cancelled task., Catch both Acceptance and Simple submitted on an edit., Catch an edit that would drop both Acceptance and #simple., Catch type or simple leaking into the Tags field., Catch POST /tasks/<id>/edit treating a missing id as a generic 404., Submit one trusted board form. Args: path: Absolute request path. fields: URL-… (+7 more)

### Community 37 - ".request"
Cohesion: 0.07
Nodes (15): Submit one trusted board form. Args: path: Absolute request path. fields: URL-…, Send one raw request to the loopback server. Args: method: HTTP request method.…, Catch /?repo= rendering the launch repository instead of the named one., Catch detail and error responses falling outside the Tabler shell., Catch DNS-rebinding exposure through an unchecked Host header., Catch cross-site form submission without the board secret., Request one board page. Args: path: Absolute request path. Returns: Status,…, Catch a trusted token submitted from an untrusted browser origin. (+7 more)

### Community 38 - "WebCommandTests"
Cohesion: 0.10
Nodes (14): patch, Remove both repositories and the configuration. Side Effects: Deletes the…, Verify the human-only web command contract., Restore configuration environment and remove the isolated root., Catch web accidentally entering the machine-output flow., Catch All being rejected or dispatched without its collection., Catch --all web still requiring an explicit configuration file., Catch --repo web dropping the collection or resolving the wrong path. (+6 more)

### Community 39 - "BoardTask"
Cohesion: 0.13
Nodes (13): BoardTask, Build a collision-proof modal id for one board row. Args: row: Board row…, Project every configured repository onto the four board columns. Side Effects:…, Render all recent tasks in Task State columns. Side Effects: Reads the selected…, Render one task card. Args: row: Board row displayed by the card. Keyword Args:…, Render one responsive board column with bounded terminal cards. Args: heading:…, Pair a board-visible Task with optional Repository Name provenance. Args: task:…, Render one Tabler modal for a board-visible task. Args: row: Board row whose… (+5 more)

### Community 40 - "Repository Collection CLI"
Cohesion: 0.09
Nodes (20): 3. Nest Repository Collection commands, 1. Spec artifacts (this directory) and ADR, 2. `CollectionStore` (TDD), 3. CLI (`CollectionRunner`), 4. Docs and skill, 5. Quality gate, Architecture, Context (+12 more)

### Community 41 - "KanbanRequestHandler"
Cohesion: 0.14
Nodes (13): BaseHTTPRequestHandler, NoReturn, Route a parse failure into the shared error path. Args: message: Diagnostic…, KanbanRequestHandler, Adapt loopback HTTP requests to a :class:`KanbanWebApp`. Args: *args: Arguments…, Serve one board page. Side Effects: Reads a repository and writes an HTTP…, Apply one board mutation. Side Effects: Reads a form, mutates a repository, and…, Apply browser hardening and finish the response headers. Side Effects: Writes… (+5 more)

### Community 42 - "CollectionKanbanWebTests"
Cohesion: 0.10
Nodes (11): CollectionKanbanWebTests, Exercise a collection-wide Kanban Board through loopback HTTP., Stop the Kanban server and remove its repositories., Catch All mixing write controls, migrate copy, or unordered cards., Catch punctuation normalization collapsing All modal ids., Catch All rendering healthy cards after a strict collection failure., Catch All requiring Current or hiding empty state columns., Catch add/edit/transition writing the launch repository or losing ?repo=. (+3 more)

### Community 43 - "Implementation order"
Cohesion: 0.11
Nodes (16): 6. Review is an in-section lifecycle state, Consequences, Considered Options, Context, Decision, 1. Persist this plan (done in the T011 recording session), 2. Format 2 read/write + migrate (TDD), 3. Review field, state, and selectors (TDD) (+8 more)

### Community 44 - "Implementation order"
Cohesion: 0.11
Nodes (16): 4. Group human `--all list` by Repository Name, Consequences, Context, Decision, 1. Persist this plan and ADR (this directory), 2. Failing tests (TDD), 3. Glossary, 4. `TaskPresenter.list_line` (+8 more)

### Community 45 - "KanbanWebApp"
Cohesion: 0.16
Nodes (10): KanbanWebApp, Return the dropdown label for one selection. Args: selection: Selection whose…, Render the Tabler repository dropdown. Args: selection: Currently displayed…, Wrap content in the shared HTML document. Args: title: Browser page title.…, Derive the immutable launch selection from constructor facts. Args: store:…, Build the canonical path for one board selection. Args: selection: Selection to…, Render the generic missing-page response. Args: selection: Selection used for…, Render one concise error page. Args: title: Human-readable error title.… (+2 more)

### Community 46 - ".store"
Cohesion: 0.22
Nodes (5): AddTests, Path, Cover add path grammar, name inference, and canonical writes., Build a store over the isolated explicit configuration path. Args: explicit:…, Create one repository directory under the isolated root. Args: name: Directory…

### Community 47 - "KanbanWebTests"
Cohesion: 0.11
Nodes (10): KanbanWebTests, Catch EADDRINUSE handling that swallows unrelated bind failures., Catch a local configured path rendered as duplicate Current., Catch loss of an existing local/root web launch., Exercise the Kanban Board through a real loopback HTTP server., Catch a board that renders state but offers no human controls., Catch a restored detail lookup for an unknown task ID., Catch state icons that disappear once a column has cards. (+2 more)

### Community 48 - "CollectionStoreTestCase"
Cohesion: 0.14
Nodes (7): CollectionStoreTestCase, MissingFileTests, Verify CollectionStore mutations of the Repository Collection file., Exercise CollectionStore against an isolated configuration root., Create an isolated directory for configuration and repositories. Side Effects:…, Remove the isolated directory. Side Effects: Deletes the temporary directory…, Cover the missing-default versus missing-explicit contract.

### Community 49 - "SkillAssets"
Cohesion: 0.18
Nodes (10): package_version(), Installable task-repository CLI for agent and human backlogs., Return the installed distribution version. Returns: Installed version, or…, InstallationResult, Install the packaged todo skill into one Skill Target's Skill Root., Classify and, unless this is a dry run, perform the installation. Side Effects:…, Report what one ``install-skill`` invocation classified and performed. Args:…, Read the packaged todo skill as bytes for one Skill Target. Assets are located… (+2 more)

### Community 50 - ".collection"
Cohesion: 0.15
Nodes (7): Path, Initialize a selector over one command's selector options. Args: root: Exact…, Load the configured Repository Collection. Side Effects: Reads the…, Resolve the Task Repository for one command. Side Effects: Reads configuration…, Resolve one configured Repository Entry. A configured path may not exist yet,…, Resolve the explicitly requested configuration path. ``--config`` overrides…, Initialize a presenter bound to one repository's provenance. Args: name:…

### Community 52 - "ConfiguredSelectionTests"
Cohesion: 0.18
Nodes (5): ConfiguredSelectionTests, Cover the --repo selector against a temporary configuration., Configure the isolated repository under a Repository Name. Side Effects: Writes…, Initialize the repositories alpha and beta and configure them in order. Side…, Create an isolated repository and an empty default configuration.

### Community 53 - "ReconciliationActionTests"
Cohesion: 0.22
Nodes (5): Any, Read the installed ownership manifest. Returns: The parsed manifest document., Overwrite the installed ownership manifest. Side Effects: Rewrites the manifest…, Classify exactly one action per invocation., ReconciliationActionTests

### Community 54 - "Implementation order"
Cohesion: 0.20
Nodes (9): 1. Persist this plan and link T008, 2. Failing tests (TDD), 3. Implementation, 4. Docs, 5. Quality gate, Architecture, Default init --name to the directory basename, Implementation order (+1 more)

### Community 55 - "File Map"
Cohesion: 0.20
Nodes (9): File Map, Global Constraints, Repository-switching Kanban Board Implementation Plan, Self-review, Task 1: Make CLI web dispatch collection-aware, Task 2: Resolve request-local selections and render the menu, Task 3: Render a strict, read-only All board, Task 4: Preserve selection across repository mutations (+1 more)

### Community 56 - "BoardSelection"
Cohesion: 0.27
Nodes (6): BoardSelection, Return the repository selected for a mutation. Args: selection: Request-local…, Add one task from browser form fields. Side Effects: Mutates the selected Task…, Identify one request's Kanban Board selection. Args: key: Query value…, Replace editable fields on one open or review task. Side Effects: Mutates the…, Apply one supported lifecycle action. Side Effects: Mutates the selected Task…

### Community 57 - "._render_add_form"
Cohesion: 0.20
Nodes (5): Render the hidden CSRF token field. Returns: Escaped hidden input markup., Render priority ``<option>`` elements. Args: selected: Priority key marked…, Render type ``<option>`` elements. Args: selected: Type tag marked…, Render the task creation form. Args: selection: Request-local board selection…, Render legal lifecycle controls for one task. Args: task: Task whose current…

### Community 58 - "RemoveTests"
Cohesion: 0.31
Nodes (3): Cover remove-by-name, remove-by-path, and name-wins collisions., Add named repositories and return the store. Side Effects: Writes the…, RemoveTests

### Community 59 - "test_skill_installation.py"
Cohesion: 0.20
Nodes (5): DryRunTests, Exercise bundled skill installation through the public command line., Classify without mutating the filesystem., Reject selector and target misuse before touching the filesystem., UsageTests

### Community 60 - "ConflictTests"
Cohesion: 0.27
Nodes (4): ConflictTests, Refuse to touch anything this installer does not own., Put the Skill Root into one conflicting state. Side Effects: Creates or…, Run a failing installation and return its exit status and error. Args:…

### Community 61 - ".resolve_path"
Cohesion: 0.25
Nodes (4): Report the platform default configuration path. Returns: Default configuration…, Resolve the active configuration path without requiring the file. Args:…, Cover active configuration path resolution., ResolvePathTests

### Community 62 - ".view"
Cohesion: 0.25
Nodes (4): Read the packaged asset view for one target. Args: target: Skill Target…, Capture every regular file under a tree. Args: tree: Directory to capture.…, Install exactly the assets each Skill Target receives., TargetViewTests

### Community 63 - "Global Constraints"
Cohesion: 0.25
Nodes (7): Global Constraints, Local Kanban Board Implementation Plan, Task 1: Web behavior, Task 2: CLI integration, Task 3: Documentation and release verification, Task 4: Tabler presentation revision, Task 5: Redesign documentation and visual verification

### Community 64 - "Kanban Task Detail Modal"
Cohesion: 0.25
Nodes (7): Docs and task metadata, Execution notes, Files, Kanban Task Detail Modal, Markup contract, Quality gate, Tests (TDD)

### Community 65 - "Local Kanban Board Design"
Cohesion: 0.29
Nodes (6): Command, Exclusions, Goal, HTTP interface, Local Kanban Board Design, Presentation and safety

### Community 66 - "Files"
Cohesion: 0.29
Nodes (6): Execution notes, Files, Kanban Task Detail Modal Edits, Task 1: Failing web tests, Task 2: Minimal implementation, Task 3: Spec, README, and quality gate

### Community 67 - "T010 Tabler redesign QA"
Cohesion: 0.33
Nodes (5): Comparison history, Evidence, Findings, Implementation checklist, T010 Tabler redesign QA

### Community 68 - "9. Kanban task detail lives in a board modal"
Cohesion: 0.33
Nodes (5): 9. Kanban task detail lives in a board modal, Consequences, Considered Options, Context, Decision

### Community 69 - "10. Edit open and review tasks in the Kanban detail modal"
Cohesion: 0.33
Nodes (5): 10. Edit open and review tasks in the Kanban detail modal, Consequences, Considered Options, Context, Decision

### Community 70 - "11. Keep collection Kanban selection request-scoped and read-only"
Cohesion: 0.33
Nodes (5): 11. Keep collection Kanban selection request-scoped and read-only, Consequences, Considered Options, Context, Decision

### Community 71 - "Files"
Cohesion: 0.33
Nodes (5): Files, Occupied Kanban Port Failure, Task 1: Failing tests, Task 2: Map EADDRINUSE in `create_server`, Task 3: Docs, link, quality gate

### Community 72 - "SkillInstallationTestCase"
Cohesion: 0.33
Nodes (4): Install the packaged skill into disposable roots only., Create an isolated Skill Root for each test. Side Effects: Creates a temporary…, Remove the isolated Skill Root. Side Effects: Deletes the temporary directory…, SkillInstallationTestCase

### Community 73 - "_build_parser"
Cohesion: 0.40
Nodes (5): ArgumentParser, _build_parser(), _port(), Parse one TCP port argument. Args: value: Decimal port text. Returns: Port…, Build the public command-line parser. Returns: Configured argument parser.

### Community 74 - "7. Serve the local Kanban Board with the Python standard library"
Cohesion: 0.40
Nodes (4): 7. Serve the local Kanban Board with the Python standard library, Consequences, Context, Decision

### Community 75 - "8. Use pinned Tabler assets for the Kanban presentation"
Cohesion: 0.40
Nodes (4): 8. Use pinned Tabler assets for the Kanban presentation, Consequences, Context, Decision

### Community 76 - ".__init__"
Cohesion: 0.40
Nodes (3): Any, Initialize one request handler. Args: *args: Arguments supplied by…, Suppress standard-library access logging. Args: _format: Standard-library log…

### Community 77 - "test_task_management_snippet.py"
Cohesion: 0.40
Nodes (3): Cover the packaged Task Management Snippet., Load the packaged markdown used by init and snippet., TaskManagementSnippetTests

### Community 78 - ".create_server"
Cohesion: 0.50
Nodes (3): Bind an HTTP server to loopback. Args: port: Requested TCP port; zero asks the…, ThreadingHTTPServer, ValueError

## Knowledge Gaps
- **141 isolated node(s):** `release.sh script`, `bot-todo`, `Settled contract`, `Architecture`, `1. Persist spec, ADR, glossary, and this plan` (+136 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TodoError` connect `TodoError` to `.load_failure`, `Task`, `CommandOutcome`, `Path`, `.load`, `repository.py`, `SkillInstaller`, `AggregateRunner`, `.discover`, `TodoStore`, `RepositoryTransaction`, `DurabilityTests`, `FileSafetyTests`, `.snapshot`, `ArchiveTests`, `BoardTask`, `KanbanRequestHandler`, `CollectionKanbanWebTests`, `KanbanWebApp`, `.store`, `KanbanWebTests`, `CollectionStoreTestCase`, `SkillAssets`, `BoardSelection`, `RemoveTests`, `.resolve_path`, `.create_server`, `FormatVersionTests`?**
  _High betweenness centrality (0.179) - this node is a cross-community bridge._
- **Why does `KanbanWebTests` connect `KanbanWebTests` to `.post`, `.request`, `CollectionKanbanWebTests`, `TodoError`, `KanbanWebApp`, `TodoCliTestCase`, `TodoStore`, `.setUp`, `.get`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `TodoCliTestCase` connect `TodoCliTestCase` to `AggregateSelectorTests`, `WebCommandTests`, `AggregateQueryTests`, `CollectionKanbanWebTests`, `TodoStore`, `FormatVersionTests`, `invoke`, `KanbanWebTests`, `ReviewStateTests`, `ConfiguredSelectionTests`, `JsonDocumentTests`, `DurabilityTests`, `test_cli.py`, `AggregateFailureTests`, `LifecycleTests`, `InitializationAndIdentityTests`, `FileSafetyTests`, `ArchiveTests`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Are the 39 inferred relationships involving `TodoError` (e.g. with `AggregateRow` and `AggregateRunner`) actually correct?**
  _`TodoError` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `Task` (e.g. with `AggregateRow` and `AggregateRunner`) actually correct?**
  _`Task` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `TodoStore` (e.g. with `AggregateRow` and `AggregateRunner`) actually correct?**
  _`TodoStore` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `KanbanWebTests` (e.g. with `RepositoryCollection` and `RepositoryEntry`) actually correct?**
  _`KanbanWebTests` has 6 INFERRED edges - model-reasoned connections that need verification._