"""
Pydantic models for the Personal CRM system.

This provides type safety, validation, and serialization/deserialization.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


# Enums for constrained values
class FactType(str, Enum):
    """Types of facts that can be stored about a person."""
    PREFERENCE = "preference"
    ACTIVITY = "activity"
    ATTRIBUTE = "attribute"
    POSSESSION = "possession"
    RELATIONSHIP = "relationship"
    BACKGROUND = "background"
    PROFESSIONAL = "professional"
    OTHER = "other"


class CRUDOperation(str, Enum):
    """CRUD operations supported by the system."""
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


# Core data models
class Fact(BaseModel):
    """A fact about a person with type and timestamp."""
    content: str = Field(..., min_length=1, description="The fact content")
    type: FactType = Field(default=FactType.OTHER, description="The fact type")
    timestamp: datetime = Field(..., description="When the fact was added")

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        use_enum_values=True
    )


class SocialMedia(BaseModel):
    """Social media handles for a person."""
    twitter: Optional[str] = None
    instagram: Optional[str] = None
    linkedin: Optional[str] = None
    other: Dict[str, str] = Field(default_factory=dict)


class Metadata(BaseModel):
    """Structured metadata about a person."""
    phone: Optional[str] = None
    email: Optional[str] = None
    social_media: SocialMedia = Field(default_factory=SocialMedia)
    age: Optional[int] = Field(None, ge=0, le=150)
    sex: Optional[str] = None
    location: Optional[str] = None
    occupation: Optional[str] = None
    company: Optional[str] = None
    birthday: Optional[str] = None  # Could be date type

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Basic email validation."""
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v


class Person(BaseModel):
    """A person in the CRM system."""
    id: str = Field(..., pattern=r'^person_\w+_\d{3}$')
    name: str = Field(..., min_length=1)
    hash_id: Optional[str] = Field(None, min_length=16, max_length=16)
    metadata: Metadata = Field(default_factory=Metadata)
    facts: List[Fact] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    last_updated: datetime

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}
    )

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Ensure tags are lowercase and unique."""
        return list(set(tag.lower() for tag in v))


class Database(BaseModel):
    """The entire CRM database."""
    people: List[Person] = Field(default_factory=list)

    def find_by_id(self, person_id: str) -> Optional[Person]:
        """Find a person by ID."""
        return next((p for p in self.people if p.id == person_id), None)

    def find_by_name(self, name: str) -> List[Person]:
        """Find all people with a given name (case-insensitive)."""
        name_lower = name.lower()
        return [p for p in self.people if p.name.lower() == name_lower]

    def delete_by_id(self, person_id: str) -> bool:
        """Delete a person by ID. Returns True if deleted."""
        original_count = len(self.people)
        self.people = [p for p in self.people if p.id != person_id]
        return len(self.people) < original_count


# LLM Request/Response models
class RouterRequest(BaseModel):
    """Input to the routing LLM."""
    user_input: str
    existing_data: Database


class ClarificationOption(BaseModel):
    """An option for disambiguating between people."""
    person_id: str
    person_name: str
    distinguishing_details: str


class RouterResponse(BaseModel):
    """Output from the routing LLM."""
    operation: CRUDOperation
    target_person_id: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    clarification_options: Optional[List[ClarificationOption]] = None


# CRUD operation models
class PersonCreate(BaseModel):
    """Data for creating a new person (no ID or timestamps yet)."""
    name: str = Field(..., min_length=1)
    metadata: Metadata = Field(default_factory=Metadata)
    facts: List[Dict[str, Any]] = Field(default_factory=list)  # Without timestamps
    tags: List[str] = Field(default_factory=list)


class PersonUpdate(BaseModel):
    """Data for updating a person."""
    metadata: Optional[Dict[str, Any]] = None
    new_facts: List[Dict[str, str]] = Field(default_factory=list)
    new_tags: List[str] = Field(default_factory=list)


class CreateExtraction(BaseModel):
    """LLM extraction for CREATE operation."""
    operation: CRUDOperation = Field(default=CRUDOperation.CREATE)
    person: PersonCreate
    summary: str


class UpdateExtraction(BaseModel):
    """LLM extraction for UPDATE operation."""
    operation: CRUDOperation = Field(default=CRUDOperation.UPDATE)
    person_id: str
    updates: PersonUpdate
    summary: str


class ReadQuery(BaseModel):
    """Query parameters for READ operation."""
    person_id: Optional[str] = None
    search_criteria: Optional[str] = None


class ReadExtraction(BaseModel):
    """LLM extraction for READ operation."""
    operation: CRUDOperation = Field(default=CRUDOperation.READ)
    query: ReadQuery
    summary: str


class DeleteExtraction(BaseModel):
    """LLM extraction for DELETE operation."""
    operation: CRUDOperation = Field(default=CRUDOperation.DELETE)
    person_id: str
    summary: str


# Config model
class Config(BaseModel):
    """Application configuration."""
    llm_provider: str = Field(default="groq")
    groq_api_key: Optional[str] = None
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    openai_api_key: Optional[str] = None
    openai_model: str = Field(default="gpt-4")
    data_file: str = Field(default="data.json")
    log_file: str = Field(default="crm.log")
    log_level: str = Field(default="INFO")

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        import os
        from dotenv import load_dotenv
        load_dotenv()

        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "groq").lower(),
            groq_api_key=os.getenv("GROQ_API_KEY"),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4"),
        )
