from types import SimpleNamespace

from app.collections.service import descendants_of
from app.family.service import member_visible_ids, rewrite_shared_parent


def test_member_sees_shared_folder_and_nested_children():
    parents = {"bills": None, "insurance": "bills", "car": "insurance", "ids": None}
    visible = member_visible_ids({"insurance"}, parents)
    assert visible == {"insurance", "car"}
    assert "bills" not in visible
    assert "ids" not in visible


def test_shared_tree_lifts_folder_when_parent_was_not_shared():
    visible = {"insurance", "car"}
    assert rewrite_shared_parent("insurance", "bills", visible) is None
    assert rewrite_shared_parent("car", "insurance", visible) == "insurance"


def test_sharing_root_keeps_nested_parents():
    parents = {"home": None, "kids": "home", "school": "kids"}
    visible = member_visible_ids({"home"}, parents)
    assert visible == {"home", "kids", "school"}
    assert rewrite_shared_parent("kids", "home", visible) == "home"
    assert rewrite_shared_parent("school", "kids", visible) == "kids"


def test_default_folder_is_not_shareable_by_name():
    from app.collections.service import is_default_collection

    default = SimpleNamespace(name="Default", parent_id=None, extra={})
    personal = SimpleNamespace(name="Family docs", parent_id=None, extra={})
    assert is_default_collection(default)
    assert not is_default_collection(personal)
