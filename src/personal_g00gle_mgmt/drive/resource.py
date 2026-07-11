from typing import Optional, Any, Dict, List
import pulumi
from pulumi.dynamic import Resource
from .provider import FolderProvider

class Folder(Resource):
    name: pulumi.Output[str]
    parent: pulumi.Output[Optional[str]]
    client_secrets_path: pulumi.Output[str]
    token_path: pulumi.Output[str]
    description: pulumi.Output[Optional[str]]
    folder_color_rgb: pulumi.Output[Optional[str]]
    permissions: pulumi.Output[Optional[List[Dict[str, Any]]]]
    mime_type: pulumi.Output[str]
    source: pulumi.Output[Optional[str]]
    source_hash: pulumi.Output[Optional[str]]

    def __init__(self,
                 resource_name: str,
                 name: pulumi.Input[str],
                 parent: Optional[pulumi.Input[str]] = None,
                 client_secrets_path: Optional[pulumi.Input[str]] = None,
                 token_path: Optional[pulumi.Input[str]] = None,
                 description: Optional[pulumi.Input[str]] = None,
                 folder_color_rgb: Optional[pulumi.Input[str]] = None,
                 permissions: Optional[pulumi.Input[List[Dict[str, Any]]]] = None,
                 mime_type: Optional[pulumi.Input[str]] = 'application/vnd.google-apps.folder',
                 source: Optional[pulumi.Input[str]] = None,
                 source_hash: Optional[pulumi.Input[str]] = None,
                 opts: Optional[pulumi.ResourceOptions] = None):
        
        props = {
            'name': name,
            'parent': parent,
            'client_secrets_path': client_secrets_path,
            'token_path': token_path,
            'description': description,
            'folder_color_rgb': folder_color_rgb,
            'permissions': permissions,
            'mime_type': mime_type,
            'source': source,
            'source_hash': source_hash,
        }
        
        super().__init__(FolderProvider(), resource_name, props, opts)
