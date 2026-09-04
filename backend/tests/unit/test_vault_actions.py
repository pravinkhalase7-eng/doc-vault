from types import SimpleNamespace

from app.ai.vault_actions import (
    clean_name,
    document_matches_name,
    parse_vault_intent,
)


def test_parse_delete_all_files_means_whole_vault():
    for phrase in (
        "delete all files",
        "delete all my files",
        "delete all the files",
        "delete all documents",
        "delete everything",
        "empty the vault",
        "delete all",
    ):
        intent = parse_vault_intent(phrase)
        assert intent.kind == "delete_all_files", phrase
        assert intent.name is None


def test_parse_delete_all_personal_files():
    intent = parse_vault_intent("delete all personal files")
    assert intent.kind == "delete_collection_files"
    assert intent.name == "personal"


def test_parse_delete_all_files_in_personal():
    intent = parse_vault_intent("delete all the files in Personal")
    assert intent.kind == "delete_collection_files"
    assert intent.name == "personal"


def test_parse_delete_all_personal_files_typo():
    intent = parse_vault_intent("delete all pesonal files")
    assert intent.kind == "delete_collection_files"
    assert intent.name == "pesonal"


def test_parse_delete_collection_asks_for_name():
    intent = parse_vault_intent("delete collection")
    assert intent.kind == "delete_collection"
    assert intent.name is None


def test_parse_delete_named_collection():
    intent = parse_vault_intent("delete the collection named education")
    assert intent.kind == "delete_collection"
    assert intent.name == "education"


def test_parse_delete_file_asks_for_name():
    intent = parse_vault_intent("delete file")
    assert intent.kind == "delete_document"
    assert intent.name is None
    assert parse_vault_intent("delete document").kind == "delete_document"


def test_parse_show_documents():
    assert parse_vault_intent("show documents").kind == "list_documents"
    assert parse_vault_intent("show me my files").kind == "list_documents"
    assert parse_vault_intent("list all documents").kind == "list_documents"
    shown = parse_vault_intent("show passport")
    assert shown.kind == "show_document"
    assert shown.name == "passport"
    assert parse_vault_intent("show me all collections").kind == "none"
    assert parse_vault_intent("delete documents").kind == "delete_document"


def test_parse_delete_named_document():
    intent = parse_vault_intent("delete the document Passport")
    assert intent.kind == "delete_document"
    assert intent.name == "passport"


def test_parse_delete_named_falls_back():
    intent = parse_vault_intent("delete Passport")
    assert intent.kind == "delete_named"
    assert intent.name == "passport"


def test_parse_confirm_and_cancel():
    assert parse_vault_intent("yes").kind == "confirm"
    assert parse_vault_intent("Confirm").kind == "confirm"
    assert parse_vault_intent("delete them").kind == "confirm"
    assert parse_vault_intent("cancel").kind == "cancel"
    assert parse_vault_intent("no").kind == "cancel"


def test_clean_name_strips_articles():
    assert clean_name("the Personal collection") == "Personal"
    assert clean_name("my passport file") == "passport"


def test_document_matches_saved_title():
    doc = SimpleNamespace(title="Passport", original_filename="scan-123.jpg")
    assert document_matches_name(doc, "passport")
    assert document_matches_name(doc, "Passport")
    assert document_matches_name(doc, "scan-123")
    assert not document_matches_name(doc, "insurance")
