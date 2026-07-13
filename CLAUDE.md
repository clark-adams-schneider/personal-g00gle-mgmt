# Agent Directives & Coding Guidelines

This project enforces strict standards for code quality, safety, and maintainability. When contributing to this repository, agents must adhere to the following rules:

### 1. No Placeholders or Stubbing
Write robust, production-ready code that scales. Do not leave "TODO" blocks or empty stub files for later. Design for the entire scope upfront.

### 2. Strict Typing & Pydantic Everywhere
Never pass around untyped dictionaries (`Dict[str, Any]`). 
Use Pydantic models to strongly type all inputs, configurations, and API specs. Use recursive models and `model_validator`s where appropriate.

### 3. Zero Magic Strings & API-Native Terminology
- Never use magic strings.
- Always use Python `Enum` classes to map constant values.
- Do not abstract away API-native terms with custom 1st-party terms. If the API expects `application/vnd.google-apps.folder`, use that exact MIME type in your Enum, rather than inventing an arbitrary string like `"folder"`.

### 4. Modern Pythonic Practices
- **Paths**: Always use `pathlib.Path` over raw strings and `os.path`.
- **Reflection**: Avoid hacky heuristics (like `if k.startswith("_"):`). Use built-in Python or Pydantic reflection (like `cls.model_fields`) to intelligently and dynamically parse data.
- **DRY**: Extract inline logic, especially string manipulation, into reusable, well-named helper functions.

### 5. Strict Linting & Cyclomatic Complexity
- **Ruff**: The project uses Ruff via GitHub Actions. All code must pass Black formatting, `isort`, and unused imports (`Pyflakes`) checks.
- **Complexity**: Cyclomatic Complexity (McCabe) is strictly capped at `10`. If a function exceeds this, refactor it into smaller helper methods immediately.

### 6. Context Awareness
Read the constraints. This architecture is built for *Personal Gmail* via standard OAuth2, explicitly avoiding Google Workspace enterprise features (like Domain-Wide Delegation). Keep this context in mind for all documentation, naming, and architectural decisions.

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
| ------ | ---------- |
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
