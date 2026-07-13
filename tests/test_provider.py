from pathlib import Path

from personal_g00gle_mgmt.drive.models import FolderInputs
from personal_g00gle_mgmt.drive.provider import FolderProvider


def _folder_inputs(**overrides) -> FolderInputs:
    defaults = {
        "name": "report",
        "client_secrets_path": Path("secrets.json"),
        "token_path": Path("token.json"),
    }
    defaults.update(overrides)
    return FolderInputs(**defaults)


def test_resolve_target_parents_primary_only():
    model = _folder_inputs(parent="folder_a")
    assert FolderProvider._resolve_target_parents(model) == {"folder_a"}


def test_resolve_target_parents_extra_only():
    model = _folder_inputs(extra_parent_ids=["folder_b", "folder_c"])
    assert FolderProvider._resolve_target_parents(model) == {"folder_b", "folder_c"}


def test_resolve_target_parents_primary_and_extra():
    model = _folder_inputs(parent="folder_a", extra_parent_ids=["folder_b"])
    assert FolderProvider._resolve_target_parents(model) == {"folder_a", "folder_b"}


def test_resolve_target_parents_none():
    model = _folder_inputs()
    assert FolderProvider._resolve_target_parents(model) == set()


def test_resolve_target_parents_dedupes_primary_in_extra():
    model = _folder_inputs(parent="folder_a", extra_parent_ids=["folder_a", "folder_b"])
    assert FolderProvider._resolve_target_parents(model) == {"folder_a", "folder_b"}
