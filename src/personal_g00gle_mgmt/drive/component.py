from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

import pulumi

from ..utils import generate_resource_name, get_file_hash
from .models import DependencyCycle, DriveSpec, TreeNode, TreePath
from .resource import Folder


@dataclass
class PlannedNode:
    path: TreePath
    name: str
    node: TreeNode
    parent_path: Optional[TreePath]
    extra_parent_paths: List[TreePath] = field(default_factory=list)

    def dependency_paths(self) -> List[TreePath]:
        deps = [self.parent_path] if self.parent_path else []
        deps.extend(self.extra_parent_paths)
        return deps


def _flatten_spec(spec: DriveSpec) -> Dict[TreePath, PlannedNode]:
    """Walk the spec tree once, assigning each node its TreePath.

    These paths are what `_parents` references in the spec resolve against.
    """
    planned: Dict[TreePath, PlannedNode] = {}

    def visit(node_name: str, node: TreeNode, parent_path: Optional[TreePath]) -> None:
        path = (
            parent_path.child(node_name) if parent_path else TreePath.of_root(node_name)
        )
        if path in planned:
            raise ValueError(f"Duplicate node path in DriveSpec: {path}")
        planned[path] = PlannedNode(
            path=path, name=node_name, node=node, parent_path=parent_path
        )
        for child_name, child_node in node.children.items():
            visit(child_name, child_node, path)

    for root_name, root_node in spec.root.items():
        visit(root_name, root_node, None)

    return planned


def _resolve_extra_parent_references(planned: Dict[TreePath, PlannedNode]) -> None:
    """Parse and validate each node's `_parents` refs against the flattened spec.

    Populates `PlannedNode.extra_parent_paths` in place so downstream steps
    (dependency ordering, resource construction) never re-parse the raw refs.
    """
    for plan in planned.values():
        resolved_paths = []
        for raw_ref in plan.node.extra_parents:
            ref_path = TreePath.parse(raw_ref)
            if ref_path not in planned:
                raise ValueError(
                    f"Node {plan.path} has unknown _parents reference: {raw_ref!r}"
                )
            resolved_paths.append(ref_path)
        plan.extra_parent_paths = resolved_paths


def _topological_build_order(planned: Dict[TreePath, PlannedNode]) -> List[TreePath]:
    """Order nodes so every node is built after its primary and extra parents.

    A plain top-down tree walk can't do this on its own: an `_parents` entry
    may point at a node that hasn't been visited yet (e.g. a later sibling's
    descendant), so we need the full dependency graph before picking an order.
    """
    _resolve_extra_parent_references(planned)

    visited: Dict[TreePath, bool] = {}
    order: List[TreePath] = []

    def visit(path: TreePath, stack: List[TreePath]) -> None:
        if visited.get(path):
            return
        if path in stack:
            cycle = DependencyCycle(nodes=(*stack, path))
            raise ValueError(f"Cycle detected among DriveSpec parents: {cycle}")
        stack.append(path)
        for dep_path in planned[path].dependency_paths():
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
        folder_ids: Dict[TreePath, pulumi.Output[str]] = {}

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
        folder_ids: Dict[TreePath, pulumi.Output[str]],
        client_secrets_path: Union[str, Path, pulumi.Input[str]],
        token_path: Union[str, Path, pulumi.Input[str]],
    ) -> pulumi.Output[str]:
        node = plan.node
        abs_source = node.source.resolve() if node.source else None
        source_hash = get_file_hash(abs_source) if abs_source else None

        resource_id = node.node_id or plan.name
        resource_name = generate_resource_name(tree_name, resource_id)

        parent_id = folder_ids[plan.parent_path] if plan.parent_path else None
        extra_parent_ids = [folder_ids[p] for p in plan.extra_parent_paths]

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
