from datetime import date, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class APIResponse(APIModel, Generic[T]):
    success: bool = True
    data: T


class ErrorBody(APIModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(APIModel):
    success: bool = False
    error: ErrorBody


class RegisterRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=200)


class LoginRequest(APIModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class RefreshRequest(APIModel):
    refresh_token: str


class VerifyEmailRequest(APIModel):
    token: str


class ForgotPasswordRequest(APIModel):
    email: EmailStr


class ResetPasswordRequest(APIModel):
    token: str
    password: str = Field(min_length=10, max_length=128)


class TokenPair(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(APIModel):
    id: str
    email: str
    full_name: str
    role: str
    email_verified_at: datetime | None
    onboarding_completed: bool
    totp_enabled: bool


class PreferenceOut(APIModel):
    language: str
    theme: str
    ai_privacy_mode: str
    external_ai_enabled: bool
    allow_highly_sensitive_external: bool
    daily_briefing_enabled: bool
    weekly_report_enabled: bool
    reminder_offsets_days: list[int]
    naming_style: str
    preferred_categories: list
    notification_email: bool
    notification_in_app: bool
    timezone: str


class PreferenceUpdate(APIModel):
    language: str | None = None
    theme: str | None = None
    ai_privacy_mode: str | None = None
    external_ai_enabled: bool | None = None
    allow_highly_sensitive_external: bool | None = None
    daily_briefing_enabled: bool | None = None
    weekly_report_enabled: bool | None = None
    reminder_offsets_days: list[int] | None = None
    naming_style: str | None = None
    preferred_categories: list | None = None
    notification_email: bool | None = None
    notification_in_app: bool | None = None
    timezone: str | None = None
    onboarding_completed: bool | None = None


class DocumentOut(APIModel):
    id: str
    title: str
    original_filename: str
    description: str | None
    mime_type: str
    extension: str
    size_bytes: int
    status: str
    sensitivity: str
    exclude_from_ai: bool
    category_id: str | None
    document_type_id: str | None
    ai_classification: str | None
    ai_confidence: float | None
    verification_status: str
    issue_date: date | None
    expiry_date: date | None
    related_person: str | None
    tags: list[str] = []
    page_count: int | None
    version: int
    created_at: datetime
    updated_at: datetime
    trashed_at: datetime | None = None


class DocumentUpdate(APIModel):
    title: str | None = None
    description: str | None = None
    category_id: str | None = None
    document_type_id: str | None = None
    subcategory: str | None = None
    related_person: str | None = None
    related_entity: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    sensitivity: str | None = None
    exclude_from_ai: bool | None = None
    tags: list[str] | None = None
    verification_status: str | None = None


class DocumentMove(APIModel):
    collection_id: str


class MetadataFieldOut(APIModel):
    id: str
    field_name: str
    value: str | None
    confidence: float | None
    page: int | None
    verification_status: str


class ConfirmMetadataRequest(APIModel):
    fields: list[dict[str, Any]]


class CategoryOut(APIModel):
    id: str
    name: str
    slug: str
    is_system: bool


class CategoryCreate(APIModel):
    name: str = Field(min_length=1, max_length=80)


class CollectionOut(APIModel):
    id: str
    name: str
    description: str | None
    parent_id: str | None = None
    ai_context: str | None = None
    metadata: dict = {}
    goal_key: str | None
    is_default: bool = False
    document_ids: list[str] = []


class CollectionCreate(APIModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    parent_id: str | None = None
    ai_context: str | None = None
    metadata: dict[str, str] | None = None
    goal_key: str | None = None
    document_ids: list[str] = []


class CollectionUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    parent_id: str | None = None
    ai_context: str | None = None
    metadata: dict[str, str] | None = None
    goal_key: str | None = None


class ReminderCreate(APIModel):
    title: str
    document_id: str | None = None
    collection_id: str | None = None
    offset_days: int = 30
    fire_at: datetime | None = None


class ReminderOut(APIModel):
    id: str
    title: str
    document_id: str | None
    offset_days: int
    fire_at: datetime
    sent_at: datetime | None


class TaskCreate(APIModel):
    title: str
    description: str | None = None
    collection_id: str | None = None
    document_id: str | None = None
    due_at: datetime | None = None


class TaskOut(APIModel):
    id: str
    title: str
    description: str | None
    status: str
    due_at: datetime | None
    completed_at: datetime | None


class ChatRequest(APIModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    language: str | None = None
    document_ids: list[str] = Field(default_factory=list, max_length=12)


class ChatNoteRequest(APIModel):
    user_content: str = Field(min_length=1, max_length=4000)
    assistant_content: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    document_ids: list[str] = Field(default_factory=list, max_length=12)


class EvidenceOut(APIModel):
    document_id: str
    document_title: str
    page_number: int | None
    text_reference: str
    confidence: float | None


class ChatResponse(APIModel):
    conversation_id: str
    message_id: str
    answer: str
    evidence: list[EvidenceOut]
    data_access: dict
    external_ai: bool
    model: str | None
    collection_tree: list[dict] = []


class ShareCreate(APIModel):
    email: EmailStr
    role: str = "VIEWER"
    document_id: str | None = None
    collection_id: str | None = None


class ShareLinkCreate(APIModel):
    document_id: str | None = None
    collection_id: str | None = None
    expires_hours: int = 72
    password: str | None = None
    download_allowed: bool = False
    max_views: int | None = None


class SearchQuery(APIModel):
    q: str = ""
    category_id: str | None = None
    document_type_id: str | None = None
    tag: str | None = None
    person: str | None = None
    expiring: bool | None = None
    verified: bool | None = None
    shared: bool | None = None
    ai_indexed: bool | None = None
    limit: int = 40
    offset: int = 0


class FeedbackRequest(APIModel):
    message_id: str | None = None
    document_id: str | None = None
    metadata_id: str | None = None
    rating: str
    corrected_value: str | None = None
    field_name: str | None = None
    notes: str | None = None


class OnboardingRequest(APIModel):
    ai_privacy_mode: str = "PRIVATE"
    external_ai_enabled: bool = False
    categories: list[str] = []
    daily_briefing_enabled: bool = False
    weekly_report_enabled: bool = True
    language: str = "en"
