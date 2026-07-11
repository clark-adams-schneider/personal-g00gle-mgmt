import os
from typing import Any, Dict, Optional

import pulumi

from ..utils import get_file_hash
from .resource import Folder


class FolderTree(pulumi.ComponentResource):
    def __init__(
        self,
        tree_name: str,
        spec: Dict[str, Any],
        client_secrets_path: pulumi.Input[str],
        token_path: Optional[pulumi.Input[str]] = "./token.json",
        opts: Optional[pulumi.ResourceOptions] = None,
    ):

        super().__init__("custom:gdrive:FolderTree", tree_name, {}, opts)

        def build_node(
            node_name: str,
            children_spec: Any,
            parent_id: Optional[pulumi.Input[str]] = None,
            prefix: str = "",
        ):
            metadata = {}
            children = {}

            if isinstance(children_spec, dict):
                for k, v in children_spec.items():
                    if k.startswith("_"):
                        metadata[k] = v
                    else:
                        children[k] = v

            desc = metadata.get("_description")
            color = metadata.get("_color")
            perms = metadata.get("_permissions")
            source_file = metadata.get("_source")

            # Resolve relative source path to absolute path
            abs_source = os.path.abspath(source_file) if source_file else None
            source_hash = get_file_hash(abs_source) if abs_source else None

            ftype = metadata.get("_type", "folder")
            if ftype == "spreadsheet":
                mime_type = "application/vnd.google-apps.spreadsheet"
            elif ftype == "document":
                mime_type = "application/vnd.google-apps.document"
            else:
                mime_type = "application/vnd.google-apps.folder"

            resource_id = metadata.get("_id") or node_name
            resource_name = f"{tree_name}-{resource_id}".replace("-", "_").replace(
                " ", "_"
            )

            child_opts = pulumi.ResourceOptions(parent=self)

            folder = Folder(
                resource_name,
                name=node_name,
                parent=parent_id,
                client_secrets_path=client_secrets_path,
                token_path=token_path,
                description=desc,
                folder_color_rgb=color,
                permissions=perms,
                mime_type=mime_type,
                source=abs_source,
                source_hash=source_hash,
                opts=child_opts,
            )

            for child_name, grandchild_spec in children.items():
                build_node(
                    child_name,
                    grandchild_spec,
                    parent_id=folder.id,
                    prefix=f"{prefix}{node_name}-",
                )

        for root_name, root_spec in spec.items():
            build_node(root_name, root_spec)
        self.register_outputs({})
