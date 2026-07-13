from pathlib import Path

from personal_g00gle_mgmt.drive.models import (
    DependencyCycle,
    DriveFileParentsPatch,
    DrivePulumiAppPropertyKey,
    FolderInputs,
    GoogleDriveAppPropertyQuery,
    GoogleDriveFolderColor,
    GoogleDriveMimeType,
    GoogleDriveSearchQuery,
    ManagedResourceMarker,
    OfficeDocumentMimeType,
    PermissionModel,
    TreeNode,
    TreePath,
)


def test_treenode_extract_children():
    data = {
        "_mimeType": "application/vnd.google-apps.folder",
        "_description": "A test folder",
        "_color": "#ac725e",
        "child_folder_1": {"_mimeType": "application/vnd.google-apps.spreadsheet"},
        "child_document": {
            "_description": "A nested doc",
            "_mimeType": "application/vnd.google-apps.document",
        },
        "native_excel": {
            "_mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        },
    }

    node = TreeNode.model_validate(data)

    assert node.mime_type == GoogleDriveMimeType.FOLDER
    assert node.description == "A test folder"
    assert node.color == GoogleDriveFolderColor.CHOCOLATE
    assert len(node.children) == 3

    assert "child_folder_1" in node.children
    assert node.children["child_folder_1"].mime_type == GoogleDriveMimeType.SPREADSHEET

    assert "child_document" in node.children
    assert node.children["child_document"].description == "A nested doc"

    assert "native_excel" in node.children
    assert node.children["native_excel"].mime_type == OfficeDocumentMimeType.XLSX


def test_treenode_parents_alias_extracted_not_treated_as_child():
    data = {
        "_mimeType": "application/vnd.google-apps.folder",
        "_parents": ["other/folder/path", "another/path"],
        "child_folder_1": {"_mimeType": "application/vnd.google-apps.spreadsheet"},
    }

    node = TreeNode.model_validate(data)

    assert node.extra_parents == ["other/folder/path", "another/path"]
    assert list(node.children.keys()) == ["child_folder_1"]


def test_treenode_no_parents_defaults_empty():
    node = TreeNode.model_validate({})
    assert node.extra_parents == []


def test_treenode_protect_defaults_false():
    node = TreeNode.model_validate({})
    assert node.protect is False


def test_treenode_protect_alias_parses_true():
    node = TreeNode.model_validate({"_protect": True})
    assert node.protect is True


def test_permission_model_is_hashable_and_comparable():
    a = PermissionModel(emailAddress="a@example.com", role="reader", type="user")
    b = PermissionModel(emailAddress="a@example.com", role="reader", type="user")
    assert a == b
    assert hash(a) == hash(b)


def test_managed_resource_marker_app_properties_roundtrip():
    marker = ManagedResourceMarker(resource_key="tree-report")

    app_properties = marker.app_properties
    assert app_properties == {"pulumi.resourceKey": "tree-report"}
    assert ManagedResourceMarker.from_app_properties(app_properties) == marker


def test_managed_resource_marker_from_app_properties_missing_key():
    assert ManagedResourceMarker.from_app_properties({"other": "value"}) is None
    assert ManagedResourceMarker.from_app_properties(None) is None


def test_google_drive_app_property_query_string():
    query = GoogleDriveAppPropertyQuery(
        key=DrivePulumiAppPropertyKey.RESOURCE_KEY, value="tree-report"
    )
    expected = (
        "appProperties has { key='pulumi.resourceKey' and value='tree-report' }"
        " and trashed = false"
    )
    assert query.query_string == expected


def test_folder_inputs_extra_parent_ids_sorted_and_deduped():
    inputs = FolderInputs(
        name="report",
        resource_key="tree-report",
        parent="folder_a",
        extra_parent_ids=["folder_c", "folder_b", "folder_b"],
        client_secrets_path=Path("secrets.json"),
        token_path=Path("token.json"),
    )

    assert inputs.extra_parent_ids == ["folder_b", "folder_c"]


def test_tree_path_parse_and_as_string_roundtrip():
    path = TreePath.parse("finances/_robots/finances-7")
    assert path.segments == ("finances", "_robots", "finances-7")
    assert path.as_string == "finances/_robots/finances-7"
    assert str(path) == "finances/_robots/finances-7"


def test_tree_path_of_root_and_child():
    root = TreePath.of_root("finances")
    child = root.child("_robots")
    assert child == TreePath.parse("finances/_robots")


def test_tree_path_equal_paths_hash_equal():
    a = TreePath.parse("a/b")
    b = TreePath.parse("a/b")
    assert a == b
    assert hash(a) == hash(b)
    assert {a: "value"}[b] == "value"


def test_dependency_cycle_description():
    cycle = DependencyCycle(
        nodes=(TreePath.parse("a"), TreePath.parse("b"), TreePath.parse("a"))
    )
    assert cycle.description == "a -> b -> a"
    assert str(cycle) == "a -> b -> a"


def test_drive_file_parents_patch_from_parent_diff_both():
    patch = DriveFileParentsPatch.from_parent_diff(
        "file_1", {"folder_b", "folder_a"}, {"folder_z"}
    )
    assert patch.fileId == "file_1"
    assert patch.addParents == "folder_a,folder_b"
    assert patch.removeParents == "folder_z"


def test_drive_file_parents_patch_from_parent_diff_none():
    patch = DriveFileParentsPatch.from_parent_diff("file_1", set(), set())
    assert patch.addParents is None
    assert patch.removeParents is None


def test_search_query_derived_attr():
    query = GoogleDriveSearchQuery(
        mime_type=GoogleDriveMimeType.SPREADSHEET,
        name="Finance 2026",
        parent="folder_123",
    )

    expected = "mimeType = 'application/vnd.google-apps.spreadsheet' and name = 'Finance 2026' and 'folder_123' in parents and trashed = false"
    assert query.query_string == expected


def test_search_query_no_parent():
    query = GoogleDriveSearchQuery(
        mime_type=GoogleDriveMimeType.FOLDER, name="Root Folder"
    )

    expected = "mimeType = 'application/vnd.google-apps.folder' and name = 'Root Folder' and 'root' in parents and trashed = false"
    assert query.query_string == expected
