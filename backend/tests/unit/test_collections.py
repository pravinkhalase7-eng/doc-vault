from types import SimpleNamespace

from app.collections.service import collection_matches_query, descendants_of, is_default_collection, would_cycle
from app.search.query import lists_all_collections, query_terms


def test_would_cycle_detects_self_parent():
    assert would_cycle("a", "a", {"a": None})


def test_would_cycle_detects_ancestor_loop():
    parents = {"child": "parent", "parent": "root", "root": None}
    assert would_cycle("root", "child", parents)
    assert not would_cycle("child", "other", {**parents, "other": None})


def test_descendants_include_nested_children():
    parents = {
        "root": None,
        "a": "root",
        "b": "a",
        "c": "root",
    }
    assert descendants_of("root", parents) == {"a", "b", "c"}
    assert descendants_of("a", parents) == {"b"}
    assert descendants_of("c", parents) == set()


def test_query_terms_drop_stopwords():
    assert query_terms("give the education document") == ["education"]
    assert query_terms("Show my Personal files") == ["personal"]
    assert query_terms("personal docs") == ["personal"]
    assert query_terms("temporary doc") == ["temporary"]


def test_collection_matches_natural_language_query():
    col = SimpleNamespace(name="education", description=None, ai_context=None, extra={})
    assert collection_matches_query(col, "give the education document")
    assert collection_matches_query(col, "education")
    assert not collection_matches_query(col, "car insurance")


def test_collection_matches_personal_and_temporary():
    personal = SimpleNamespace(name="Personal", description=None, ai_context=None, extra={})
    temporary = SimpleNamespace(name="temporary", description=None, ai_context=None, extra={})
    assert collection_matches_query(personal, "personal docs")
    assert collection_matches_query(temporary, "temporary doc")
    assert not collection_matches_query(personal, "temporary doc")
    assert not collection_matches_query(temporary, "personal docs")
    assert not collection_matches_query(personal, "impersonal records")


def test_collection_matches_typos_like_orage():
    orange = SimpleNamespace(name="Orange", description=None, ai_context=None, extra={})
    assert collection_matches_query(orange, "give me orange docs")
    assert collection_matches_query(orange, "give me orage docs")
    assert collection_matches_query(orange, "orage")
    assert not collection_matches_query(orange, "storage docs")


def test_lists_all_collections_intent():
    assert lists_all_collections("show me all collections")
    assert lists_all_collections("list my folders")
    assert lists_all_collections("what collections do I have")
    assert not lists_all_collections("personal docs")
    assert not lists_all_collections("temporary collection")
    assert not lists_all_collections("when does insurance expire")


def test_is_default_collection_by_flag_or_name():
    flagged = SimpleNamespace(name="Inbox", parent_id=None, extra={"is_default": True})
    named = SimpleNamespace(name="Default", parent_id=None, extra={})
    nested = SimpleNamespace(name="Default", parent_id="root", extra={})
    other = SimpleNamespace(name="Personal", parent_id=None, extra={})
    assert is_default_collection(flagged)
    assert is_default_collection(named)
    assert not is_default_collection(nested)
    assert not is_default_collection(other)
