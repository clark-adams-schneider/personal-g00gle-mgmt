import pytest

from personal_g00gle_mgmt.drive.component import (
    _flatten_spec,
    _topological_build_order,
)
from personal_g00gle_mgmt.drive.models import DriveSpec, TreePath


def test_flatten_spec_assigns_tree_paths():
    spec = DriveSpec.model_validate(
        {
            "finances": {
                "_robots": {
                    "finances-7": {},
                },
            },
        }
    )

    planned = _flatten_spec(spec)

    assert {p.as_string for p in planned} == {
        "finances",
        "finances/_robots",
        "finances/_robots/finances-7",
    }
    grandchild = planned[TreePath.parse("finances/_robots/finances-7")]
    assert grandchild.parent_path == TreePath.parse("finances/_robots")
    assert planned[TreePath.parse("finances")].parent_path is None


def test_topological_build_order_respects_tree_parents():
    spec = DriveSpec.model_validate(
        {
            "root": {
                "child": {
                    "grandchild": {},
                },
            },
        }
    )

    planned = _flatten_spec(spec)
    order = _topological_build_order(planned)

    root = TreePath.parse("root")
    child = TreePath.parse("root/child")
    grandchild = TreePath.parse("root/child/grandchild")
    assert order.index(root) < order.index(child)
    assert order.index(child) < order.index(grandchild)


def test_topological_build_order_respects_cross_branch_parents_reference():
    spec = DriveSpec.model_validate(
        {
            "reports": {
                "quarterly": {"_parents": ["other/target"]},
            },
            "other": {
                "target": {},
            },
        }
    )

    planned = _flatten_spec(spec)
    order = _topological_build_order(planned)

    target = TreePath.parse("other/target")
    quarterly = TreePath.parse("reports/quarterly")
    assert order.index(target) < order.index(quarterly)


def test_topological_build_order_raises_on_unknown_reference():
    spec = DriveSpec.model_validate(
        {
            "reports": {"_parents": ["does/not/exist"]},
        }
    )

    planned = _flatten_spec(spec)
    with pytest.raises(ValueError, match="unknown _parents reference"):
        _topological_build_order(planned)


def test_topological_build_order_raises_on_cycle():
    spec = DriveSpec.model_validate(
        {
            "a": {"_parents": ["b"]},
            "b": {"_parents": ["a"]},
        }
    )

    planned = _flatten_spec(spec)
    with pytest.raises(ValueError, match="Cycle detected"):
        _topological_build_order(planned)
