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
