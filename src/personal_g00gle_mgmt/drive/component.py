import os
from typing import Optional

import pulumi

from ..utils import generate_resource_name, get_file_hash
from .models import DriveSpec, TreeNode
from .resource import Folder


class FolderTree(pulumi.ComponentResource):
    def __init__(
        self,
        tree_name: str,
        spec: DriveSpec,
        client_secrets_path: pulumi.Input[str],
        token_path: Optional[pulumi.Input[str]] = "./token.json",
        opts: Optional[pulumi.ResourceOptions] = None,
    ):
        super().__init__("custom:gdrive:FolderTree", tree_name, {}, opts)

        def build_node(
            node_name: str,
            node: TreeNode,
            parent_id: Optional[pulumi.Input[str]] = None,
            prefix: str = "",
        ):
            abs_source = os.path.abspath(node.source) if node.source else None
            source_hash = get_file_hash(abs_source) if abs_source else None

            mime_type = node.mime_type.value

            resource_id = node.node_id or node_name
            resource_name = generate_resource_name(tree_name, resource_id)

            child_opts = pulumi.ResourceOptions(parent=self)

            perms_dicts = [p.model_dump() for p in node.permissions]

            folder = Folder(
                resource_name,
                name=node_name,
                parent=parent_id,
                client_secrets_path=client_secrets_path,
                token_path=token_path,
                description=node.description,
                folder_color_rgb=node.color,
                permissions=perms_dicts,
                mime_type=mime_type,
                source=abs_source,
                source_hash=source_hash,
                opts=child_opts,
            )

            for child_name, child_node in node.children.items():
                build_node(
                    child_name,
                    child_node,
                    parent_id=folder.id,
                    prefix=f"{prefix}{node_name}-",
                )

        for root_name, root_node in spec.root.items():
            build_node(root_name, root_node)

        self.register_outputs({})
