from personal_g00gle_mgmt.drive.models import (
    GoogleDriveFolderColor,
    GoogleDriveMimeType,
    GoogleDriveSearchQuery,
    OfficeDocumentMimeType,
    TreeNode,
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
