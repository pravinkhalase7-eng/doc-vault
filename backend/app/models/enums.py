from enum import Enum


class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class AIPrivacyMode(str, Enum):
    PRIVATE = "PRIVATE"
    CLOUD = "CLOUD"
    CUSTOM = "CUSTOM"


class SensitivityLevel(str, Enum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    SENSITIVE = "SENSITIVE"
    HIGHLY_SENSITIVE = "HIGHLY_SENSITIVE"


class DocumentStatus(str, Enum):
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    OCR_PROCESSING = "OCR_PROCESSING"
    AI_PROCESSING = "AI_PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"


class VerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    USER_CONFIRMED = "USER_CONFIRMED"
    REJECTED = "REJECTED"


class ShareRole(str, Enum):
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class TaskStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class NotificationChannel(str, Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"


class AIOperation(str, Enum):
    CLASSIFY = "CLASSIFY"
    EXTRACT = "EXTRACT"
    SUMMARIZE = "SUMMARIZE"
    SEARCH = "SEARCH"
    REASON = "REASON"
    CHECKLIST = "CHECKLIST"
    BRIEFING = "BRIEFING"
    ORGANIZE = "ORGANIZE"
    NAME = "NAME"
    COMPARE = "COMPARE"
    CHAT = "CHAT"
    EMBED = "EMBED"


class EntityKind(str, Enum):
    PERSON = "PERSON"
    VEHICLE = "VEHICLE"
    PROPERTY = "PROPERTY"
    ORGANIZATION = "ORGANIZATION"
    POLICY = "POLICY"
    ACCOUNT = "ACCOUNT"
    EVENT = "EVENT"
    DOCUMENT = "DOCUMENT"


class RelationshipType(str, Enum):
    OWNS = "OWNS"
    RELATED_TO = "RELATED_TO"
    ISSUED_BY = "ISSUED_BY"
    INSURES = "INSURES"
    APPLIES_TO = "APPLIES_TO"
    PARENT_OF = "PARENT_OF"
    MEMBER_OF = "MEMBER_OF"


class ThemePreference(str, Enum):
    LIGHT = "LIGHT"
    DARK = "DARK"
    SYSTEM = "SYSTEM"


class LanguageCode(str, Enum):
    EN = "en"
    HI = "hi"
    MR = "mr"


HIGHLY_SENSITIVE_TYPES = {
    "aadhaar",
    "pan",
    "passport",
    "bank_statement",
    "medical_report",
    "prescription",
    "lab_report",
    "credit_card",
    "voter_id",
    "driving_licence",
}

DEFAULT_CATEGORIES = [
    "Government",
    "Health",
    "Education",
    "Personal",
    "Finance",
    "Insurance",
    "Vehicle",
    "Property",
    "Work",
    "Legal",
    "Travel",
    "Family",
    "Photos",
    "Other",
]

DEFAULT_DOCUMENT_TYPES: dict[str, list[str]] = {
    "Government": ["Aadhaar", "PAN", "Passport", "Driving Licence", "Voter ID"],
    "Vehicle": ["RC", "Insurance", "PUC", "Service record", "Purchase invoice"],
    "Health": ["Prescription", "Medical report", "Insurance", "Vaccination certificate", "Lab report"],
    "Education": ["Degree", "Certificate", "Marksheet", "School document"],
    "Finance": ["Bank statement", "Invoice", "Receipt", "Tax document", "Loan document"],
    "Insurance": ["Policy", "Claim", "Premium receipt"],
    "Property": ["Sale deed", "Tax receipt", "Utility bill", "Lease"],
    "Work": ["Offer letter", "Payslip", "ID card", "Experience letter"],
    "Legal": ["Agreement", "Will", "Court order", "Affidavit"],
    "Travel": ["Ticket", "Visa", "Itinerary", "Hotel booking"],
    "Family": ["Birth certificate", "Marriage certificate", "Family photo"],
    "Photos": ["Photo"],
    "Personal": ["ID", "Letter", "Note"],
    "Other": ["Other"],
}

GOAL_CHECKLISTS: dict[str, list[str]] = {
    "renew_insurance": ["Insurance policy", "RC", "PUC", "Previous premium receipt"],
    "apply_for_passport": ["Passport", "Address proof", "Photograph", "Aadhaar"],
    "apply_for_visa": ["Passport", "Photograph", "Bank statement", "Travel itinerary", "Invitation letter"],
    "buy_a_house": ["ID proof", "Address proof", "Income proof", "Bank statement", "PAN"],
    "buy_a_car": ["Driving Licence", "PAN", "Address proof", "Insurance"],
    "school_admission": ["Birth certificate", "Address proof", "Photograph", "Previous marksheet"],
    "job_application": ["Resume", "Degree", "ID proof", "Experience letter"],
    "tax_preparation": ["PAN", "Form 16", "Bank statement", "Investment proofs"],
    "medical_claim": ["Medical report", "Bills", "Insurance policy", "ID proof"],
    "loan_application": ["PAN", "Aadhaar", "Bank statement", "Salary slips", "Address proof"],
}

LIFE_EVENTS = list(GOAL_CHECKLISTS.keys())
