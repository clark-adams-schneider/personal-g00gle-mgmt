from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, RootModel, model_validator


class PermissionModel(BaseModel):
    emailAddress: str
    role: str
    type: str


class FolderInputs(BaseModel):
    name: str
    parent: Optional[str] = None
    client_secrets_path: str
    token_path: str
    description: Optional[str] = None
    folder_color_rgb: Optional[str] = None
    permissions: List[PermissionModel] = Field(default_factory=list)
    mime_type: str = "application/vnd.google-apps.folder"
    source: Optional[str] = None
    source_hash: Optional[str] = None


class NodeType(str, Enum):
    FOLDER = "folder"
    SPREADSHEET = "spreadsheet"
    DOCUMENT = "document"

    @property
    def mime_type(self) -> str:
        mapping = {
            NodeType.FOLDER: "application/vnd.google-apps.folder",
            NodeType.SPREADSHEET: "application/vnd.google-apps.spreadsheet",
            NodeType.DOCUMENT: "application/vnd.google-apps.document",
        }
        return mapping[self]


class TreeNode(BaseModel):
    description: Optional[str] = Field(None, alias="_description")
    color: Optional[str] = Field(None, alias="_color")
    permissions: List[PermissionModel] = Field(
        default_factory=list, alias="_permissions"
    )
    source: Optional[str] = Field(None, alias="_source")
    node_type: NodeType = Field(NodeType.FOLDER, alias="_type")
    node_id: Optional[str] = Field(None, alias="_id")
    children: Dict[str, TreeNode] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def extract_children(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        extracted = {}
        children = {}
        for k, v in data.items():
            if k.startswith("_"):
                extracted[k] = v
            else:
                children[k] = v
        extracted["children"] = children
        return extracted


TreeNode.model_rebuild()


class DriveSpec(RootModel[Dict[str, TreeNode]]):
    pass
