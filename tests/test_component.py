import pytest

from personal_g00gle_mgmt.drive.component import (
    _flatten_spec,
    _topological_build_order,
)
from personal_g00gle_mgmt.drive.models import DriveSpec


def test_flatten_spec_assigns_slash_joined_paths():
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

    assert set(planned) == {
        "finances",
        "finances/_robots",
        "finances/_robots/finances-7",
    }
    assert planned["finances/_robots/finances-7"].parent_path == "finances/_robots"
    assert planned["finances"].parent_path is None


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

    assert order.index("root") < order.index("root/child")
    assert order.index("root/child") < order.index("root/child/grandchild")


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

    assert order.index("other/target") < order.index("reports/quarterly")


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
