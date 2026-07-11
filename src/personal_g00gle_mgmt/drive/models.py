from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, RootModel, model_validator


class PermissionModel(BaseModel):
    emailAddress: str
    role: str
    type: str


class PermissionResponse(BaseModel):
    id: str
    emailAddress: Optional[str] = None
    role: Optional[str] = None
    type: Optional[str] = None


class GoogleDriveFolderColor(str, Enum):
    CHOCOLATE = "#ac725e"
    OLD_BRICK = "#d06b64"
    CARDINAL = "#f83a22"
    WILD_STRAWBERRY = "#fa573c"
    MARS_ORANGE = "#ff7537"
    YELLOW_CAB = "#ffad46"
    SPEARMINT = "#42d692"
    VERN_FERN = "#16a765"
    MACARONI = "#7bd148"
    DESIGN = "#b3dc6c"
    YELLOW = "#fbe983"
    LIGHT_GREEN = "#fad165"
    SEAFOAM = "#92e1c0"
    RAINY_SKY = "#9fe1e7"
    CORNFLOWER = "#9fc6e7"
    BLUE = "#4986e7"
    LIGHT_PURPLE = "#9a9cff"
    PURPLE = "#b99aff"
    MOUSE = "#8f8f8f"
    MOUNTAIN_GREY = "#cabdbf"
    EARTHWORM = "#cca6ac"
    BUBBLE_GUM = "#f691b2"
    PURPLE_DINOSAUR = "#cd74e6"
    TOY_AUBERGINE = "#a47ae2"


class BinaryMimeType(str, Enum):
    OCTET_STREAM = "application/octet-stream"


class OfficeDocumentMimeType(str, Enum):
    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    @property
    def upload_mime_type(self) -> "OfficeDocumentMimeType":
        return self


class GoogleDriveMimeType(str, Enum):
    FOLDER = "application/vnd.google-apps.folder"
    SPREADSHEET = "application/vnd.google-apps.spreadsheet"
    DOCUMENT = "application/vnd.google-apps.document"

    @property
    def upload_mime_type(self) -> Union[OfficeDocumentMimeType, BinaryMimeType]:
        if self == GoogleDriveMimeType.SPREADSHEET:
            return OfficeDocumentMimeType.XLSX
        elif self == GoogleDriveMimeType.DOCUMENT:
            return OfficeDocumentMimeType.DOCX
        return BinaryMimeType.OCTET_STREAM


AnyMimeType = Union[GoogleDriveMimeType, OfficeDocumentMimeType]


class GoogleDriveFileBody(BaseModel):
    name: Optional[str] = None
    mimeType: Optional[AnyMimeType] = None
    parents: Optional[List[str]] = None
    description: Optional[str] = None
    folderColorRgb: Optional[GoogleDriveFolderColor] = None
    trashed: Optional[bool] = None


class GoogleDriveSearchQuery(BaseModel):
    mime_type: AnyMimeType
    name: str
    parent: Optional[str] = None
    trashed: bool = False

    @property
    def query_string(self) -> str:
        parent_id = self.parent if self.parent else "root"
        trashed_str = "true" if self.trashed else "false"
        return f"mimeType = '{self.mime_type.value}' and name = '{self.name}' and '{parent_id}' in parents and trashed = {trashed_str}"


class GoogleDriveFileResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    folderColorRgb: Optional[GoogleDriveFolderColor] = None
    mimeType: AnyMimeType
    parents: List[str] = Field(default_factory=list)
    trashed: bool = False


class FolderInputs(BaseModel):
    name: str
    parent: Optional[str] = None
    client_secrets_path: Path
    token_path: Path
    description: Optional[str] = None
    folder_color_rgb: Optional[str] = None
    permissions: List[PermissionModel] = Field(default_factory=list)
    mime_type: AnyMimeType = Field(default=GoogleDriveMimeType.FOLDER)
    source: Optional[Path] = None
    source_hash: Optional[str] = None


class TreeNode(BaseModel):
    description: Optional[str] = Field(None, alias="_description")
    color: Optional[GoogleDriveFolderColor] = Field(None, alias="_color")
    permissions: List[PermissionModel] = Field(
        default_factory=list, alias="_permissions"
    )
    source: Optional[Path] = Field(None, alias="_source")
    mime_type: AnyMimeType = Field(GoogleDriveMimeType.FOLDER, alias="_mimeType")
    node_id: Optional[str] = Field(None, alias="_id")
    children: Dict[str, TreeNode] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def extract_children(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        known_aliases = {
            field.alias or name
            for name, field in cls.model_fields.items()
            if name != "children"
        }

        extracted = {}
        children = {}
        for k, v in data.items():
            if k in known_aliases:
                extracted[k] = v
            else:
                children[k] = v

        extracted["children"] = children
        return extracted


TreeNode.model_rebuild()


class DriveSpec(RootModel[Dict[str, TreeNode]]):
    pass
