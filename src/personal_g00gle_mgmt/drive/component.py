from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

import pulumi

from ..utils import generate_resource_name, get_file_hash
from .models import DriveSpec, TreeNode
from .resource import Folder

TREE_PATH_SEPARATOR = "/"


@dataclass
class PlannedNode:
    path: str
    name: str
    node: TreeNode
    parent_path: Optional[str]


def _flatten_spec(spec: DriveSpec) -> Dict[str, PlannedNode]:
    """Walk the spec tree once, assigning each node a unique slash-joined path.

    These paths are what `_parents` references in the spec resolve against.
    """
    planned: Dict[str, PlannedNode] = {}

    def visit(node_name: str, node: TreeNode, parent_path: Optional[str]) -> None:
        path = (
            f"{parent_path}{TREE_PATH_SEPARATOR}{node_name}"
            if parent_path
            else node_name
        )
        if path in planned:
            raise ValueError(f"Duplicate node path in DriveSpec: {path!r}")
        planned[path] = PlannedNode(
            path=path, name=node_name, node=node, parent_path=parent_path
        )
        for child_name, child_node in node.children.items():
            visit(child_name, child_node, path)

    for root_name, root_node in spec.root.items():
        visit(root_name, root_node, None)

    return planned


def _dependency_paths(plan: PlannedNode, planned: Dict[str, PlannedNode]) -> List[str]:
    deps = [plan.parent_path] if plan.parent_path else []
    for ref in plan.node.extra_parents:
        if ref not in planned:
            raise ValueError(
                f"Node {plan.path!r} has unknown _parents reference: {ref!r}"
            )
        deps.append(ref)
    return deps


def _topological_build_order(planned: Dict[str, PlannedNode]) -> List[str]:
    """Order nodes so every node is built after its primary and extra parents.

    A plain top-down tree walk can't do this on its own: an `_parents` entry
    may point at a node that hasn't been visited yet (e.g. a later sibling's
    descendant), so we need the full dependency graph before picking an order.
    """
    dependencies = {
        path: _dependency_paths(plan, planned) for path, plan in planned.items()
    }

    visited: Dict[str, bool] = {}
    order: List[str] = []

    def visit(path: str, stack: List[str]) -> None:
        if visited.get(path):
            return
        if path in stack:
            cycle = " -> ".join([*stack, path])
            raise ValueError(f"Cycle detected among DriveSpec parents: {cycle}")
        stack.append(path)
        for dep_path in dependencies[path]:
            visit(dep_path, stack)
        stack.pop()
        visited[path] = True
        order.append(path)

    for path in planned:
        visit(path, [])

    return order


class FolderTree(pulumi.ComponentResource):
    def __init__(
        self,
        tree_name: str,
        spec: DriveSpec,
        client_secrets_path: Union[str, Path, pulumi.Input[str]],
        token_path: Union[str, Path, pulumi.Input[str]] = Path("./token.json"),
        opts: Optional[pulumi.ResourceOptions] = None,
    ):
        super().__init__("custom:gdrive:FolderTree", tree_name, {}, opts)

        planned = _flatten_spec(spec)
        build_order = _topological_build_order(planned)
        folder_ids: Dict[str, pulumi.Output[str]] = {}

        for path in build_order:
            folder_ids[path] = self._build_node(
                tree_name=tree_name,
                plan=planned[path],
                folder_ids=folder_ids,
                client_secrets_path=client_secrets_path,
                token_path=token_path,
            )

        self.register_outputs({})

    def _build_node(
        self,
        tree_name: str,
        plan: PlannedNode,
        folder_ids: Dict[str, pulumi.Output[str]],
        client_secrets_path: Union[str, Path, pulumi.Input[str]],
        token_path: Union[str, Path, pulumi.Input[str]],
    ) -> pulumi.Output[str]:
        node = plan.node
        abs_source = node.source.resolve() if node.source else None
        source_hash = get_file_hash(abs_source) if abs_source else None

        resource_id = node.node_id or plan.name
        resource_name = generate_resource_name(tree_name, resource_id)

        parent_id = folder_ids[plan.parent_path] if plan.parent_path else None
        extra_parent_ids = [folder_ids[ref] for ref in node.extra_parents]

        perms_dicts = [p.model_dump() for p in node.permissions]

        folder = Folder(
            resource_name,
            name=plan.name,
            parent=parent_id,
            extra_parent_ids=extra_parent_ids or None,
            client_secrets_path=str(client_secrets_path),
            token_path=str(token_path),
            description=node.description,
            folder_color_rgb=node.color.value if node.color else None,
            permissions=perms_dicts,
            mime_type=node.mime_type.value,
            source=str(abs_source) if abs_source else None,
            source_hash=source_hash,
            opts=pulumi.ResourceOptions(parent=self),
        )

        return folder.id
