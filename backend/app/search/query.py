import re

STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "my",
        "me",
        "i",
        "is",
        "are",
        "of",
        "for",
        "to",
        "in",
        "on",
        "and",
        "or",
        "please",
        "show",
        "give",
        "get",
        "find",
        "list",
        "all",
        "any",
        "doc",
        "docs",
        "document",
        "documents",
        "file",
        "files",
        "folder",
        "folders",
        "collection",
        "collections",
        "related",
        "about",
        "your",
        "you",
        "want",
        "need",
        "can",
        "could",
        "would",
        "this",
        "that",
        "with",
        "from",
        "have",
        "has",
        "what",
        "which",
        "where",
        "when",
        "who",
        "how",
        "vault",
    }
)


def query_terms(query: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]{3,}", (query or "").lower())
    terms: list[str] = []
    for token in tokens:
        if token in STOPWORDS or token in terms:
            continue
        terms.append(token)
    return terms


def lists_all_collections(query: str) -> bool:
    question = (query or "").lower().strip()
    if not question:
        return False
    if not re.search(r"\b(collections?|folders?)\b", question):
        return False
    if query_terms(question):
        return False
    if question in {"collections", "collection", "folders", "folder"}:
        return True
    return bool(re.search(r"\b(show|list|give|get|find|what|which|all|every|have)\b", question))
