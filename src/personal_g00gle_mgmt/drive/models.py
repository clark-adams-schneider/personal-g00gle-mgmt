from typing import List, Optional

from pydantic import BaseModel, Field


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
