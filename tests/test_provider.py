from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personal_g00gle_mgmt.drive.models import FolderInputs
from personal_g00gle_mgmt.drive.provider import (
    FolderProvider,
    ProtectedResourceDeletionError,
)


def _folder_inputs(**overrides) -> FolderInputs:
    defaults = {
        "name": "report",
        "resource_key": "tree-report",
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


def test_delete_raises_when_protected():
    model = _folder_inputs(protect=True)
    provider = FolderProvider()

    with pytest.raises(ProtectedResourceDeletionError):
        provider.delete("some-id", model)


def test_find_existing_tries_resource_key_before_name_parent():
    service = MagicMock()
    service.files.return_value.list.return_value.execute.side_effect = [
        {"files": []},
        {"files": [{"id": "existing-id"}]},
    ]
    model = _folder_inputs(parent="folder_a")
    provider = FolderProvider()

    result = provider._find_existing(service, model)

    assert result == "existing-id"
    calls = service.files.return_value.list.call_args_list
    assert len(calls) == 2
    assert "appProperties has" in calls[0].kwargs["q"]
    assert "mimeType =" in calls[1].kwargs["q"]


def test_find_existing_short_circuits_on_resource_key_match():
    service = MagicMock()
    service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "keyed-id"}]
    }
    model = _folder_inputs()
    provider = FolderProvider()

    result = provider._find_existing(service, model)

    assert result == "keyed-id"
    assert service.files.return_value.list.call_count == 1


def test_reconcile_permissions_only_applies_delta():
    service = MagicMock()
    service.permissions.return_value.list.return_value.execute.return_value = {
        "permissions": [
            {
                "id": "perm-keep",
                "emailAddress": "keep@example.com",
                "role": "reader",
                "type": "user",
            },
            {
                "id": "perm-remove",
                "emailAddress": "remove@example.com",
                "role": "reader",
                "type": "user",
            },
        ]
    }
    model = _folder_inputs(
        permissions=[
            {"emailAddress": "keep@example.com", "role": "reader", "type": "user"},
            {"emailAddress": "add@example.com", "role": "writer", "type": "user"},
        ]
    )
    provider = FolderProvider()

    provider._reconcile_permissions(service, "folder-id", model)

    service.permissions.return_value.delete.assert_called_once_with(
        fileId="folder-id", permissionId="perm-remove"
    )
    service.permissions.return_value.create.assert_called_once_with(
        fileId="folder-id",
        body={"emailAddress": "add@example.com", "role": "writer", "type": "user"},
    )
