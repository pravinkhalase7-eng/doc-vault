"""Specialized ADK agents. They never query the database directly."""

from app.ai.adk.root_agent import ROOT_INSTRUCTION

DOCUMENT_AGENT = "Document metadata, classification, and evidence."
SEARCH_AGENT = "Hybrid keyword + vector search over permitted documents."
EMAIL_AGENT = "Notification drafts only. Never attach original files."
REMINDER_AGENT = "Create structured reminder payloads for backend validation."
COLLECTION_AGENT = "Propose collections. Never move files without approval."
PRIVACY_AGENT = "Explain data access and enforce exclude-from-AI."
TASK_AGENT = "Create tasks that require user confirmation before side effects."

AGENTS = {
    "DocVaultAgent": ROOT_INSTRUCTION,
    "DocumentAgent": DOCUMENT_AGENT,
    "SearchAgent": SEARCH_AGENT,
    "EmailNotificationAgent": EMAIL_AGENT,
    "ReminderAgent": REMINDER_AGENT,
    "CollectionAgent": COLLECTION_AGENT,
    "PrivacyAgent": PRIVACY_AGENT,
    "TaskAgent": TASK_AGENT,
}
