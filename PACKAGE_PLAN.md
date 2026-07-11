# Package Plan: Prod-Ready Pulumi GDrive OAuth

This repository (`personal-g00gle-mgmt`) serves as the source for a production-ready, consumable Python package. Downstream consumers will install this package to declaratively manage their Google Drive state (e.g., the `_robots` directory) using OAuth2 user credentials.

## 1. End-User Consumption Pattern

A downstream consumer will create their own Pulumi project and consume this package as follows:

**1. Installation:**
The consumer installs the package via their package manager (e.g., `uv add git+https://github.com/.../personal-g00gle-mgmt` or `pip install ...`).

**2. State Declaration:**
The consumer defines their desired Google Drive state in a JSON or YAML file (e.g., `robots_state.json`), representing the `_robots` directory.

**3. Pulumi Orchestration:**
The consumer writes a minimal `__main__.py` to invoke the package's component:

```python
# __main__.py (Downstream Consumer's Pulumi Program)
import json
import pulumi
from personal_g00gle_mgmt import FolderTree

# Load the target state declaration
with open("robots_state.json") as f:
    state = json.load(f)

# Instantiate the component which recursively builds the Drive tree
FolderTree(
    "robots-tree",
    spec=state,
    client_secrets_path="./client_secrets.json",
    token_path="./token.json"
)
```

## 2. Package Architecture (Src-Layout)

This repository will use a standard Python `src/` layout to ensure separation of concerns, testability, and adherence to packaging conventions.

**Directory Structure:**
```text
personal-g00gle-mgmt/
├── pyproject.toml              # Modern package metadata (e.g., hatchling or setuptools)
├── README.md                   # Consumption documentation for the end user
└── src/
    └── personal_g00gle_mgmt/
        ├── __init__.py         # Exports FolderTree and Folder for clean importing
        ├── auth.py             # OAuth2 token caching, refresh, and GCP client initialization
        ├── utils.py            # Hashing, relative path resolution, MIME type inference
        ├── provider.py         # The core Pulumi Dynamic ResourceProvider (CRUD + drift logic)
        ├── resource.py         # The Pulumi Dynamic Resource (Folder)
        └── component.py        # FolderTree ComponentResource (recursive dictionary parser)
```

## 3. Key Refactorings for Prod-Readiness

1. **Modularization**: Break down the 460-line monolithic PoC script into the focused modules listed above.
2. **Dependency Management**: Use a standard `pyproject.toml` specifying accurate requirements (`pulumi`, `google-auth-oauthlib`, `google-api-python-client`, etc.) so consumers inherit the right dependencies.
3. **Error Handling & Logging**: Replace `print()` statements with standard Python `logging` or `pulumi.log` so output and errors surface correctly in the consumer's Pulumi CLI.
4. **Path Resolution**: Ensure paths for source files (e.g., `_source: "./local_foo.xlsx"`) are robustly resolved relative to the consumer's Pulumi project root, rather than the package's execution path.
5. **Typing & Linting**: Add comprehensive type hints (`typing.TypedDict` for the schema) and docstrings to ensure the package passes `mypy` and provides robust IDE autocomplete for downstream users.
