from app.ai.chat_intent import is_general_chat, is_greeting, local_chat_reply
from app.ai.evidence_checker import MISSING, validate_answer
from app.ai.router import AIRouter


def test_hello_is_a_greeting_not_a_vault_search():
    assert is_greeting("hello")
    assert is_greeting("Hi!")
    assert is_greeting("Hey there")
    assert is_greeting("good morning")
    assert is_greeting("hello how are you")
    assert is_general_chat("hello, can you help?")
    assert is_general_chat("hello")
    assert is_general_chat("what can you do?")
    assert is_general_chat("what is GST")
    assert not is_greeting("when does my passport expire")
    assert not is_general_chat("when does my passport expire")
    assert not is_general_chat("show me all collections")
    assert not is_general_chat("help me find my passport")
    assert not is_general_chat("Remind me tomorrow at 10am to renew my passport")


def test_hello_reply_greets_instead_of_missing_documents():
    reply = local_chat_reply("hello")
    assert "couldn't find" not in reply.lower()
    assert "hi" in reply.lower()
    assert "docvault" in reply.lower()


def test_validate_answer_keeps_greeting_when_vault_is_empty():
    answer, evidence = validate_answer("Hi — I'm DocVault.", [], [], question="hello")
    assert "couldn't find" not in answer.lower()
    assert evidence == []


def test_validate_answer_still_blocks_ungrounded_document_questions():
    answer, evidence = validate_answer("March 2029", [], [], question="when does my passport expire")
    assert answer == MISSING
    assert evidence == []


def test_local_reason_greets_hello():
    reply = AIRouter()._local_reason({"question": "hello", "records": [], "language": "en"})
    assert "couldn't find" not in reply.lower()
    assert "hi" in reply.lower()
